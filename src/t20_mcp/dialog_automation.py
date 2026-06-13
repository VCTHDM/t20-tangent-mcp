"""Win32 对话框按钮自动化 — 白名单 + BM_CLICK only。

适用场景: 个别天正命令 (如 TEXPLODE) 必弹原生 #32770 模态框, 无法纯命令行
驱动, 但框内按钮可枚举可点击。本模块提供受控的「等框 → 按序点按钮」原语。

安全边界 (PROJECT_RULES.md 铁律):
  * 只对 **标题精确匹配白名单** 的对话框动手, 按钮文本也必须精确匹配;
  * 只用 BM_CLICK 点击按钮; **严禁 WM_CLOSE** (真机曾致 AutoCAD 致命错误);
  * 找不到框/按钮一律超时返回, 不做任何兜底强关; 恢复交给调用方 (ESC 路径)。

itest_24 真机验证 (2026-06-13): TEXPLODE「分解对象」框, 点
「分解当前选中的天正对象」+「确定」后, 命令继续在命令行提示选择对象,
vl-cmdf 参数队列里的选择集被正常消费。
"""

from __future__ import annotations

import asyncio
import sys

BM_CLICK = 0x00F5

# 唯一获准自动点击的对话框 → 按钮点击序列。新增条目必须 fable review。
TEXPLODE_DIALOG_TITLE = "分解对象"
TEXPLODE_BUTTONS = ("分解当前选中的天正对象", "确定")

# 危险按钮黑名单: 任何驱动序列都不得包含 (会波及用户实体)。
FORBIDDEN_BUTTONS = frozenset({"分解本图所有天正对象", "分解块参照内天正对象"})


def _win32_available() -> bool:
    if sys.platform != "win32":
        return False
    try:
        import win32gui  # noqa: F401

        return True
    except ImportError:
        return False


def _find_dialog(title: str) -> int | None:
    """在 acad 进程的可见顶层窗口中找标题精确匹配的 #32770。"""
    import win32gui
    import win32process

    from t20_mcp.backends.file_ipc import _process_image_name
    from t20_mcp.config import ACAD_PROCESS_NAME

    found: list[int] = []

    def cb(hwnd: int, _: object) -> bool:
        try:
            if not win32gui.IsWindowVisible(hwnd):
                return True
            if win32gui.GetClassName(hwnd) != "#32770":
                return True
            if win32gui.GetWindowText(hwnd) != title:
                return True
            _, pid = win32process.GetWindowThreadProcessId(hwnd)
            if _process_image_name(pid) == ACAD_PROCESS_NAME:
                found.append(hwnd)
        except Exception:
            pass
        return True

    win32gui.EnumWindows(cb, None)
    return found[0] if found else None


def _find_button(dialog: int, text: str) -> int | None:
    import win32gui

    found: list[int] = []

    def cb(child: int, _: object) -> bool:
        try:
            if (
                win32gui.GetClassName(child) == "Button"
                and win32gui.GetWindowText(child) == text
            ):
                found.append(child)
        except Exception:
            pass
        return True

    try:
        win32gui.EnumChildWindows(dialog, cb, None)
    except Exception:
        pass
    return found[0] if found else None


async def click_dialog_buttons(
    title: str,
    buttons: tuple[str, ...],
    timeout: float = 8.0,
    settle: float = 0.3,
) -> str:
    """等待标题为 ``title`` 的对话框出现, 按序 BM_CLICK ``buttons``。

    返回结果描述字符串 (供日志/payload):
      clicked-dialog-closed / dialog-never-appeared /
      button-missing:<text> / dialog-still-open / forbidden:<text> /
      win32-unavailable
    """
    for text in buttons:
        if text in FORBIDDEN_BUTTONS:
            return f"forbidden:{text}"
    if not buttons:
        return "no-buttons-specified"
    if not _win32_available():
        return "win32-unavailable"

    import win32gui

    loop = asyncio.get_event_loop()
    deadline = loop.time() + timeout
    while loop.time() < deadline:
        dialog = _find_dialog(title)
        if dialog:
            for text in buttons:
                btn = _find_button(dialog, text)
                if btn is None:
                    return f"button-missing:{text}"
                win32gui.PostMessage(btn, BM_CLICK, 0, 0)
                await asyncio.sleep(settle)
            await asyncio.sleep(settle)
            if _find_dialog(title) is None:
                return "clicked-dialog-closed"
            # 个别情况首次确定未关框: 再点一次最后一个按钮
            btn = _find_button(dialog, buttons[-1])
            if btn is not None:
                win32gui.PostMessage(btn, BM_CLICK, 0, 0)
                await asyncio.sleep(settle * 2)
            return (
                "clicked-dialog-closed"
                if _find_dialog(title) is None
                else "dialog-still-open"
            )
        await asyncio.sleep(0.25)
    return "dialog-never-appeared"


async def drive_texplode_dialog(timeout: float = 8.0) -> str:
    """TEXPLODE「分解对象」框的标准驱动序列 (itest_24 真机验证)。"""
    return await click_dialog_buttons(TEXPLODE_DIALOG_TITLE, TEXPLODE_BUTTONS, timeout)
