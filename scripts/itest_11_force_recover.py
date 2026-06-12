"""真机联调 Step 11 — 强力恢复: 点击挂起对话框的按钮 (BM_CLICK).

枚举 acad.exe 的 #32770 对话框, 打印其全部子控件 (类名/文本),
优先点击 取消/否/关闭, 否则点击 确定/是 等默认按钮, 直至 ping 恢复。

用法: uv run python scripts/itest_11_force_recover.py
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

BM_CLICK = 0x00F5

CANCEL_WORDS = ("取消", "否", "关闭", "cancel", "no", "close")
OK_WORDS = ("确定", "是", "ok", "yes")


def acad_dialogs() -> list[int]:
    out: list[int] = []

    def cb(hwnd, _):
        if win32gui.IsWindowVisible(hwnd):
            try:
                _, pid = win32process.GetWindowThreadProcessId(hwnd)
            except Exception:
                return True
            if _process_image_name(pid) == "acad.exe" and win32gui.GetClassName(hwnd) == "#32770":
                out.append(hwnd)
        return True

    win32gui.EnumWindows(cb, None)
    return out


def children(hwnd: int) -> list[tuple[int, str, str]]:
    out: list[tuple[int, str, str]] = []

    def cb(child, _):
        out.append((child, win32gui.GetClassName(child), win32gui.GetWindowText(child)))
        return True

    try:
        win32gui.EnumChildWindows(hwnd, cb, None)
    except Exception:
        pass
    return out


def click_button(dialog: int) -> str | None:
    btns = [(h, t) for h, c, t in children(dialog) if c == "Button"]
    for words in (CANCEL_WORDS, OK_WORDS):
        for h, t in btns:
            label = t.replace("&", "").strip().lower()
            if any(w in label for w in words):
                win32gui.PostMessage(h, BM_CLICK, 0, 0)
                return t
    if btns:  # 没匹配词就点第一个按钮
        win32gui.PostMessage(btns[0][0], BM_CLICK, 0, 0)
        return btns[0][1]
    return None


async def main() -> int:
    for round_no in range(1, 6):
        dialogs = acad_dialogs()
        if not dialogs:
            print(f"[round {round_no}] 无 #32770 对话框")
            break
        for d in dialogs:
            title = win32gui.GetWindowText(d)
            print(f"[round {round_no}] dialog hwnd={d} title={title!r}")
            for h, c, t in children(d):
                print(f"    child class={c!r} text={t!r}")
            clicked = click_button(d)
            print(f"    -> 点击按钮: {clicked!r}")
        time.sleep(1.0)

    backend = FileIPCBackend()
    init = await backend.initialize()
    print(f"恢复验证 -> ok={init.ok}")
    if init.ok:
        await backend.execute_lisp('(progn (setvar "CMDDIA" 1) (setvar "FILEDIA" 1))')
        env = await backend.drawing_get_variables(["CMDDIA", "FILEDIA", "OSMODE", "CMDACTIVE"])
        r = await backend.entity_count()
        print(f"环境: {env.payload} entities={r.payload}")
    return 0 if init.ok else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
