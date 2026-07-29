"""Win32 对话框/面板自动化 — 白名单 + 受控原语。

适用场景:
  1. TGColumn 标准柱面板 (Handoff 36, itest_39 真机验证): 无标题 #32770
     浮动面板, owner 不被 disable, 无 确定/取消 按钮 — 参数即时生效,
     落地靠向命令行打插入点坐标, 退出靠 ESC。控件按「class + 标签锚点」
     每次运行时重新发现 (hwnd 会话性), 定位规则见
     docs/handoff/36_tgcolumn_control_map.md。
  2. TOpening 门窗参数面板 (Handoff 39, itest_42 真机验证): 标题精确为
     「门窗参数」, 底部标准 ToolbarWindow32 的模式按钮可用受控鼠标消息
     切换。按钮会话性且切换时面板可能重建, 所以每次运行重新发现。
     TOpening 的默认提示是「<退出>」, 必须用空回车结束; ESC 会继续/重启
     放置循环, 不能作为该面板的正常退出路径。

安全边界 (PROJECT_RULES.md 铁律):
  * 只对白名单面板动手: TGColumn 使用结构指纹精确匹配, TOpening 使用
    标题 + ToolbarWindow32 强结构指纹;
  * 标准 Button 只用 BM_CLICK, 工具栏只发受控鼠标消息; **严禁 WM_CLOSE**
    (真机曾致 AutoCAD 致命错误);
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
WM_LBUTTONDOWN = 0x0201
WM_LBUTTONUP = 0x0202
MK_LBUTTON = 0x0001
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
TB_BUTTONCOUNT = 0x0418


def _win32_available() -> bool:
    if sys.platform != "win32":
        return False
    try:
        import win32gui  # noqa: F401

        return True
    except ImportError:
        return False


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
# TOpening 门窗参数面板 (Handoff 39; itest_42 真机验证)
# ---------------------------------------------------------------------------

OPENING_PANEL_TITLE = "门窗参数"
OPENING_TOOLBAR_ID = 134
OPENING_TOOLBAR_BUTTON_COUNT = 24
OPENING_TOOLBAR_SIZE = (636, 27)
OPENING_TOOLBAR_SIZE_TOLERANCE = (8, 4)

# T20 V10 的标准工具栏布局:
#   14 x 23px 插入方式 + 2 x 8px separator + 23px 插门 + 23px 插窗。
# 坐标是 ToolbarWindow32 客户区坐标, 不依赖面板屏幕位置。
OPENING_MODE_POINTS: dict[str, tuple[int, int]] = {
    "door": (349, 12),
    "window": (372, 12),
}


def find_opening_panel(pid: int, exclude: set[int] | None = None) -> int | None:
    """按标题白名单找 TOpening「门窗参数」面板。"""
    import win32gui

    for h in find_acad_popups(pid):
        if exclude and h in exclude:
            continue
        try:
            if win32gui.GetWindowText(h) == OPENING_PANEL_TITLE:
                return h
        except Exception:
            continue
    return None


def locate_opening_toolbar(panel: int) -> int | None:
    """按强结构指纹定位门窗模式工具栏, 避免误点其它 #32770。

    指纹 = 标题「门窗参数」+ 唯一可见 ToolbarWindow32 +
    control id 134 + 24 个按钮 + T20 V10 已验证尺寸。
    """
    import win32gui

    try:
        if (
            win32gui.GetClassName(panel) != "#32770"
            or win32gui.GetWindowText(panel) != OPENING_PANEL_TITLE
        ):
            return None
    except Exception:
        return None

    candidates: list[int] = []
    for h in all_descendants(panel):
        try:
            if (
                win32gui.GetClassName(h) == "ToolbarWindow32"
                and win32gui.IsWindowVisible(h)
                and win32gui.GetDlgCtrlID(h) == OPENING_TOOLBAR_ID
            ):
                candidates.append(h)
        except Exception:
            continue
    if len(candidates) != 1:
        return None

    toolbar = candidates[0]
    try:
        left, top, right, bottom = win32gui.GetWindowRect(toolbar)
        button_count = _user32.SendMessageW(toolbar, TB_BUTTONCOUNT, 0, 0)
    except Exception:
        return None
    width = right - left
    height = bottom - top
    expected_width, expected_height = OPENING_TOOLBAR_SIZE
    width_tolerance, height_tolerance = OPENING_TOOLBAR_SIZE_TOLERANCE
    if (
        button_count != OPENING_TOOLBAR_BUTTON_COUNT
        or abs(width - expected_width) > width_tolerance
        or abs(height - expected_height) > height_tolerance
    ):
        return None
    return toolbar


def click_opening_mode(panel: int, mode: str) -> str:
    """向门窗工具栏的「插门/插窗」按钮发送受控鼠标消息。

    标准 ToolbarWindow32 的按钮不是独立 HWND, 因此 BM_CLICK 不适用。
    这里只向已通过强结构指纹的工具栏客户区发送 down/up; 不移动真实鼠标。
    """
    point = OPENING_MODE_POINTS.get(mode)
    if point is None:
        return f"unsupported-mode:{mode}"
    toolbar = locate_opening_toolbar(panel)
    if toolbar is None:
        return "toolbar-not-found"

    x, y = point
    lparam = (y << 16) | (x & 0xFFFF)
    down_posted = _user32.PostMessageW(toolbar, WM_LBUTTONDOWN, MK_LBUTTON, lparam)
    up_posted = _user32.PostMessageW(toolbar, WM_LBUTTONUP, 0, lparam)
    return "mode-clicked" if down_posted and up_posted else "mode-click-failed"


async def drive_opening_mode(
    pid: int,
    cmd_hwnd: int,
    mode: str,
    *,
    exclude: set[int] | None = None,
    timeout: float = 5.0,
) -> str:
    """等待 TOpening 面板 → 切门/窗模式 → 空回车退出放置循环。

    前提: 调用方已通过独立 LISP 启动 TOpening, 且 CMDACTIVE=1。此函数
    返回前不走 IPC。最终模式是否生效仍由 opening.lsp 的 DXF group71
    门禁判定, 本函数只负责可回滚的 UI 切换。
    """
    if not _win32_available():
        return "win32-unavailable"
    if mode not in OPENING_MODE_POINTS:
        return f"unsupported-mode:{mode}"

    loop = asyncio.get_event_loop()

    async def _exit_placing_loop() -> bool:
        # 默认提示是「<退出>」, 空回车比 ESC 更确定且不会重启 TOpening。
        for _ in range(2):
            type_to_command_line(cmd_hwnd, "")
            deadline_close = loop.time() + 2.0
            while loop.time() < deadline_close:
                if find_opening_panel(pid) is None:
                    return True
                await asyncio.sleep(0.1)
        return find_opening_panel(pid) is None

    deadline = loop.time() + timeout
    panel = None
    while loop.time() < deadline:
        panel = find_opening_panel(pid, exclude)
        if panel:
            break
        await asyncio.sleep(0.1)
    if not panel:
        # 调用契约保证 TOpening 已 active；面板未出现时仍用默认空回车收尾，
        # 防止把无界的活动命令留给下一次 dispatcher 请求。
        type_to_command_line(cmd_hwnd, "")
        await asyncio.sleep(0.3)
        return "panel-not-found"

    clicked = click_opening_mode(panel, mode)
    if clicked != "mode-clicked":
        closed = await _exit_placing_loop()
        return clicked if closed else f"{clicked};panel-still-open"

    # 切换到另一模式时面板会重建; 同模式时原 HWND 保持。两种情况都需
    # 等消息落地后再向命令行发送默认「退出」的空回车。
    await asyncio.sleep(0.6)
    return "mode-selected" if await _exit_placing_loop() else "panel-still-open"


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
                if win32gui.GetClassName(k) == "#32770" and win32gui.GetWindowText(k) == "柱高":
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
    need = [
        "height_edit",
        "material_combo",
        "rotation_combo",
        "rotation_edit",
        "section_w_edit",
        "section_h_edit",
    ]
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
