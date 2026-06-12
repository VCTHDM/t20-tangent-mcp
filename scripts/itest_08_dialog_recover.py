"""真机联调 Step 8 — 诊断并尝试 ESC 恢复阻塞会话.

  1. 枚举 acad.exe 进程的全部可见顶层窗口, 打印类名/标题 (P1-2 判据情报)
  2. 对疑似对话框 (非主窗) 仅发送 ESC 取消
  3. ping 验证会话恢复

注意: 严禁对天正 ARX 对话框发送 WM_CLOSE, 真机曾因此 AutoCAD 致命错误。
若 ESC 后仍阻塞, 改用 scripts/itest_11_force_recover.py 点击取消按钮。

用法: uv run python scripts/itest_08_dialog_recover.py
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


def enum_acad_windows() -> list[tuple[int, str, str]]:
    out: list[tuple[int, str, str]] = []

    def cb(hwnd, _):
        if not win32gui.IsWindowVisible(hwnd):
            return True
        try:
            _, pid = win32process.GetWindowThreadProcessId(hwnd)
        except Exception:
            return True
        if _process_image_name(pid) == "acad.exe":
            out.append((hwnd, win32gui.GetClassName(hwnd), win32gui.GetWindowText(hwnd)))
        return True

    win32gui.EnumWindows(cb, None)
    return out


async def main() -> int:
    main_hwnd = find_autocad_window()
    windows = enum_acad_windows()
    print("acad.exe 可见顶层窗口:")
    dialogs: list[int] = []
    for hwnd, cls, title in windows:
        tag = " <-- 主窗" if hwnd == main_hwnd else ""
        print(f"  hwnd={hwnd} class={cls!r} title={title!r}{tag}")
        if hwnd != main_hwnd:
            dialogs.append(hwnd)

    for hwnd in dialogs:
        print(f"尝试恢复 hwnd={hwnd}: 仅发送 ESC")
        win32gui.PostMessage(hwnd, win32con.WM_KEYDOWN, win32con.VK_ESCAPE, 0)
        win32gui.PostMessage(hwnd, win32con.WM_KEYUP, win32con.VK_ESCAPE, 0)
        time.sleep(0.5)
        if win32gui.IsWindow(hwnd) and win32gui.IsWindowVisible(hwnd):
            print(f"  仍可见: hwnd={hwnd}; 请运行 itest_11_force_recover.py 点取消按钮")

    backend = FileIPCBackend()
    init = await backend.initialize()
    print(f"恢复验证 initialize/ping -> ok={init.ok} error={init.error!r}")
    if init.ok:
        env = await backend.drawing_get_variables(["CMDDIA", "FILEDIA", "OSMODE", "CMDACTIVE"])
        print(f"环境: {env.payload}")
    return 0 if init.ok else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
