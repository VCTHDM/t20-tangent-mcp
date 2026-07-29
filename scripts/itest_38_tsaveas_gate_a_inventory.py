"""真机联调 Step 38 — TSaveAs / 整图导出框 Gate A inventory.

TODO_BACKLOG §C2. Gate A 规则与 itest_36/37 一致: ESC-only, 不点击不填框,
不发 IDCANCEL, 严禁 WM_CLOSE (Handoff 09 ARX 致命崩溃证据)。

差异点:
- 同时枚举 #32770 与任意类名的新顶层窗口 (WPF 自绘可能不挂 #32770);
- 子树深度 = 3, 标记 WPF (HwndWrapper / System.Windows / Microsoft.*) 类;
- 启动前 setvar FILEDIA 0, 用以复核任务书断言 "WPF 框无视 FILEDIA=0"。

用法: uv run python scripts/itest_38_tsaveas_gate_a_inventory.py
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
    "(progn (setq n 0)"
    ' (while (and (< n 8) (> (getvar "CMDACTIVE") 0)) (command) (setq n (1+ n)))'
    ' (setvar "CMDDIA" 1) (setvar "FILEDIA" 1) (setvar "OSMODE" 0) "rst")'
)

START_TSAVEAS = (
    _load_prelude() + '\n(progn (setvar "CMDECHO" 1) (setvar "FILEDIA" 0)'
    ' (vl-catch-all-apply (quote vl-cmdf) (list "TSAVEAS"))'
    ' (strcat "active=" (itoa (getvar "CMDACTIVE"))'
    '         " filedia=" (itoa (getvar "FILEDIA"))))'
)

WPF_TOKENS = ("HwndWrapper", "System.Windows", "Microsoft.")


def post_esc(hwnd: int, n: int = 4) -> None:
    pm = ctypes.windll.user32.PostMessageW
    for _ in range(n):
        pm(hwnd, 0x0100, 0x1B, 0)
        pm(hwnd, 0x0101, 0x1B, 0)


def owner_state(h: int) -> tuple[int, bool]:
    o = win32gui.GetWindow(h, win32con.GW_OWNER)
    return (o, not win32gui.IsWindowEnabled(o)) if o else (0, False)


def is_wpf(cls: str) -> bool:
    return any(t in cls for t in WPF_TOKENS)


def enum_kids(parent: int, depth: int = 3) -> list[dict]:
    out: list[dict] = []

    def walk(h: int, d: int):
        if d > depth:
            return

        def cb(c, _):
            if not win32gui.IsWindow(c):
                return True
            try:
                rec = {
                    "depth": d,
                    "hwnd": c,
                    "class": win32gui.GetClassName(c),
                    "title": win32gui.GetWindowText(c),
                    "style_hex": f"0x{win32gui.GetWindowLong(c, win32con.GWL_STYLE):08X}",
                    "rect": win32gui.GetWindowRect(c),
                    "enabled": bool(win32gui.IsWindowEnabled(c)),
                    "visible": bool(win32gui.IsWindowVisible(c)),
                }
            except Exception as e:
                out.append({"depth": d, "hwnd": c, "error": repr(e)})
                return True
            out.append(rec)
            walk(c, d + 1)
            return True

        try:
            win32gui.EnumChildWindows(h, cb, None)
        except Exception:
            pass

    walk(parent, 1)
    return out


def list_tops(pid: int) -> list[tuple[int, str, str]]:
    out: list[tuple[int, str, str]] = []

    def cb(h, _):
        if win32gui.IsWindowVisible(h):
            _, wp = win32process.GetWindowThreadProcessId(h)
            if wp == pid:
                try:
                    out.append((h, win32gui.GetClassName(h), win32gui.GetWindowText(h)))
                except Exception:
                    pass
        return True

    win32gui.EnumWindows(cb, None)
    return out


def list_modals(pid: int) -> list[int]:
    return [h for h, c, _ in list_tops(pid) if c == "#32770"]


async def main() -> int:
    b = FileIPCBackend()
    init = await b.initialize()
    if not init.ok:
        print(f"FAIL init: {init.error}")
        return 1
    _, pid = win32process.GetWindowThreadProcessId(b._hwnd)

    cn = await b.execute_lisp('(strcat "cn=" (vl-prin1-to-string (getcname "TSAVEAS")))')
    print(f"[reg] {cn.payload}")
    await b.execute_lisp(RESET_ENV)

    base_cnt = (await b.entity_count()).payload.get("count", -1)
    base_modals = list_modals(pid)
    base_tops = list_tops(pid)
    base_top_h = {h for h, _, _ in base_tops}
    print(f"[baseline] entity_count={base_cnt} pre_modals={base_modals} top_count={len(base_tops)}")

    r = await b.execute_lisp(START_TSAVEAS)
    print(f"[launch] ok={r.ok} payload={r.payload!r} error={r.error!r}")
    time.sleep(1.5)

    new_modals = [h for h in list_modals(pid) if h not in base_modals]
    new_tops = [(h, c, t) for h, c, t in list_tops(pid) if h not in base_top_h]
    print(f"[after_launch] new_modals={new_modals}")
    print(f"[after_launch] new_top_windows={new_tops}")

    inv: list[dict] = []
    targets = list({h for h in new_modals} | {h for h, _, _ in new_tops})
    for h in targets:
        try:
            rec = {
                "hwnd": h,
                "class": win32gui.GetClassName(h),
                "title": win32gui.GetWindowText(h),
                "rect": win32gui.GetWindowRect(h),
                "enabled": bool(win32gui.IsWindowEnabled(h)),
            }
        except Exception as e:
            inv.append({"hwnd": h, "error": repr(e)})
            continue
        own, owd = owner_state(h)
        kids = enum_kids(h, depth=3)
        wpf_hits = [k for k in kids if "class" in k and is_wpf(k["class"])]
        rec.update(
            {
                "owner_hwnd": own,
                "owner_disabled": owd,
                "child_count": len(kids),
                "wpf_child_count": len(wpf_hits),
                "wpf_classes": list({k["class"] for k in wpf_hits})[:8],
                "children": kids,
            }
        )
        inv.append(rec)

    print()
    print("[recover] ESC-only (严禁 WM_CLOSE; ARX 崩溃风险)")
    for h in targets:
        for _ in range(6):
            post_esc(h, 4)
            time.sleep(0.25)
    await b.execute_lisp(RESET_ENV)
    time.sleep(0.5)

    post_modals = list_modals(pid)
    post_new_tops = [(h, c, t) for h, c, t in list_tops(pid) if h not in base_top_h]
    env = await b.drawing_get_variables(["CMDACTIVE", "CMDDIA", "FILEDIA", "OSMODE"])
    after_cnt = (await b.entity_count()).payload.get("count", -1)
    print(f"[post] modals={post_modals} new_tops={post_new_tops}")
    print(f"[post] entity_count={after_cnt} env={env.payload}")

    print()
    print("=" * 60)
    print("TSaveAs Gate A inventory")
    print("=" * 60)
    for it in inv:
        if "error" in it:
            print(f"\n# hwnd={it.get('hwnd')} ERR {it.get('error')}")
            continue
        print(f"\n# Top hwnd={it['hwnd']} class={it['class']!r} title={it['title']!r}")
        print(f"  rect={it['rect']} enabled={it['enabled']}")
        print(f"  owner_hwnd={it['owner_hwnd']} owner_disabled={it['owner_disabled']}")
        print(f"  child_count={it['child_count']}  wpf_child_count={it['wpf_child_count']}")
        print(f"  wpf_classes={it['wpf_classes']}")
        for c in it["children"]:
            ind = "    " * c["depth"]
            if "error" in c:
                print(f"  {ind}- err {c.get('error')}")
                continue
            print(
                f"  {ind}- [{c['depth']}] hwnd={c['hwnd']} class={c['class']!r} title={c['title']!r} "
                f"style={c['style_hex']} enabled={c['enabled']} visible={c['visible']} rect={c['rect']}"
            )

    has_modal = any(it.get("class") == "#32770" for it in inv if "error" not in it)
    has_wpf = any((it.get("wpf_child_count") or 0) > 0 for it in inv if "error" not in it) or any(
        is_wpf(it.get("class", "")) for it in inv if "error" not in it
    )
    blocked_under_filedia0 = bool(targets)
    no_residual = (not post_modals) and (not post_new_tops)
    env_clean = env.ok and env.payload.get("CMDACTIVE") == 0
    delta_zero = after_cnt == base_cnt
    print()
    print("=== Step38 Gate A verdict ===")
    print(f"  TSaveAs 弹 #32770                            : {'YES' if has_modal else 'no'}")
    print(f"  WPF 内嵌存在 (HwndWrapper/...)               : {'YES' if has_wpf else 'no'}")
    print(
        f"  FILEDIA=0 未拦住模态                         : {'YES' if blocked_under_filedia0 else 'no'}"
    )
    print(
        f"  ESC 后无残留 (modal+top)                     : {'YES' if no_residual else 'NO  *警告*'}"
    )
    print(f"  环境恢复 (CMDACTIVE=0)                       : {'YES' if env_clean else 'no'}")
    print(f"  无实体生成 (entity delta=0)                  : {'YES' if delta_zero else 'no'}")
    print(f"  baseline / final entity_count = {base_cnt} / {after_cnt}")
    if not no_residual:
        print()
        print("  *警告*: ESC 未能干净关闭 TSaveAs 模态/WPF 顶层。")
        print("         请用户手动关闭 (点取消按钮); 不要再跑本探针。")
    pass_all = has_modal and no_residual and env_clean and delta_zero
    print(
        f"  -> 结论: {'BLOCKED-Win32-modal' if (pass_all and not has_wpf) else ('BLOCKED-WPF-host' if (pass_all and has_wpf) else 'INDETERMINATE')}"
    )
    return 0 if pass_all else 2


if __name__ == "__main__":
    _lock = live_lock_or_exit(__file__)
    raise SystemExit(asyncio.run(main()))
