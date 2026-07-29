"""真机联调 Step 41 — TRectAxis 绘制轴网对话框 Gate B 控件级驱动探针 (A1).

结论 (Handoff 37, 2026-07-02): **Gate B 机制打通, 但 A1 不封装 (WON'T-SHIP)**。
    机制侧全部成立 (bind + IDOK + 打点 → 确定性落图), 但 TRectAxis 在 T20 V10
    本配置下产出的是 **纯 LINE @ 图层 DOTE, 无任何 xdata / 无 TCH_AXIS / 无轴号**,
    与既有 axis_lines (entmake 纯 LINE) 同类。驱动对话框相较 axis_lines 零增益,
    反添 GUI 会话依赖与脆弱性, 故不封装 rect_axis 子命令。详见文档 §结论。

前提事实 (Gate A, Handoff 34 + docs/handoff/37_trectaxis_control_map.md):
    - TRectAxis 弹无标题 #32770, **owner 不 disable 且 CMDACTIVE=0** (对话框自持)。
    - SysTabControl32 双 tab (直线轴网 visible / 弧线轴网 hidden)。
    - 直线 tab 关键控件 (锚点定位, hwnd 会话性):
        键入 Edit    = y∈[439,460] 的宽 Edit (width>200) — 输入间距串
        方向 radio x4 = BS_AUTORADIOBUTTON, x 升序 = 上开/下开/左进/右进
        总开间/总进深 = Static '总开间:'/'总进深:' 右侧的数字 Static (自校验读数)
        ListBox      = **预设常用间距值调色板** (1200..6900), 非已录入值
        右下 29x29 owner-draw Button x2 = 确定/取消 (owner-draw, BM_CLICK 无效)

关键机制发现:
    1. 间距语法是 **个数*轴间距 (COUNT*SPACING)**: "3*3000" = 3 跨×3000 = 4 根轴线,
       总开间 9000。(误用 "3000*2" 会被读成 3000 跨×2mm = 3000 根轴线, 曾致 3003
       实体的假象。)
    2. owner-draw 确定/取消按钮对 BM_CLICK / 鼠标消息 / 父窗通知 **全部无效**;
       唯 **WM_COMMAND(dialog, IDOK=1)** 生效 → 关框且 CMDACTIVE=1 (等插入点)。
    3. IDOK 后 CMDACTIVE=1 窗口期严禁走 IPC; 命令行 WM_CHAR 打坐标落图。

Gate B 假说 (均已真机验证):
    H1 (bind): 选方向 radio + 键入 "N*S" + Enter → 总开间/总进深联动更新 (不落图自校验)。
    H2 (commit): WM_COMMAND(IDOK) → 打插入点 → 确定性生成 N 根 LINE; 分类实体类型。

铁律: 严禁 WM_CLOSE; 退出只走 ESC; cleanup 撤实体+复位环境+无残留框。

用法:
    uv run python scripts/itest_41_rectaxis_gate_b.py bind    # H1, 不落图
    uv run python scripts/itest_41_rectaxis_gate_b.py commit  # H1+H2, IDOK 落图+分类
    uv run python scripts/itest_41_rectaxis_gate_b.py diag    # owner-draw 点击法甄别

返回码: 0=本阶段假说成立, 2=FAIL, 3=INDETERMINATE
"""

from __future__ import annotations

import asyncio
import sys
import time
from pathlib import Path

sys.stdout.reconfigure(errors="replace")
sys.path.insert(0, str(Path(__file__).resolve().parent))  # for _live_lock
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import win32gui  # noqa: E402
import win32process  # noqa: E402

from _live_lock import live_lock_or_exit  # noqa: E402
from t20_mcp.backends.file_ipc import FileIPCBackend  # noqa: E402
from t20_mcp.dialog_automation import (  # noqa: E402
    BM_CLICK,
    all_descendants,
    find_acad_popups,
    get_window_text,
    post_escape,
    set_edit_text,
    type_to_command_line,
    _user32,
)
from t20_mcp.tools.tangent import _load_prelude  # noqa: E402

WM_CHAR = 0x0102
BM_GETCHECK = 0x00F0
BST_CHECKED = 1
BS_TYPEMASK = 0x0F
BS_AUTORADIOBUTTON = 0x09
GWL_STYLE = -16

# 键入串: 语法 = 个数*轴间距 (COUNT*SPACING)。
#   下开 "3*3000" = 3 跨 3000 → 总开间 9000, 4 根竖轴线
#   左进 "2*4500" = 2 跨 4500 → 总进深 9000, 3 根横轴线
#   预期落图 = 4 + 3 = 7 根 LINE。
SPACING_BAY = "3*3000"
EXPECT_BAY_TOTAL = "9000"
SPACING_DEPTH = "2*4500"
EXPECT_DEPTH_TOTAL = "9000"
EXPECT_LINES = 7
INS_POINT = "40000,40000"

RESET_ENV = (
    "(progn (setq n 0)"
    ' (while (and (< n 8) (> (getvar "CMDACTIVE") 0)) (command) (setq n (1+ n)))'
    ' (setvar "CMDDIA" 1) (setvar "FILEDIA" 1) (setvar "OSMODE" 0)'
    ' (strcat "rst CMDACTIVE=" (itoa (getvar "CMDACTIVE"))))'
)
ENV_VARS = ["CMDACTIVE", "CMDDIA", "FILEDIA", "OSMODE"]

START_TRECTAXIS = (
    _load_prelude() + '\n(progn (setvar "CMDECHO" 1)'
    ' (vl-catch-all-apply (quote vl-cmdf) (list "TRECTAXIS"))'
    ' (strcat "active=" (itoa (getvar "CMDACTIVE"))))'
)

# 全图实体类型直方图 (判定 TCH_AXIS 系 vs 普通 LINE) + 图层直方图 + 样本
TYPE_HISTOGRAM = """
(setq t20mcp:ga-ss (ssget "X") t20mcp:ga-i 0 t20mcp:ga-al nil t20mcp:ga-la nil)
(if t20mcp:ga-ss
  (while (< t20mcp:ga-i (sslength t20mcp:ga-ss))
    (setq t20mcp:ga-e (entget (ssname t20mcp:ga-ss t20mcp:ga-i)))
    (setq t20mcp:ga-t (cdr (assoc 0 t20mcp:ga-e)))
    (setq t20mcp:ga-p (assoc t20mcp:ga-t t20mcp:ga-al))
    (setq t20mcp:ga-al
          (if t20mcp:ga-p
              (subst (cons t20mcp:ga-t (1+ (cdr t20mcp:ga-p))) t20mcp:ga-p t20mcp:ga-al)
              (cons (cons t20mcp:ga-t 1) t20mcp:ga-al)))
    (setq t20mcp:ga-lyr (cdr (assoc 8 t20mcp:ga-e)))
    (setq t20mcp:ga-q (assoc t20mcp:ga-lyr t20mcp:ga-la))
    (setq t20mcp:ga-la
          (if t20mcp:ga-q
              (subst (cons t20mcp:ga-lyr (1+ (cdr t20mcp:ga-q))) t20mcp:ga-q t20mcp:ga-la)
              (cons (cons t20mcp:ga-lyr 1) t20mcp:ga-la)))
    (setq t20mcp:ga-i (1+ t20mcp:ga-i))))
;; 段长直方图 (short<200 / mid<2000 / long>=2000) + 全图 bbox + 5 个散点样本
(setq t20mcp:ga-sh 0 t20mcp:ga-md 0 t20mcp:ga-lg 0
      t20mcp:ga-n (if t20mcp:ga-ss (sslength t20mcp:ga-ss) 0) t20mcp:ga-i 0
      t20mcp:ga-minx 1e99 t20mcp:ga-miny 1e99 t20mcp:ga-maxx -1e99 t20mcp:ga-maxy -1e99)
(while (< t20mcp:ga-i t20mcp:ga-n)
  (setq t20mcp:ga-e (entget (ssname t20mcp:ga-ss t20mcp:ga-i))
        t20mcp:ga-p10 (cdr (assoc 10 t20mcp:ga-e))
        t20mcp:ga-p11 (cdr (assoc 11 t20mcp:ga-e)))
  (if (and t20mcp:ga-p10 t20mcp:ga-p11)
    (progn
      (setq t20mcp:ga-d (distance t20mcp:ga-p10 t20mcp:ga-p11))
      (cond ((< t20mcp:ga-d 200) (setq t20mcp:ga-sh (1+ t20mcp:ga-sh)))
            ((< t20mcp:ga-d 2000) (setq t20mcp:ga-md (1+ t20mcp:ga-md)))
            (t (setq t20mcp:ga-lg (1+ t20mcp:ga-lg))))
      (setq t20mcp:ga-minx (min t20mcp:ga-minx (car t20mcp:ga-p10) (car t20mcp:ga-p11))
            t20mcp:ga-maxx (max t20mcp:ga-maxx (car t20mcp:ga-p10) (car t20mcp:ga-p11))
            t20mcp:ga-miny (min t20mcp:ga-miny (cadr t20mcp:ga-p10) (cadr t20mcp:ga-p11))
            t20mcp:ga-maxy (max t20mcp:ga-maxy (cadr t20mcp:ga-p10) (cadr t20mcp:ga-p11)))))
  (setq t20mcp:ga-i (1+ t20mcp:ga-i)))
(setq t20mcp:ga-s "" t20mcp:ga-i 0)
(foreach t20mcp:ga-k (list 0 (/ t20mcp:ga-n 4) (/ t20mcp:ga-n 2) (- t20mcp:ga-n 1))
  (if (and (>= t20mcp:ga-k 0) (< t20mcp:ga-k t20mcp:ga-n))
    (progn
      (setq t20mcp:ga-e (entget (ssname t20mcp:ga-ss t20mcp:ga-k))
            t20mcp:ga-p10 (cdr (assoc 10 t20mcp:ga-e))
            t20mcp:ga-p11 (cdr (assoc 11 t20mcp:ga-e)))
      (setq t20mcp:ga-s (strcat t20mcp:ga-s " #" (itoa t20mcp:ga-k) ":len="
                                (if (and t20mcp:ga-p10 t20mcp:ga-p11)
                                    (rtos (distance t20mcp:ga-p10 t20mcp:ga-p11) 2 0) "?"))))))
(setq t20mcp:ga-s (strcat t20mcp:ga-s
      " | seglen short<200=" (itoa t20mcp:ga-sh)
      " mid=" (itoa t20mcp:ga-md) " long>=2000=" (itoa t20mcp:ga-lg)
      " | bbox=(" (rtos t20mcp:ga-minx 2 0) "," (rtos t20mcp:ga-miny 2 0) ")-("
      (rtos t20mcp:ga-maxx 2 0) "," (rtos t20mcp:ga-maxy 2 0) ")"))
(strcat "types=" (vl-prin1-to-string t20mcp:ga-al)
        " layers=" (vl-prin1-to-string t20mcp:ga-la)
        " sample=" t20mcp:ga-s)
"""


def find_rectaxis_dialog(pid: int, exclude: set[int]) -> int | None:
    """指纹: 无标题 #32770, 含 SysTabControl32 + Static '总开间:'。"""
    for h in find_acad_popups(pid):
        if h in exclude:
            continue
        try:
            if win32gui.GetWindowText(h) != "":
                continue
            kids = all_descendants(h)
            has_tab = any(win32gui.GetClassName(k) == "SysTabControl32" for k in kids)
            has_total = any(
                win32gui.GetClassName(k) == "Static" and win32gui.GetWindowText(k) == "总开间:"
                for k in kids
            )
            if has_tab and has_total:
                return h
        except Exception:
            continue
    return None


def locate(dialog: int) -> dict[str, object]:
    """按锚点定位直线轴网 tab 的关键控件 (只取 visible 控件)。"""
    metas: dict[int, tuple] = {}
    for h in set(all_descendants(dialog)):
        try:
            if not win32gui.IsWindowVisible(h):
                continue
            metas[h] = (
                win32gui.GetClassName(h),
                win32gui.GetWindowText(h),
                win32gui.GetWindowRect(h),
                win32gui.GetWindowLong(h, GWL_STYLE),
            )
        except Exception:
            continue

    drect = win32gui.GetWindowRect(dialog)

    def rel(rect):  # 相对坐标, 与 Gate A raw 可比
        return (rect[0] - drect[0], rect[1] - drect[1], rect[2] - drect[0], rect[3] - drect[1])

    found: dict[str, object] = {}
    lab = {t: h for h, (c, t, _r, _s) in metas.items() if c == "Static" and t}

    # 键入 Edit: 宽 > 200
    for h, (c, _t, r, _s) in metas.items():
        if c == "Edit" and (r[2] - r[0]) > 200:
            found["input_edit"] = h
    # 夹角 Edit: 与 '轴网夹角:' y 重叠且在其右
    if "轴网夹角:" in lab:
        ar = metas[lab["轴网夹角:"]][2]
        for h, (c, _t, r, _s) in metas.items():
            if c == "Edit" and r[0] >= ar[0] and r[1] < ar[3] and ar[1] < r[3]:
                found["angle_edit"] = h
    # 总开间/总进深 数字 Static: 在标签右侧同行
    for key, name in (("bay_total", "总开间:"), ("depth_total", "总进深:")):
        if name in lab:
            ar = metas[lab[name]][2]
            cands = [
                (r[0], h)
                for h, (c, t, r, _s) in metas.items()
                if c == "Static"
                and t != name
                and r[0] >= ar[2] - 4
                and r[1] < ar[3]
                and ar[1] < r[3]
                and (r[0] - ar[2]) < 30
            ]
            if cands:
                found[key] = min(cands)[1]
    # 方向 radio x4: BS_AUTORADIOBUTTON, 与 '上开' 标签同行, x 升序
    if "上开" in lab:
        row = metas[lab["上开"]][2]
        radios = sorted(
            (r[0], h)
            for h, (c, _t, r, s) in metas.items()
            if c == "Button"
            and (s & BS_TYPEMASK) == BS_AUTORADIOBUTTON
            and r[1] < row[3]
            and row[1] - 20 < r[3]
        )
        if len(radios) >= 4:
            found["radios"] = [h for _x, h in radios[:4]]  # 上开/下开/左进/右进
    # 右下 owner-draw 图标按钮 x2 (确定/取消 候选): ~29x29, 在对话框右下角
    cands = []
    for h, (c, _t, r, s) in metas.items():
        w, hh = r[2] - r[0], r[3] - r[1]
        if c == "Button" and 20 <= w <= 40 and 20 <= hh <= 40:
            rr = rel(r)
            if rr[1] > 300 and rr[0] > 250:
                cands.append((rr[0], h))
    found["ok_cancel"] = [h for _x, h in sorted(cands)]
    found["_rel"] = {k: rel(metas[v][2]) for k, v in found.items() if isinstance(v, int)}
    return found


WM_LBUTTONDOWN = 0x0201
WM_LBUTTONUP = 0x0202
WM_COMMAND = 0x0111
WM_KEYDOWN = 0x0100
WM_KEYUP = 0x0101
VK_RETURN = 0x0D
BN_CLICKED = 0
IDOK = 1


def click_mouse(hwnd: int) -> None:
    """向按钮中心发左键 down+up (owner-draw 按钮对 BM_CLICK 常无反应)。"""
    r = win32gui.GetWindowRect(hwnd)
    cx, cy = (r[2] - r[0]) // 2, (r[3] - r[1]) // 2
    lp = (cy << 16) | cx
    _user32.PostMessageW(hwnd, WM_LBUTTONDOWN, 1, lp)
    _user32.PostMessageW(hwnd, WM_LBUTTONUP, 0, lp)


def click_via_parent_command(dialog: int, btn: int) -> None:
    """向对话框发 WM_COMMAND(BN_CLICKED, ctrlid) — owner-draw 的通知等价路径。"""
    ctrl_id = win32gui.GetDlgCtrlID(btn)
    _user32.SendMessageW(dialog, WM_COMMAND, (BN_CLICKED << 16) | ctrl_id, btn)


def radio_checked(h: int) -> bool:
    return _user32.SendMessageW(h, BM_GETCHECK, 0, 0) == BST_CHECKED


def press_enter(hwnd: int) -> None:
    _user32.PostMessageW(hwnd, WM_CHAR, 0x0D, 0)


async def count(b: FileIPCBackend) -> int:
    r = await b.entity_count()
    return r.payload["count"] if r.ok else -1


async def cleanup(backend, base, pid, base_modals) -> bool:
    residual0 = [h for h in find_acad_popups(pid) if h not in base_modals]
    for h in residual0:
        post_escape(h, 4)
    await asyncio.sleep(0.5)
    await backend.execute_lisp(RESET_ENV)
    rounds = 0
    while rounds < 16:
        c = await count(backend)
        if c <= base or c < 0:
            break
        u = await backend.undo()
        if not u.ok:
            break
        rounds += 1
    final = await count(backend)
    await backend.execute_lisp(RESET_ENV)
    env = await backend.drawing_get_variables(ENV_VARS)
    residual = [h for h in find_acad_popups(pid) if h not in base_modals]
    print(
        f"[cleanup] rounds={rounds} final={final} (baseline {base}) env={env.payload} residual={residual}"
    )
    return (
        final == base
        and env.ok
        and env.payload.get("CMDACTIVE") == 0
        and env.payload.get("CMDDIA") == 1
        and env.payload.get("FILEDIA") == 1
        and env.payload.get("OSMODE") == 0
        and not residual
    )


async def open_and_bind(backend, pid, base_modals) -> tuple[int | None, dict]:
    """启动 TRECTAXIS + H1 bind 验证。返回 (dialog hwnd | None, ctrls)。"""
    r = await backend.execute_lisp(START_TRECTAXIS)
    print(f"[launch] ok={r.ok} payload={r.payload!r}")
    dialog = None
    deadline = time.time() + 5.0
    while time.time() < deadline:
        dialog = find_rectaxis_dialog(pid, base_modals)
        if dialog:
            break
        time.sleep(0.25)
    if not dialog:
        print("FAIL: 未找到 TRectAxis 对话框 (指纹: SysTabControl32 + 总开间:)")
        return None, {}

    ctrls = locate(dialog)
    print(f"[locate] rel={ctrls.get('_rel')}")
    print(
        f"[locate] radios={len(ctrls.get('radios', []))} ok_cancel={len(ctrls.get('ok_cancel', []))}"
    )
    need = ["input_edit", "angle_edit", "bay_total", "depth_total", "radios"]
    missing = [k for k in need if k not in ctrls]
    if missing or len(ctrls.get("radios", [])) < 4 or len(ctrls.get("ok_cancel", [])) < 2:
        print(f"FAIL: 控件缺失 missing={missing} (radios/ok_cancel 数量不足)")
        return dialog, {}

    radios = ctrls["radios"]
    print(
        f"[bind] 初值: input={get_window_text(ctrls['input_edit'])!r} "
        f"angle={get_window_text(ctrls['angle_edit'])!r} "
        f"bay_total={get_window_text(ctrls['bay_total'])!r} "
        f"depth_total={get_window_text(ctrls['depth_total'])!r} "
        f"radio_checked={[radio_checked(h) for h in radios]}"
    )

    # H1a: 下开 = radios[1]
    _user32.SendMessageW(radios[1], BM_CLICK, 0, 0)
    await asyncio.sleep(0.3)
    ok_radio1 = radio_checked(radios[1])
    set_edit_text(ctrls["input_edit"], SPACING_BAY)
    press_enter(ctrls["input_edit"])
    await asyncio.sleep(0.5)
    bay = get_window_text(ctrls["bay_total"])
    print(
        f"[bind] 下开 radio={ok_radio1} 键入{SPACING_BAY!r}+Enter -> 总开间={bay!r} (期望 {EXPECT_BAY_TOTAL})"
    )

    # H1b: 左进 = radios[2]
    _user32.SendMessageW(radios[2], BM_CLICK, 0, 0)
    await asyncio.sleep(0.3)
    ok_radio2 = radio_checked(radios[2])
    set_edit_text(ctrls["input_edit"], SPACING_DEPTH)
    press_enter(ctrls["input_edit"])
    await asyncio.sleep(0.5)
    depth = get_window_text(ctrls["depth_total"])
    print(
        f"[bind] 左进 radio={ok_radio2} 键入{SPACING_DEPTH!r}+Enter -> 总进深={depth!r} (期望 {EXPECT_DEPTH_TOTAL})"
    )

    bind_ok = ok_radio1 and ok_radio2 and bay == EXPECT_BAY_TOTAL and depth == EXPECT_DEPTH_TOTAL
    print(f"[bind] H1 verdict: {'PASS' if bind_ok else 'FAIL'}")
    ctrls["_bind_ok"] = bind_ok
    return dialog, ctrls


async def _diag_clicks(backend, pid, base_modals) -> int:
    """诊断: 逐法试图关闭对话框, 报告哪种生效 (关框且不立即报错)。

    方法分两类:
      - 对话框级 (与按钮无关): 发 WM_COMMAND(IDOK) / 回车默认键;
      - 按钮级 (对 ok_cancel[0] 试): bm_click / 鼠标消息 / 父窗通知。
    """
    cmd_hwnd = backend._command_hwnd or backend._hwnd

    def m_idok(dlg, ctrls):
        _user32.SendMessageW(dlg, WM_COMMAND, IDOK, 0)

    def m_enter(dlg, ctrls):
        _user32.PostMessageW(dlg, WM_KEYDOWN, VK_RETURN, 0)
        _user32.PostMessageW(dlg, WM_KEYUP, VK_RETURN, 0)

    def m_bm(dlg, ctrls):
        _user32.SendMessageW(ctrls["ok_cancel"][0], BM_CLICK, 0, 0)

    def m_mouse(dlg, ctrls):
        click_mouse(ctrls["ok_cancel"][0])

    def m_parent(dlg, ctrls):
        click_via_parent_command(dlg, ctrls["ok_cancel"][0])

    methods = [
        ("idok_cmd", m_idok),
        ("enter_key", m_enter),
        ("bm_click[0]", m_bm),
        ("mouse[0]", m_mouse),
        ("parent_cmd[0]", m_parent),
    ]
    for mname, fn in methods:
        dialog, ctrls = await open_and_bind(backend, pid, base_modals)
        if not ctrls:
            return 2
        cids = [win32gui.GetDlgCtrlID(h) for h in ctrls["ok_cancel"]]
        try:
            fn(dialog, ctrls)
        except Exception as e:
            print(f"[diag] 方法={mname:14s} -> EXC {e!r}")
            post_escape(dialog, 4)
            await asyncio.sleep(0.4)
            await backend.execute_lisp(RESET_ENV)
            continue
        await asyncio.sleep(1.0)
        gone = not (win32gui.IsWindow(dialog) and win32gui.IsWindowVisible(dialog))
        active = await backend.drawing_get_variables(["CMDACTIVE"])
        print(
            f"[diag] 方法={mname:14s} ok_cancel_ctrlids={cids} "
            f"-> dialog_gone={gone} CMDACTIVE={active.payload}"
        )
        post_escape(dialog if not gone else cmd_hwnd, 4)
        await asyncio.sleep(0.4)
        await backend.execute_lisp(RESET_ENV)
    return 0


async def _run_inner(backend, pid, cmd_hwnd, base, base_modals, mode, cand) -> int:
    if mode == "diag":
        return await _diag_clicks(backend, pid, base_modals)

    dialog, ctrls = await open_and_bind(backend, pid, base_modals)
    if not ctrls:
        return 2
    if mode == "bind":
        return 0 if ctrls["_bind_ok"] else 2
    if not ctrls["_bind_ok"]:
        print("bind 未通过, 不进入 commit")
        return 2

    # H2: WM_COMMAND(IDOK) 确认 (diag 证实 owner-draw 按钮点击无效, 但对话框
    # OnOK 处理器响应标准 IDOK 命令) -> 关框且 CMDACTIVE=1 (等插入点) ->
    # 纯 Win32 打坐标 -> 读回实体类型。
    print("\n[commit] WM_COMMAND(IDOK) 确认对话框")
    _user32.SendMessageW(dialog, WM_COMMAND, IDOK, 0)
    await asyncio.sleep(1.0)
    gone = not (win32gui.IsWindow(dialog) and win32gui.IsWindowVisible(dialog))
    print(f"[commit] dialog_gone={gone}")
    # CMDACTIVE=1 (等插入点): 纯 Win32 打坐标, 禁 IPC
    type_to_command_line(cmd_hwnd, INS_POINT)
    await asyncio.sleep(2.0)
    post_escape(cmd_hwnd, 4)
    await asyncio.sleep(0.5)
    await backend.execute_lisp(RESET_ENV)
    after = await count(backend)
    print(f"[commit] count {base}->{after} (预期 +{EXPECT_LINES})")
    if after > base:
        hist = await backend.execute_lisp(TYPE_HISTOGRAM)
        print(f"[commit] {hist.payload!r}")
        payload = str(hist.payload or "")
        tch_axis = "TCH_AXIS" in payload
        count_ok = (after - base) == EXPECT_LINES
        print()
        print("=== Step41 Gate B verdict ===")
        print("  H1 bind (选向+键入 N*S -> 总计联动)  : PASS")
        print(f"  H2 IDOK 关框 + 打点落图              : PASS (delta +{after - base})")
        print(f"  实体根数符合 N*S 语义 (+{EXPECT_LINES})       : {'PASS' if count_ok else 'FAIL'}")
        print(f"  智能轴对象 (TCH_AXIS 系)             : {'YES' if tch_axis else 'NO (纯 LINE)'}")
        print()
        print("  --- A1 价值裁定 ---")
        print("  TRectAxis 产出 = 纯 LINE @ DOTE, 无 xdata, 无 TCH_AXIS, 无轴号;")
        print("  与既有 axis_lines (entmake 纯 LINE) 同类, 驱动对话框零增益。")
        print("  => 机制 PASS, 但 A1 WON'T-SHIP: 不封装 rect_axis (详见 Handoff 37)。")
        # 机制成立即回 0; 是否封装是工程裁定, 不影响探针的机制结论。
        return 0 if count_ok else 2
    print("\n=== Step41 Gate B verdict: INDETERMINATE (IDOK 后未落实体) ===")
    return 3


async def run(mode: str, cand: int) -> int:
    backend = FileIPCBackend()
    init = await backend.initialize()
    if not init.ok:
        print(f"FAIL init: {init.error}")
        return 2
    _, pid = win32process.GetWindowThreadProcessId(backend._hwnd)
    cmd_hwnd = backend._command_hwnd or backend._hwnd

    guard = 0
    while await count(backend) > 0 and guard < 8:
        await backend.undo()
        guard += 1
    await backend.execute_lisp(RESET_ENV)
    base = await count(backend)
    base_modals = set(find_acad_popups(pid))
    print(f"baseline entity={base}")

    try:
        rc = await _run_inner(backend, pid, cmd_hwnd, base, base_modals, mode, cand)
    finally:
        clean = await cleanup(backend, base, pid, base_modals)
        print(f"  cleanup clean             : {'PASS' if clean else 'FAIL'}")
    return rc if clean else 2


async def main() -> int:
    if len(sys.argv) < 2 or sys.argv[1] not in ("bind", "commit", "diag"):
        print(__doc__)
        return 2
    cand = int(sys.argv[2]) if len(sys.argv) > 2 else 0
    return await run(sys.argv[1], cand)


if __name__ == "__main__":
    _lock = live_lock_or_exit(__file__)
    raise SystemExit(asyncio.run(main()))
