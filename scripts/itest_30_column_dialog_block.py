"""历史 raw-vl-cmdf 探针 — TGColumn #32770 面板阻塞复测 (Handoff 13).

注意：本脚本只固化「直接用 vl-cmdf 喂插入点无法穿透标准柱面板」这一历史结论，
不代表当前 ``tangent.column`` 不可执行。现行实现已由 Handoff 36 改为 Win32
控件级 UI 自动化，并完成真机验证；当前 column 验收应走 execute_column/itest_39。

背景: Handoff 12 曾记录 TGCOLUMN 单点序列生成 1 个 TCH_COLUMN (delta=1),
据此把 column 转正为 "E2E 已验证"。2026-06-13 真机复测**不可复现**:
TGCOLUMN 弹 #32770 标准柱面板且命令保持 active=1, vl-cmdf 喂入的点字符串
到不了"绘图区放置"处理器 -> 0 实体。Handoff 12 的 delta=1 是面板恰好开着的
顺序依赖假成功；该 raw-vl-cmdf 路径随后被控件级 UI 自动化取代。

本脚本固化该结论, 作为回归记录: 断言 TGCOLUMN
  (a) 不生成任何实体, 且 (b) 留命令 active, 且 (c) 弹出 #32770 面板。
对照: 同环境下 wall (TgWall, 命令行驱动) 应正常生成 TCH_WALL。

用法: uv run python scripts/itest_30_column_dialog_block.py
"""

from __future__ import annotations

import asyncio
import sys
import time
from pathlib import Path

sys.stdout.reconfigure(errors="replace")
sys.path.insert(0, str(Path(__file__).resolve().parent))  # for _live_lock
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import win32gui
import win32process

from _live_lock import live_lock_or_exit  # noqa: E402
from t20_mcp.backends.file_ipc import FileIPCBackend  # noqa: E402
from t20_mcp.tools.tangent import _load_prelude, generate_lisp  # noqa: E402

RESET_ENV = (
    "(progn (setq n 0)"
    ' (while (and (< n 8) (> (getvar "CMDACTIVE") 0)) (command) (setq n (1+ n)))'
    ' (setvar "CMDDIA" 1) (setvar "FILEDIA" 1) (setvar "OSMODE" 0) "env-reset")'
)

# CMDECHO=0 静默跑 TGCOLUMN + 一个点, 留命令活动 (由 Python 侧后续 reset 取消)。
RUN_TGCOLUMN = (
    _load_prelude() + '\n(progn (setvar "CMDECHO" 0)'
    ' (vl-catch-all-apply (quote vl-cmdf) (list "TGCOLUMN" "2000,2000"))'
    ' (strcat "active=" (itoa (getvar "CMDACTIVE"))))'
)


def popup_classes(pid: int) -> list[str]:
    out: list[str] = []

    def cb(h, _):
        if win32gui.IsWindowVisible(h):
            _, wp = win32process.GetWindowThreadProcessId(h)
            if wp == pid:
                out.append(win32gui.GetClassName(h))
        return True

    win32gui.EnumWindows(cb, None)
    return out


async def count(b: FileIPCBackend) -> int:
    r = await b.entity_count()
    return r.payload["count"] if r.ok else -1


async def main() -> int:
    b = FileIPCBackend()
    init = await b.initialize()
    if not init.ok:
        print(f"FAIL: initialize: {init.error}")
        return 1
    _, pid = win32process.GetWindowThreadProcessId(b._hwnd)

    await b.execute_lisp(RESET_ENV)
    base = await count(b)

    # --- 对照: wall 命令行驱动应正常 ---
    await b.execute_lisp(
        generate_lisp(
            "wall",
            {
                "x1": 0,
                "y1": 0,
                "x2": 3000,
                "y2": 0,
                "left_width": 120,
                "right_width": 120,
                "height": 3000,
                "wall_type": "砖",
            },
        )
    )
    wall_ok = await count(b) == base + 1
    for _ in range(6):
        if await count(b) <= base:
            break
        await b.undo()

    # --- TGCOLUMN: 期望 0 实体 + 命令 active + #32770 面板 ---
    r = await b.execute_lisp(RUN_TGCOLUMN)
    time.sleep(0.6)
    after = await count(b)
    classes = popup_classes(pid)
    has_dialog = "#32770" in classes
    active = r.payload or ""

    # 取消活动命令并确认面板消失 + 图面回到 baseline
    await b.execute_lisp(RESET_ENV)
    time.sleep(0.3)
    dialog_gone = "#32770" not in popup_classes(pid)
    rounds = 0
    while await count(b) > base and rounds < 8:
        await b.undo()
        rounds += 1
    final = await count(b)
    env = await b.drawing_get_variables(["CMDACTIVE", "CMDDIA", "FILEDIA", "OSMODE"])

    blocker = after == base and "active=1" in active and has_dialog
    clean = (
        dialog_gone
        and final == base
        and env.ok
        and env.payload.get("CMDACTIVE") == 0
        and env.payload.get("CMDDIA") == 1
    )

    print()
    print("=== Step30 标准柱 #32770 阻塞复测 ===")
    print(f"  对照 wall 命令行驱动正常: {'PASS' if wall_ok else 'FAIL'}")
    print(f"  TGCOLUMN 0 实体: {'PASS' if after == base else 'FAIL'} (count {base}->{after})")
    print(f"  命令保持 active: {'PASS' if 'active=1' in active else 'FAIL'} ({active})")
    print(f"  弹 #32770 面板: {'PASS' if has_dialog else 'FAIL'}")
    print(f"  阻塞结论复现: {'PASS' if blocker else 'FAIL'}")
    print(f"  清理还原: {'PASS' if clean else 'FAIL'}")
    print("  -> 仅 raw vl-cmdf 路径被阻塞；现行 column 使用控件级 UI 自动化")
    return 0 if blocker and clean and wall_ok else 1


if __name__ == "__main__":
    _lock = live_lock_or_exit(__file__)
    raise SystemExit(asyncio.run(main()))
