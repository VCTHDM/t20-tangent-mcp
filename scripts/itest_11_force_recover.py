"""真机联调 Step 11 — 强制恢复阻塞会话: 已知模态弹框点取消按钮 + Lisp reset.

目标:
    当 itest_08_dialog_recover.py 仅靠 ESC 不足以退出某些 #32770 弹框
    (例如「门窗参数」「图形导出」「天正模型导出到TGL」), 用 WM_COMMAND IDCANCEL
    模拟点击对话框上的"取消"按钮, 然后跑标准 reset Lisp 把环境拉回:
        CMDACTIVE=0  CMDDIA=1  FILEDIA=1  OSMODE=0
    最后 initialize/ping + drawing_get_variables 验证恢复结果。

铁律 (与 directive + Handoff 09 一致):
    1. 严禁 WM_CLOSE — 真机曾因此 AutoCAD 致命错误。
    2. 仅识别白名单标题的 #32770 弹框, 其它顶层窗口只 ESC 不点击。
    3. 仅发 WM_COMMAND IDCANCEL (= 2), 等价于"点 Cancel 按钮", 由对话框自己处理。
    4. 不打开 dialog_automation.py, 不点其它按钮, 不填文本框。

用法: uv run python scripts/itest_11_force_recover.py
"""

from __future__ import annotations

import asyncio
import sys
import time
from pathlib import Path

sys.stdout.reconfigure(errors="replace")
sys.path.insert(0, str(Path(__file__).resolve().parent))            # for _live_lock
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import win32con
import win32gui
import win32process

from _live_lock import live_lock_or_exit  # noqa: E402  (imported after sys.path setup)

from t20_mcp.backends.file_ipc import (  # noqa: E402
    FileIPCBackend,
    _process_image_name,
    find_autocad_window,
)

# 已知可点 IDCANCEL 安全恢复的 #32770 弹框标题白名单。
# 不在此列表内的弹框只发 ESC, 不点按钮, 避免误点。
KNOWN_CANCELABLE_TITLES = (
    "门窗参数",
    "图形导出",
    "天正模型导出到TGL",
)

IDCANCEL = 2  # 标准 Cancel 按钮 ID

RESET_ENV_LISP = (
    '(progn (setq n 0)'
    ' (while (and (< n 8) (> (getvar "CMDACTIVE") 0)) (command) (setq n (1+ n)))'
    ' (setvar "CMDDIA" 1) (setvar "FILEDIA" 1) (setvar "OSMODE" 0)'
    ' (strcat "rst CMDACTIVE=" (itoa (getvar "CMDACTIVE"))))'
)


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


def post_idcancel(hwnd: int) -> None:
    """对 #32770 发 WM_COMMAND IDCANCEL, 等价于点击对话框的取消按钮."""
    win32gui.PostMessage(hwnd, win32con.WM_COMMAND, IDCANCEL, 0)


def post_escape(hwnd: int) -> None:
    win32gui.PostMessage(hwnd, win32con.WM_KEYDOWN, win32con.VK_ESCAPE, 0)
    win32gui.PostMessage(hwnd, win32con.WM_KEYUP, win32con.VK_ESCAPE, 0)


async def main() -> int:
    main_hwnd = find_autocad_window()
    if not main_hwnd:
        print("FAIL: 未找到 acad.exe 主窗口")
        return 1

    windows = enum_acad_windows()
    print("acad.exe 可见顶层窗口:")
    for hwnd, cls, title in windows:
        tag = " <-- 主窗" if hwnd == main_hwnd else ""
        print(f"  hwnd={hwnd} class={cls!r} title={title!r}{tag}")

    # 1) 对白名单 #32770 发 WM_COMMAND IDCANCEL
    cancelable: list[tuple[int, str]] = []
    other_dialogs: list[tuple[int, str, str]] = []
    for hwnd, cls, title in windows:
        if hwnd == main_hwnd:
            continue
        if cls == "#32770" and any(t in title for t in KNOWN_CANCELABLE_TITLES):
            cancelable.append((hwnd, title))
        else:
            other_dialogs.append((hwnd, cls, title))

    for hwnd, title in cancelable:
        print(f"\n点取消 (IDCANCEL): hwnd={hwnd} title={title!r}")
        post_idcancel(hwnd)
        time.sleep(0.5)
        if win32gui.IsWindow(hwnd) and win32gui.IsWindowVisible(hwnd):
            print(f"  IDCANCEL 后仍可见, 再补一次 ESC")
            post_escape(hwnd)
            time.sleep(0.4)

    # 2) 其它非白名单顶层窗口只 ESC 不点击
    for hwnd, cls, title in other_dialogs:
        print(f"\n非白名单 (仅 ESC): hwnd={hwnd} class={cls!r} title={title!r}")
        post_escape(hwnd)
        time.sleep(0.3)

    # 3) Lisp reset
    backend = FileIPCBackend()
    init = await backend.initialize()
    if not init.ok:
        print(f"\n[reset] initialize 失败 (dispatcher 未加载?): {init.error}")
        # 此时无法用 dispatcher 跑 reset, 只能依赖前面 IDCANCEL/ESC 的结果
        return 1

    rst = await backend.execute_lisp(RESET_ENV_LISP)
    print(f"\n[reset] lisp ok={rst.ok} payload={rst.payload!r} error={rst.error!r}")

    # 4) 验证: ping + 关键环境变量
    env = await backend.drawing_get_variables(["CMDACTIVE", "CMDDIA", "FILEDIA", "OSMODE"])
    print(f"[verify] env={env.payload}")

    # 5) 二次窗口枚举, 确认弹框已退
    after = enum_acad_windows()
    leftovers = [
        (h, c, t) for h, c, t in after
        if h != main_hwnd and c == "#32770"
        and any(tt in t for tt in KNOWN_CANCELABLE_TITLES)
    ]
    print(f"[verify] 残留白名单弹框: {leftovers}")

    ok = (
        env.ok
        and env.payload.get("CMDACTIVE") == 0
        and env.payload.get("CMDDIA") == 1
        and env.payload.get("FILEDIA") == 1
        and env.payload.get("OSMODE") == 0
        and not leftovers
    )
    print(f"\n=== Step11 verdict: {'PASS' if ok else 'FAIL'} ===")
    return 0 if ok else 1


if __name__ == "__main__":
    _lock = live_lock_or_exit(__file__)
    raise SystemExit(asyncio.run(main()))
