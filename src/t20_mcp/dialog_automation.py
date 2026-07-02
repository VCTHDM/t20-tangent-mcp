"""Win32 对话框/面板自动化 — 白名单 + 受控原语。

适用场景:
  1. 个别天正命令 (如 TEXPLODE) 必弹原生 #32770 模态框, 无法纯命令行驱动,
     但框内按钮可枚举可点击 —「等框 → 按序点按钮」(itest_24 真机验证)。
  2. TGColumn 标准柱面板 (Handoff 36, itest_39 真机验证): 无标题 #32770
     浮动面板, owner 不被 disable, 无 确定/取消 按钮 — 参数即时生效,
     落地靠向命令行打插入点坐标, 退出靠 ESC。控件按「class + 标签锚点」
     每次运行时重新发现 (hwnd 会话性), 定位规则见
     docs/handoff/36_tgcolumn_control_map.md。

安全边界 (PROJECT_RULES.md 铁律):
  * 只对白名单对话框动手: 标题精确匹配 (TEXPLODE「分解对象」), 或结构指纹
    精确匹配 (TGColumn = 含 title='柱高' #32770 子面板的无标题 #32770);
  * 按钮只用 BM_CLICK; **严禁 WM_CLOSE** (真机曾致 AutoCAD 致命错误);
  * Edit 写入只用 WM_SETTEXT + 回读校验 + EN_KILLFOCUS 通知补发;
    ComboBox 只用 CB_SETCURSEL + CBN_SELENDOK/CBN_SELCHANGE 通知补发;
  * 找不到框/控件一律返回失败, 不做任何兜底强关; 恢复交给调用方 (ESC 路径)。
"""

from __future__ import annotations

import asyncio
import ctypes
import sys

BM_CLICK = 0x00F5
WM_SETTEXT = 0x000C
WM_GETTEXT = 0x000D
WM_GETTEXTLENGTH = 0x000E
WM_COMMAND = 0x0111
WM_CHAR = 0x0102
WM_KEYDOWN = 0x0100
WM_KEYUP = 0x0101
VK_ESCAPE = 0x1B
EN_KILLFOCUS = 0x0200
CB_GETCOUNT = 0x0146
CB_GETCURSEL = 0x0147
CB_GETLBTEXT = 0x0148
CB_GETLBTEXTLEN = 0x0149
CB_SETCURSEL = 0x014E
CBN_SELCHANGE = 1
CBN_KILLFOCUS = 4
CBN_EDITCHANGE = 5
CBN_SELENDOK = 9

# 唯一获准自动点击的对话框 → 按钮点击序列。新增条目必须经评审。
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


# ---------------------------------------------------------------------------
# 通用控件原语 (Handoff 36 / itest_39 真机验证)
# ---------------------------------------------------------------------------

_user32 = ctypes.windll.user32 if sys.platform == "win32" else None


def get_window_text(hwnd: int) -> str:
    """WM_GETTEXT 读控件文本 (win32gui.GetWindowText 对 Edit 有时取不到)。"""
    n = _user32.SendMessageW(hwnd, WM_GETTEXTLENGTH, 0, 0)
    buf = ctypes.create_unicode_buffer(n + 1)
    _user32.SendMessageW(hwnd, WM_GETTEXT, n + 1, buf)
    return buf.value


def set_edit_text(hwnd: int, text: str) -> bool:
    """WM_SETTEXT 写 Edit + 回读校验 + 向父窗补发 EN_KILLFOCUS (触发 MFC DDX)。

    返回回读是否与写入一致。EN_KILLFOCUS 通知必须补发 — 面板内部状态在
    失焦提交时才更新 (itest_39 真机验证该组合生效)。"""
    import win32gui

    _user32.SendMessageW(hwnd, WM_SETTEXT, 0, ctypes.c_wchar_p(text))
    ok = get_window_text(hwnd) == text
    parent = win32gui.GetParent(hwnd)
    ctrl_id = win32gui.GetDlgCtrlID(hwnd)
    _user32.SendMessageW(parent, WM_COMMAND, (EN_KILLFOCUS << 16) | ctrl_id, hwnd)
    return ok


def combo_items(hwnd: int) -> list[str]:
    """枚举 ComboBox 全部条目文本。"""
    out = []
    for i in range(_user32.SendMessageW(hwnd, CB_GETCOUNT, 0, 0)):
        n = _user32.SendMessageW(hwnd, CB_GETLBTEXTLEN, i, 0)
        buf = ctypes.create_unicode_buffer(n + 1)
        _user32.SendMessageW(hwnd, CB_GETLBTEXT, i, buf)
        out.append(buf.value)
    return out


def combo_select(hwnd: int, index: int) -> bool:
    """CB_SETCURSEL + 补发 CBN_SELENDOK/CBN_SELCHANGE (SETCURSEL 不自发通知)。"""
    import win32gui

    _user32.SendMessageW(hwnd, CB_SETCURSEL, index, 0)
    ok = _user32.SendMessageW(hwnd, CB_GETCURSEL, 0, 0) == index
    parent = win32gui.GetParent(hwnd)
    ctrl_id = win32gui.GetDlgCtrlID(hwnd)
    for code in (CBN_SELENDOK, CBN_SELCHANGE):
        _user32.SendMessageW(parent, WM_COMMAND, (code << 16) | ctrl_id, hwnd)
    return ok


def notify_combo_edit(combo: int) -> None:
    """DROPDOWN 型 ComboBox 的子 Edit 改完后, 以 combo 名义补发编辑/失焦通知。"""
    import win32gui

    parent = win32gui.GetParent(combo)
    ctrl_id = win32gui.GetDlgCtrlID(combo)
    for code in (CBN_EDITCHANGE, CBN_KILLFOCUS):
        _user32.SendMessageW(parent, WM_COMMAND, (code << 16) | ctrl_id, combo)


def all_descendants(root: int) -> list[int]:
    """递归枚举窗口的全部后代 hwnd。"""
    import win32gui

    out: list[int] = []

    def walk(h: int):
        def cb(child, _):
            out.append(child)
            walk(child)
            return True

        try:
            win32gui.EnumChildWindows(h, cb, None)
        except Exception:
            pass

    walk(root)
    return out


def post_escape(hwnd: int, times: int = 4) -> None:
    """向窗口发 ESC 键 (唯一获准的退出手段, 严禁 WM_CLOSE)。"""
    for _ in range(times):
        _user32.PostMessageW(hwnd, WM_KEYDOWN, VK_ESCAPE, 0)
        _user32.PostMessageW(hwnd, WM_KEYUP, VK_ESCAPE, 0)


def type_to_command_line(hwnd: int, text: str) -> None:
    """向命令行 hwnd 打字 + 回车 — 与 file_ipc._type_dispatch_trigger 同机制。

    用于向等待点输入的命令 (CMDACTIVE=1) 喂坐标; 此状态下严禁走 IPC
    (dispatch 触发文本会被点提示吃掉)。"""
    for ch in text:
        _user32.PostMessageW(hwnd, WM_CHAR, ord(ch), 0)
    _user32.PostMessageW(hwnd, WM_CHAR, 0x0D, 0)


def find_acad_popups(pid: int) -> list[int]:
    """枚举指定进程的可见顶层 #32770 窗口。"""
    import win32gui
    import win32process

    out: list[int] = []

    def cb(h, _):
        if win32gui.IsWindowVisible(h) and win32gui.GetClassName(h) == "#32770":
            _, wp = win32process.GetWindowThreadProcessId(h)
            if wp == pid:
                out.append(h)
        return True

    win32gui.EnumWindows(cb, None)
    return out


# ---------------------------------------------------------------------------
# TGColumn 标准柱面板 (Handoff 36; 定位规则源自 36_tgcolumn_control_map.md)
# ---------------------------------------------------------------------------

# 真机枚举的材料下拉项 (2026-07-02, T20 V10); 运行时仍按实际条目匹配。
COLUMN_MATERIALS: tuple[str, ...] = ("金属", "钢筋砼", "混凝土", "石材", "毛石", "砖", "耐火砖")


def find_column_panel(pid: int, exclude: set[int] | None = None) -> int | None:
    """按结构指纹找 TGColumn 面板: 无标题 #32770 且含 title='柱高' #32770 子面板。"""
    import win32gui

    for h in find_acad_popups(pid):
        if exclude and h in exclude:
            continue
        try:
            if win32gui.GetWindowText(h) != "":
                continue
            for k in all_descendants(h):
                if (
                    win32gui.GetClassName(k) == "#32770"
                    and win32gui.GetWindowText(k) == "柱高"
                ):
                    return h
        except Exception:
            continue
    return None


def locate_column_controls(panel: int) -> dict[str, int]:
    """按语义锚点定位 TGColumn 关键控件 (hwnd 会话性, 每次重新发现)。

    返回键: height_edit / material_combo / rotation_combo / rotation_edit /
    section_w_edit / section_h_edit; 缺键 = 该控件未找到。"""
    import win32gui

    def _info(h: int):
        return (
            win32gui.GetClassName(h),
            win32gui.GetWindowText(h),
            win32gui.GetWindowRect(h),
            bool(win32gui.IsWindowVisible(h)),
        )

    def _y_overlap(a, b) -> bool:
        return a[1] < b[3] and b[1] < a[3]

    metas: dict[int, tuple] = {}
    for h in all_descendants(panel):
        try:
            metas[h] = _info(h)
        except Exception:
            continue

    anchors: dict[str, int] = {}
    for h, (cls, title, _rect, vis) in metas.items():
        if cls == "#32770" and title == "柱高":
            anchors["height_panel"] = h
        elif cls == "Static" and title == "材料：":
            anchors["material"] = h
        elif cls == "Static" and title == "转角：":
            anchors["rotation"] = h
        elif cls == "Button" and title == "横向" and vis:
            anchors["sec_w"] = h
        elif cls == "Button" and title == "纵向" and vis:
            anchors["sec_h"] = h

    found: dict[str, int] = {}
    if "height_panel" in anchors:
        for h in all_descendants(anchors["height_panel"]):
            if win32gui.GetClassName(h) == "Edit":
                found["height_edit"] = h
                break

    def _right_of(anchor_key: str, cls_want: str) -> int | None:
        if anchor_key not in anchors:
            return None
        arect = metas[anchors[anchor_key]][2]
        cands = []
        for h, (cls, _t, rect, vis) in metas.items():
            if cls != cls_want or not vis:
                continue
            if _y_overlap(arect, rect) and rect[0] >= arect[0]:
                cands.append((rect[0], h))
        return min(cands)[1] if cands else None

    if mat := _right_of("material", "ComboBox"):
        found["material_combo"] = mat
    if rot := _right_of("rotation", "ComboBox"):
        found["rotation_combo"] = rot
        for h in all_descendants(rot):
            if win32gui.GetClassName(h) == "Edit":
                found["rotation_edit"] = h
                break
    if sw := _right_of("sec_w", "Edit"):
        found["section_w_edit"] = sw
    if sh := _right_of("sec_h", "Edit"):
        found["section_h_edit"] = sh
    return found


async def drive_column_panel(
    pid: int,
    cmd_hwnd: int,
    point: tuple[float, float],
    *,
    height: float | None = None,
    material: str | None = None,
    rotation: float | None = None,
    sec_w: float | None = None,
    sec_h: float | None = None,
    exclude: set[int] | None = None,
    timeout: float = 5.0,
) -> str:
    """TGColumn 面板全链路驱动: 等面板 → 填参 → 打插入点 → ESC 退出。

    前提: 调用方已通过 vl-cmdf 启动 TGCOLUMN (CMDACTIVE=1, 面板浮起),
    且此后**不得走 IPC** 直到本函数返回。

    返回 "placed" 或失败原因:
      panel-not-found / control-missing:<keys> / set-failed:<field> /
      material-not-in-list:<items> / win32-unavailable / panel-still-open
    实体是否生成/参数是否命中由调用方经 IPC 读回判定。"""
    if not _win32_available():
        return "win32-unavailable"

    import win32gui

    loop = asyncio.get_event_loop()
    deadline = loop.time() + timeout
    panel = None
    while loop.time() < deadline:
        panel = find_column_panel(pid, exclude)
        if panel:
            break
        await asyncio.sleep(0.25)
    if not panel:
        return "panel-not-found"

    ctrls = locate_column_controls(panel)
    need = ["height_edit", "material_combo", "rotation_combo", "rotation_edit",
            "section_w_edit", "section_h_edit"]
    missing = [k for k in need if k not in ctrls]
    if missing:
        post_escape(panel)
        return f"control-missing:{','.join(missing)}"

    def _fmt(v: float) -> str:
        fv = float(v)
        return str(int(fv)) if fv == int(fv) else f"{fv:g}"

    for field, hwnd_key, value in (
        ("height", "height_edit", height),
        ("rotation", "rotation_edit", rotation),
        ("sec_w", "section_w_edit", sec_w),
        ("sec_h", "section_h_edit", sec_h),
    ):
        if value is None:
            continue
        if not set_edit_text(ctrls[hwnd_key], _fmt(value)):
            post_escape(panel)
            post_escape(cmd_hwnd)
            return f"set-failed:{field}"
        if field == "rotation":
            notify_combo_edit(ctrls["rotation_combo"])

    if material is not None:
        items = combo_items(ctrls["material_combo"])
        if material not in items:
            post_escape(panel)
            post_escape(cmd_hwnd)
            return f"material-not-in-list:{items}"
        if not combo_select(ctrls["material_combo"], items.index(material)):
            post_escape(panel)
            post_escape(cmd_hwnd)
            return "set-failed:material"

    type_to_command_line(cmd_hwnd, f"{_fmt(point[0])},{_fmt(point[1])}")
    await asyncio.sleep(1.5)

    # ESC 退出放置循环, 面板随之关闭
    post_escape(cmd_hwnd)
    await asyncio.sleep(0.5)
    post_escape(panel, 2)
    deadline = loop.time() + 4.0
    while loop.time() < deadline:
        if not (win32gui.IsWindow(panel) and win32gui.IsWindowVisible(panel)):
            return "placed"
        await asyncio.sleep(0.2)
    return "panel-still-open"
