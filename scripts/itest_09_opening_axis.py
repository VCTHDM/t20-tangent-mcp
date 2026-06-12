"""真机联调 Step 9 — 环境复位 + TOPENING/TRECTAXIS 试验 (带弹框自动恢复).

  0. 复位 CMDDIA=1 / FILEDIA=1 (清除上次对话框阻塞留下的静默态泄漏)
  1. TOPENING: 画墙 → 墙中点插门窗 → 看 TCH_OPENING
  2. TRECTAXIS: 最小驱动试验
  超时(=弹框)时: 枚举 acad.exe 新增窗口并发 ESC 自动取消, ping 验证恢复。

用法: uv run python scripts/itest_09_opening_axis.py
"""

from __future__ import annotations

import asyncio
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import win32con
import win32gui
import win32process

from t20_mcp.backends.file_ipc import FileIPCBackend, _process_image_name, find_autocad_window
from t20_mcp.tools.tangent import _load_prelude

TRIAL = """
(defun c:t20mcp-trial ( / t20mcp:saved *error*)
  (setq t20mcp:saved (t20mcp:begin "trial"))
  (defun *error* (m) (t20mcp:on-error m t20mcp:saved))
  (if (t20mcp:call "{CMD}" (list {ARGS}))
      (t20mcp:end "trial" t20mcp:saved)
      (t20mcp:fail "trial" t20mcp:saved "command-failed"))
  (princ))
(c:t20mcp-trial)
"""

LAST_TYPE = '(if (entlast) (cdr (assoc 0 (entget (entlast)))) "none")'
RESTORE_ENV = '(progn (setvar "CMDDIA" 1) (setvar "FILEDIA" 1) "env-restored")'


def acad_windows() -> set[int]:
    out: set[int] = set()

    def cb(hwnd, _):
        if win32gui.IsWindowVisible(hwnd):
            try:
                _, pid = win32process.GetWindowThreadProcessId(hwnd)
            except Exception:
                return True
            if _process_image_name(pid) == "acad.exe":
                out.add(hwnd)
        return True

    win32gui.EnumWindows(cb, None)
    return out


def dismiss_new_windows(baseline: set[int]) -> list[str]:
    dismissed = []
    for hwnd in acad_windows() - baseline:
        cls = win32gui.GetClassName(hwnd)
        title = win32gui.GetWindowText(hwnd)
        dismissed.append(f"{cls!r}:{title!r}")
        win32gui.PostMessage(hwnd, win32con.WM_KEYDOWN, win32con.VK_ESCAPE, 0)
        win32gui.PostMessage(hwnd, win32con.WM_KEYUP, win32con.VK_ESCAPE, 0)
        time.sleep(0.4)
        if win32gui.IsWindow(hwnd) and win32gui.IsWindowVisible(hwnd):
            dismissed.append(f"still-visible:{cls!r}:{title!r}")
    return dismissed


async def count(backend: FileIPCBackend) -> int:
    r = await backend.entity_count()
    if not r.ok:
        return -999
    return r.payload["count"]


async def trial(backend: FileIPCBackend, label: str, cmd: str, args: str) -> int:
    baseline = acad_windows()
    before = await count(backend)
    code = _load_prelude() + "\n" + TRIAL.replace("{CMD}", cmd).replace("{ARGS}", args)
    result = await backend.execute_lisp(code)
    if not result.ok and "Timeout" in (result.error or ""):
        closed = dismiss_new_windows(baseline)
        print(f"[{label}] TIMEOUT(弹框) -> 自动关闭: {closed or '(未发现新窗口)'}")
        time.sleep(1.0)
        ping = await backend._dispatch("ping", {})
        await backend.execute_lisp(RESTORE_ENV)
        print(f"  恢复: ping ok={ping.ok}")
        return -1
    after = await count(backend)
    last_type = await backend.execute_lisp(LAST_TYPE)
    print(f"[{label}] ok={result.ok} entities {before}->{after} "
          f"last={last_type.payload!r} error={result.error!r}")
    return after - before


async def main() -> int:
    backend = FileIPCBackend()
    init = await backend.initialize()
    if not init.ok:
        print(f"FAIL: initialize: {init.error}")
        return 1

    # --- 0: 环境复位 ---
    r = await backend.execute_lisp(RESTORE_ENV)
    env = await backend.drawing_get_variables(["CMDDIA", "FILEDIA", "OSMODE", "CMDACTIVE"])
    print(f"[0 复位] {r.payload!r} env={env.payload} entities={await count(backend)}")

    # --- 1: TOPENING (先画墙) ---
    wall_delta = await trial(backend, "1a 画墙备用", "TGWALL",
                             '(t20mcp:pt 0 0) (t20mcp:pt 3000 0) ""')
    opening_delta = await trial(backend, "1b TOPENING [墙中点]", "TOPENING",
                                '(t20mcp:pt 1500 0) ""')
    if opening_delta > 0:
        await backend.undo()
    if wall_delta > 0:
        await backend.undo()
    print(f"  清理后实体数: {await count(backend)}")

    # --- 2: TRECTAXIS ---
    axis_delta = await trial(backend, "2 TRECTAXIS 最小试验", "TRECTAXIS", '""')
    if axis_delta > 0:
        await backend.undo()
    print(f"  最终实体数: {await count(backend)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
