"""真机联调 Step 17 — 导出替代命令探测 (ESC-only 恢复).

探测 `TPartSaveAs` 与 `TGetXML` 的最小空输入行为。遇到超时/弹框时只发 ESC,
不发送 WM_CLOSE。该脚本用于记录可驱动性, 不生成正式封装。

用法: uv run python scripts/itest_17_export_alternatives.py
"""

from __future__ import annotations

import asyncio
import sys
import time
from pathlib import Path

sys.stdout.reconfigure(errors="replace")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import win32con
import win32gui
import win32process

from t20_mcp.backends.file_ipc import FileIPCBackend, _process_image_name
from t20_mcp.tools.tangent import _load_prelude

RESET_ENV = """
(progn
  (setq n 0)
  (while (and (< n 6) (> (getvar "CMDACTIVE") 0))
    (command)
    (setq n (1+ n)))
  (setvar "CMDDIA" 1)
  (setvar "FILEDIA" 1)
  (setvar "OSMODE" 0)
  "env-reset")
"""


def acad_windows() -> list[tuple[int, str, str]]:
    out: list[tuple[int, str, str]] = []

    def cb(hwnd: int, _: object) -> bool:
        if win32gui.IsWindowVisible(hwnd):
            try:
                _, pid = win32process.GetWindowThreadProcessId(hwnd)
            except Exception:
                return True
            if _process_image_name(pid) == "acad.exe":
                out.append((hwnd, win32gui.GetClassName(hwnd), win32gui.GetWindowText(hwnd)))
        return True

    win32gui.EnumWindows(cb, None)
    return out


def send_esc_to_new_windows(baseline: list[tuple[int, str, str]]) -> list[tuple[str, str]]:
    base = {hwnd for hwnd, _, _ in baseline}
    seen: list[tuple[str, str]] = []
    for hwnd, cls, title in acad_windows():
        if hwnd in base:
            continue
        seen.append((cls, title))
        win32gui.PostMessage(hwnd, win32con.WM_KEYDOWN, win32con.VK_ESCAPE, 0)
        win32gui.PostMessage(hwnd, win32con.WM_KEYUP, win32con.VK_ESCAPE, 0)
    return seen


def trial_lisp(command: str) -> str:
    tag = command.lower()
    return (
        _load_prelude()
        + "\n"
        + f"""
(defun c:t20mcp-trial ( / t20mcp:saved *error* t20mcp:prev t20mcp:new)
  (setq t20mcp:saved (t20mcp:begin "{tag}"))
  (defun *error* (m) (t20mcp:on-error m t20mcp:saved))
  (setq t20mcp:prev (entlast))
  (t20mcp:call "{command}" (list ""))
  (setq t20mcp:new (entlast))
  (if (and t20mcp:new (not (eq t20mcp:prev t20mcp:new)))
      (t20mcp:end "{tag}:entity-created" t20mcp:saved)
      (t20mcp:fail "{tag}" t20mcp:saved "no-entity"))
  (princ))
(c:t20mcp-trial)
"""
    )


async def count(backend: FileIPCBackend) -> int:
    result = await backend.entity_count()
    return result.payload["count"] if result.ok else -999


async def main() -> int:
    backend = FileIPCBackend()
    init = await backend.initialize()
    if not init.ok:
        print(f"FAIL: initialize: {init.error}")
        return 1

    await backend.execute_lisp(RESET_ENV)
    all_recovered = True
    for command in ("TPARTSAVEAS", "TGETXML"):
        baseline = acad_windows()
        before = await count(backend)
        result = await backend.execute_lisp(trial_lisp(command))
        after = await count(backend)
        print(
            f"[{command}] ok={result.ok} payload={result.payload!r} "
            f"error={result.error!r} entities {before}->{after}"
        )
        if not result.ok and "Timeout" in (result.error or ""):
            windows = send_esc_to_new_windows(baseline)
            print(f"  timeout windows: {windows or '(none)'}")
            if backend._command_hwnd:
                for _ in range(2):
                    win32gui.PostMessage(
                        backend._command_hwnd, win32con.WM_KEYDOWN, win32con.VK_ESCAPE, 0
                    )
                    win32gui.PostMessage(
                        backend._command_hwnd, win32con.WM_KEYUP, win32con.VK_ESCAPE, 0
                    )
            time.sleep(1.0)
        reset = await backend.execute_lisp(RESET_ENV)
        env = await backend.drawing_get_variables(["CMDACTIVE", "CMDDIA", "FILEDIA", "OSMODE"])
        recovered = (
            reset.ok
            and env.ok
            and env.payload.get("CMDACTIVE") == 0
            and env.payload.get("CMDDIA") == 1
            and env.payload.get("FILEDIA") == 1
            and env.payload.get("OSMODE") == 0
            and await count(backend) == before
        )
        all_recovered = all_recovered and recovered
        print(f"  recovered={recovered} env={env.payload if env.ok else env.error}")

    return 0 if all_recovered else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
