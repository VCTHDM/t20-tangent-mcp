"""真机联调 Step 37 — TRectAxis / 矩形轴网面板 #32770 Gate A inventory.

目标 (TODO_BACKLOG §C1 / Gate A inventory-only):
    捕获 TRectAxis 弹出的 #32770 矩形轴网面板的窗口结构 (class / title /
    styles / enabled state / 子控件树), 为后续 A1 (TRectAxis Gate B 矩形轴网封装)
    提供事实证据。

Gate A 规则 (硬性, 与 itest_36 TGColumn 完全一致):
    - 仅注册确认 + baseline window/entity 抓取 + 启动命令 + 窗口树抓取 + ESC 恢复;
    - 不点击, 不填文本框, 不在绘图区点点, 不改 dialog_automation.py;
    - 不把 clean exit 当成功;
    - 任何点击 / 键盘文字 / 模拟回车 / WM_CLOSE 都禁止。

复测目标:
    1. TRectAxis 弹 #32770 (复现 docs/T20_COMMANDS.md §1.2 第 22 行结论);
    2. 抓取面板顶层窗口 + 直系子窗口 (class, title, styles, enabled, rect);
    3. 抓 owner / parent disabled 状态 (确认 modal-ness);
    4. ESC 关闭, 环境断言 CMDACTIVE=0, 主窗口重新可用;
    5. entity_count 前后一致, remaining_#32770_modals=[] (任务书闭合判据)。

用法: uv run python scripts/itest_37_trectaxis_gate_a_inventory.py
"""

from __future__ import annotations

import asyncio
import ctypes
import sys
import time
from pathlib import Path

sys.stdout.reconfigure(errors="replace")
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import win32con
import win32gui
import win32process

from _live_lock import live_lock_or_exit  # noqa: E402
from t20_mcp.backends.file_ipc import FileIPCBackend  # noqa: E402
from t20_mcp.tools.tangent import _load_prelude  # noqa: E402

RESET_ENV = (
    '(progn (setq n 0)'
    ' (while (and (< n 8) (> (getvar "CMDACTIVE") 0)) (command) (setq n (1+ n)))'
    ' (setvar "CMDDIA" 1) (setvar "FILEDIA" 1) (setvar "OSMODE" 0) "rst")'
)

START_TRECTAXIS = (
    _load_prelude()
    + '\n(progn (setvar "CMDECHO" 1)'
    ' (vl-catch-all-apply (quote vl-cmdf) (list "TRECTAXIS"))'
    ' (strcat "active=" (itoa (getvar "CMDACTIVE"))))'
)


def post_escape(hwnd: int, times: int = 4) -> None:
    pm = ctypes.windll.user32.PostMessageW
    for _ in range(times):
        pm(hwnd, 0x0100, 0x1B, 0)
        pm(hwnd, 0x0101, 0x1B, 0)


def is_modal_owner_disabled(modal_hwnd: int) -> tuple[int, bool]:
    owner = win32gui.GetWindow(modal_hwnd, win32con.GW_OWNER)
    if owner == 0:
        return 0, False
    return owner, not win32gui.IsWindowEnabled(owner)


def enum_children(parent_hwnd: int, depth: int = 2) -> list[dict]:
    out: list[dict] = []

    def walk(h: int, d: int):
        if d > depth:
            return

        def cb(child, _):
            if not win32gui.IsWindow(child):
                return True
            try:
                cls = win32gui.GetClassName(child)
                title = win32gui.GetWindowText(child)
                styles = win32gui.GetWindowLong(child, win32con.GWL_STYLE)
                rect = win32gui.GetWindowRect(child)
                enabled = bool(win32gui.IsWindowEnabled(child))
                visible = bool(win32gui.IsWindowVisible(child))
            except Exception as e:
                out.append({"depth": d, "hwnd": child, "error": repr(e)})
                return True
            out.append({
                "depth": d, "hwnd": child, "class": cls, "title": title,
                "style_hex": f"0x{styles:08X}", "rect": rect,
                "enabled": enabled, "visible": visible,
            })
            walk(child, d + 1)
            return True

        try:
            win32gui.EnumChildWindows(h, cb, None)
        except Exception:
            pass

    walk(parent_hwnd, 1)
    return out


def find_modals_for_pid(pid: int) -> list[int]:
    out: list[int] = []

    def cb(h, _):
        if win32gui.IsWindowVisible(h) and win32gui.GetClassName(h) == "#32770":
            _, wp = win32process.GetWindowThreadProcessId(h)
            if wp == pid:
                out.append(h)
        return True

    win32gui.EnumWindows(cb, None)
    return out


async def main() -> int:
    backend = FileIPCBackend()
    init = await backend.initialize()
    if not init.ok:
        print(f"FAIL init: {init.error}")
        return 1
    _, pid = win32process.GetWindowThreadProcessId(backend._hwnd)

    cn = await backend.execute_lisp('(strcat "cn=" (vl-prin1-to-string (getcname "TRECTAXIS")))')
    print(f"[reg] {cn.payload}")

    await backend.execute_lisp(RESET_ENV)

    base_cnt_r = await backend.entity_count()
    base_cnt = base_cnt_r.payload["count"] if base_cnt_r.ok else -1
    base_modals = find_modals_for_pid(pid)
    print(f"[baseline] entity_count={base_cnt} pre_existing_#32770_modals={base_modals}")

    r = await backend.execute_lisp(START_TRECTAXIS)
    print(f"[launch] ok={r.ok} payload={r.payload!r} error={r.error!r}")
    time.sleep(1.0)

    modals = [h for h in find_modals_for_pid(pid) if h not in base_modals]
    print(f"[modals_after_launch] {modals}")
    inventory: list[dict] = []
    for h in modals:
        try:
            cls = win32gui.GetClassName(h)
            title = win32gui.GetWindowText(h)
            rect = win32gui.GetWindowRect(h)
            enabled = bool(win32gui.IsWindowEnabled(h))
        except Exception as e:
            inventory.append({"hwnd": h, "error": repr(e)})
            continue
        owner, owner_disabled = is_modal_owner_disabled(h)
        children = enum_children(h, depth=2)
        inventory.append({
            "hwnd": h, "class": cls, "title": title,
            "rect": rect, "enabled": enabled,
            "owner_hwnd": owner,
            "owner_disabled (modal-blocking?)": owner_disabled,
            "child_count": len(children),
            "children": children,
        })

    print()
    print("[recover] ESC-only sequence (严禁 WM_CLOSE)")
    for h in modals:
        for _ in range(4):
            post_escape(h, 4)
            time.sleep(0.2)
    await backend.execute_lisp(RESET_ENV)
    time.sleep(0.5)
    post_modals = find_modals_for_pid(pid)
    print(f"[post-recover] remaining_#32770_modals={post_modals}")

    env = await backend.drawing_get_variables(["CMDACTIVE", "CMDDIA", "FILEDIA", "OSMODE"])
    after_cnt_r = await backend.entity_count()
    after_cnt = after_cnt_r.payload["count"] if after_cnt_r.ok else -1
    print(f"[post-recover] entity_count={after_cnt} env={env.payload}")

    print()
    print("=" * 60)
    print("TRectAxis Gate A inventory")
    print("=" * 60)
    for item in inventory:
        print(f"\n# Modal hwnd={item.get('hwnd')} class={item.get('class')!r} title={item.get('title')!r}")
        print(f"  rect={item.get('rect')} enabled={item.get('enabled')}")
        print(f"  owner_hwnd={item.get('owner_hwnd')} owner_disabled={item.get('owner_disabled (modal-blocking?)')}")
        print(f"  children ({item.get('child_count')}):")
        for c in item.get("children", []):
            indent = "    " * c["depth"]
            if "error" in c:
                print(f"  {indent}- err {c.get('error')}")
                continue
            print(f"  {indent}- [{c['depth']}] hwnd={c['hwnd']} class={c['class']!r} title={c['title']!r} "
                  f"style={c['style_hex']} enabled={c['enabled']} visible={c['visible']} rect={c['rect']}")

    has_modal = any(item.get("class") == "#32770" for item in inventory)
    no_residual = not post_modals
    env_clean = env.ok and env.payload.get("CMDACTIVE") == 0
    delta_zero = after_cnt == base_cnt
    print()
    print("=== Step37 Gate A verdict ===")
    print(f"  TRectAxis 弹 #32770 面板                    : {'YES' if has_modal else 'no'}")
    print(f"  ESC 后无残留模态 (remaining_#32770=[])       : {'YES' if no_residual else 'NO'}")
    print(f"  环境恢复 (CMDACTIVE=0)                       : {'YES' if env_clean else 'no'}")
    print(f"  无实体生成 (entity delta=0)                  : {'YES' if delta_zero else 'no'}")
    print(f"  baseline / final entity_count = {base_cnt} / {after_cnt}")
    print(f"  -> 结论: {'BLOCKED-by-#32770 (Gate A inventory captured)' if (has_modal and no_residual and env_clean and delta_zero) else 'INDETERMINATE'}")
    return 0 if (has_modal and no_residual and env_clean and delta_zero) else 2


if __name__ == "__main__":
    _lock = live_lock_or_exit(__file__)
    raise SystemExit(asyncio.run(main()))
