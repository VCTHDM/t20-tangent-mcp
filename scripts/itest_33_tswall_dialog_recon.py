"""真机联调 Step 33 — TSWall 单线变墙弹框/提示侦察.

目的: Handoff 12/14 记录 TSWall 能选中 LINE, 但回车后没有生成 TCH_WALL。
本脚本只做取证:
  1. 记录基线实体数并创建一条 LINE;
  2. 用 vl-cmdf 启动 TSWALL, 传入 LINE 选择集并回车;
  3. 观察是否出现新的 acad.exe 顶层窗口, 若有则 dump 类名/标题/子控件;
  4. 只发 ESC 恢复, 严禁 WM_CLOSE;
  5. UNDO 回到基线实体数并复位环境。

用法: uv run python scripts/itest_33_tswall_dialog_recon.py
"""

from __future__ import annotations

import asyncio
import sys
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

LAUNCH_TSWALL = (
    _load_prelude()
    + """
(defun c:t20mcp-tswall-recon ( / *error* prev new ss)
  (defun *error* (m) (princ (strcat "\\nT20MCP-TSWALL-ERR " (if m m "?"))))
  (setq prev (entlast))
  ;; Python 侧刚创建一条 LINE, 这里只选择 entlast, 避免误选用户图中的其他 LINE。
  (setq ss (ssadd (entlast)))
  (vl-catch-all-apply 'vl-cmdf (list "TSWALL" ss ""))
  (setq new (entlast))
  (strcat
    "active=" (itoa (getvar "CMDACTIVE"))
    " newtype="
    (if (and new (not (eq prev new))) (cdr (assoc 0 (entget new))) "none")))
(c:t20mcp-tswall-recon)
"""
)


def acad_windows() -> set[int]:
    windows: set[int] = set()

    def callback(hwnd: int, _: object) -> bool:
        if win32gui.IsWindowVisible(hwnd):
            try:
                _, pid = win32process.GetWindowThreadProcessId(hwnd)
            except Exception:
                return True
            if _process_image_name(pid) == "acad.exe":
                windows.add(hwnd)
        return True

    win32gui.EnumWindows(callback, None)
    return windows


def dump_window(hwnd: int) -> list[str]:
    rows = [
        f"WINDOW class={win32gui.GetClassName(hwnd)} title={win32gui.GetWindowText(hwnd)!r}"
    ]

    def callback(child: int, _: object) -> bool:
        try:
            rows.append(
                f"  {win32gui.GetClassName(child)} | {win32gui.GetWindowText(child)!r}"
            )
        except Exception:
            pass
        return True

    try:
        win32gui.EnumChildWindows(hwnd, callback, None)
    except Exception:
        pass
    return rows


def send_escape(hwnd: int, times: int = 2) -> None:
    for _ in range(times):
        win32gui.PostMessage(hwnd, win32con.WM_KEYDOWN, win32con.VK_ESCAPE, 0)
        win32gui.PostMessage(hwnd, win32con.WM_KEYUP, win32con.VK_ESCAPE, 0)


async def entity_count(backend: FileIPCBackend) -> int:
    result = await backend.entity_count()
    return result.payload["count"] if result.ok else -1


async def cleanup_to(backend: FileIPCBackend, target_count: int) -> bool:
    await backend.execute_lisp(RESET_ENV)
    rounds = 0
    while rounds < 12:
        count = await entity_count(backend)
        if count < 0 or count <= target_count:
            break
        await backend.undo()
        rounds += 1
    env = await backend.drawing_get_variables(["CMDACTIVE", "CMDDIA", "FILEDIA", "OSMODE"])
    final = await entity_count(backend)
    print(f"[cleanup] entities={final} env={env.payload if env.ok else env.error}")
    return (
        env.ok
        and final == target_count
        and env.payload.get("CMDACTIVE") == 0
        and env.payload.get("CMDDIA") == 1
        and env.payload.get("FILEDIA") == 1
        and env.payload.get("OSMODE") == 0
    )


async def main() -> int:
    backend = FileIPCBackend()
    init = await backend.initialize()
    if not init.ok:
        print(f"FAIL: initialize: {init.error}")
        return 1

    await backend.execute_lisp(RESET_ENV)
    baseline_count = await entity_count(backend)
    baseline_windows = acad_windows()
    await backend.create_line(0, 0, 3000, 0)
    line_count = await entity_count(backend)
    print(f"[setup] entities {baseline_count}->{line_count}")

    task = asyncio.create_task(backend.execute_lisp(LAUNCH_TSWALL))
    dialog = None
    for _ in range(24):
        await asyncio.sleep(0.25)
        new_windows = acad_windows() - baseline_windows
        if new_windows:
            dialog = next(iter(new_windows))
            break
        if task.done():
            break

    if dialog is None:
        print("[dialog] none observed")
    else:
        print("[dialog] observed")
        for row in dump_window(dialog):
            print(row)
        send_escape(dialog)

    try:
        result = await asyncio.wait_for(task, timeout=10.0)
        print(f"[lisp] ok={result.ok} payload={result.payload!r} error={result.error!r}")
    except asyncio.TimeoutError:
        task.cancel()
        print("[lisp] task-timeout after ESC; stop before any stronger recovery")

    if backend._command_hwnd:
        send_escape(backend._command_hwnd)
    await asyncio.sleep(0.5)
    clean = await cleanup_to(backend, baseline_count)
    return 0 if clean else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
