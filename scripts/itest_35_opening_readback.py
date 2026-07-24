"""真机联调 Step 35 — TOpening (door / window) Width/Height/SillHeight COM 读回验证.

目标 (Handoff 32 P1-C / P3 door / P3 window 路线):
    使用现有 tangent.door / tangent.window 子命令 (走 opening.lsp 模板, COM 注入
    Width/Height/DoorSill/SillHeight), 在已存在 TCH_WALL 的前提下:
        1. 真机生成 TCH_OPENING;
        2. 通过 ActiveX 读回 Width / Height / DoorSill (door 模式) 或
           Width / Height / DoorSill (window 模式, Handoff 33 证实门/窗共用
           DoorSill, 窗模式 DoorSill 承载窗台高);
        3. 数值与传入参数匹配, entity type 为 TCH_OPENING。

Handoff 39 更新:
    door/window 调用前会自动识别「门窗参数」工具栏并切换插门/插窗模式；
    插入后仍以 DXF group 71 为最终判据，不依赖控件点击返回值。

本脚本不写新 wrapper, 只做读回探针。失败结论也作为证据写入 handoff。

cleanup 铁律 (P0):
    无论 PASS/FAIL/SKIP, 都必须撤回本轮实体到 baseline, 并把 CMDACTIVE 拉到 0,
    复位 CMDDIA=1 / FILEDIA=1 / OSMODE=0。cleanup 判定同时检查 entity baseline
    与这四个环境变量, 任一不满足即 cleanup FAIL。失败/异常路径走 try/finally
    同样执行 cleanup, 不只清实体。

door 探针对齐 (P1):
    wall/door 参数与执行顺序对齐 itest_12_e2e.py 已真机验证的 good 路径
    (wall 6000 长 / door 在墙中点 3000 / width=1000 height=2000 sill=0),
    开头加清场 undo loop, door 调用后单独读 entlast 类型 + CMDACTIVE 做诊断,
    以区分"插入失败"与"插入成功但类型非 TCH_OPENING"。

用法:
    uv run python scripts/itest_35_opening_readback.py door
    uv run python scripts/itest_35_opening_readback.py window

返回码: 0=PASS, 2=FAIL
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.stdout.reconfigure(errors="replace")
sys.path.insert(0, str(Path(__file__).resolve().parent))  # for _live_lock
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from _live_lock import live_lock_or_exit  # noqa: E402
from t20_mcp.backends.file_ipc import FileIPCBackend  # noqa: E402
from t20_mcp.tools.tangent import execute_opening, generate_lisp  # noqa: E402

# 退出活动命令 (最多 8 层, 与 itest_11 一致) + 复位四变量; 返回 rst CMDACTIVE=N。
RESET_ENV = (
    '(progn (setq n 0)'
    ' (while (and (< n 8) (> (getvar "CMDACTIVE") 0)) (command) (setq n (1+ n)))'
    ' (setvar "CMDDIA" 1) (setvar "FILEDIA" 1) (setvar "OSMODE" 0)'
    ' (strcat "rst CMDACTIVE=" (itoa (getvar "CMDACTIVE"))))'
)

# entlast 的实体类型 (与 itest_12 LAST_TYPE 一致), 用于 door 诊断: 失败时看
# entlast 到底是 TCH_WALL(没插入) 还是别的。
LAST_TYPE = '(if (entlast) (cdr (assoc 0 (entget (entlast)))) "none")'

# entlast 的 DXF group 71: 0=门, 1=窗 (Handoff 33 证实门/窗真区分)。window preflight 用。
GROUP71 = '(if (entlast) (cdr (assoc 71 (entget (entlast)))) "none")'

# 读回最后一个 TCH_OPENING 的 entity type + COM 属性 (返回单字符串供 IPC payload 解析)
# 注意: 必须在外层 setq, 否则 c:t20mcp-rb 的 ( / ...) 局部变量在 strcat 时已脱出作用域。
READBACK_LISP = '''
(setq t20mcp:rb-etyp "no-entity"
      t20mcp:rb-w nil t20mcp:rb-h nil t20mcp:rb-ds nil t20mcp:rb-sh nil)
(if (entlast)
  (progn
    (setq t20mcp:rb-etyp (cdr (assoc 0 (entget (entlast)))))
    (setq o (vlax-ename->vla-object (entlast)))
    (setq t20mcp:rb-w  (vl-catch-all-apply 'vlax-get-property (list o "Width")))
    (setq t20mcp:rb-h  (vl-catch-all-apply 'vlax-get-property (list o "Height")))
    (setq t20mcp:rb-ds (vl-catch-all-apply 'vlax-get-property (list o "DoorSill")))
    (setq t20mcp:rb-sh (vl-catch-all-apply 'vlax-get-property (list o "SillHeight")))))
(strcat
  "type=" (vl-prin1-to-string t20mcp:rb-etyp)
  " W="  (vl-prin1-to-string t20mcp:rb-w)
  " H="  (vl-prin1-to-string t20mcp:rb-h)
  " DS=" (vl-prin1-to-string t20mcp:rb-ds)
  " SH=" (vl-prin1-to-string t20mcp:rb-sh))
'''

# 必须同时复位这四个变量; cleanup 判定逐项检查。
ENV_VARS = ["CMDACTIVE", "CMDDIA", "FILEDIA", "OSMODE"]


async def count(b: FileIPCBackend) -> int:
    r = await b.entity_count()
    return r.payload["count"] if r.ok else -1


async def _reset_env(backend: FileIPCBackend) -> None:
    """退出活动命令 + 复位 CMDDIA/FILEDIA/OSMODE (P0 cleanup 必经步骤)。"""
    r = await backend.execute_lisp(RESET_ENV)
    if not r.ok:
        print(f"[reset] FAIL: {r.error}")


async def _cleanup(backend: FileIPCBackend, base: int) -> bool:
    """结尾清理: 撤销本轮实体回到 baseline, 再复位四环境变量。

    返回 cleanup 是否干净 (entity 回 baseline 且四变量全部归位)。
    无论前面业务 PASS/FAIL 都调用; undo 失败也不跳过环境复位。"""
    rounds = 0
    while rounds < 16:
        c = await count(backend)
        if c <= base or c < 0:
            break
        u = await backend.undo()
        if not u.ok:
            print(f"[cleanup] undo fail: {u.error}")
            break
        rounds += 1
    final = await count(backend)
    # P0: 环境变量复位必须执行, 不依赖 entity undo 是否成功。
    await _reset_env(backend)
    env = await backend.drawing_get_variables(ENV_VARS)
    print(f"[cleanup] rounds={rounds} final={final} (baseline {base}) env={env.payload}")
    return (
        final == base
        and env.ok
        and env.payload.get("CMDACTIVE") == 0
        and env.payload.get("CMDDIA") == 1
        and env.payload.get("FILEDIA") == 1
        and env.payload.get("OSMODE") == 0
    )


async def run(mode: str) -> int:
    backend = FileIPCBackend()
    init = await backend.initialize()
    if not init.ok:
        print(f"FAIL init: {init.error}")
        return 1

    # 开头清场 (对齐 itest_12): 撤销上次运行残留实体 + 复位环境, 保证 baseline 干净。
    guard = 0
    while await count(backend) > 0 and guard < 8:
        await backend.undo()
        guard += 1
    await _reset_env(backend)
    base = await count(backend)
    print(f"baseline entity count={base} (cleaned {guard} undo)")

    verdict_ok = False
    try:
        # 1) 准备一道墙 — 参数对齐 itest_12 已真机验证的 good 路径。
        wall_code = generate_lisp("wall", {
            "x1": 0, "y1": 0, "x2": 6000, "y2": 0,
            "left_width": 240, "right_width": 120,
            "height": 3300, "wall_type": "砖",
        })
        wall_r = await backend.execute_lisp(wall_code)
        after_wall = await count(backend)
        print(f"[wall] ok={wall_r.ok} count {base}->{after_wall}")
        if after_wall <= base:
            print("FAIL: 墙未创建")
            return 1

        # 2) 在墙上插入 door 或 window — door 参数对齐 itest_12 good 路径。
        if mode == "door":
            params = {"ins_x": 3000.0, "ins_y": 0.0,
                      "width": 1000.0, "height": 2000.0, "sill_distance": 0.0}
            expect_w, expect_h, expect_ds = 1000.0, 2000.0, 0.0
            expect_sh = None
        elif mode == "window":
            params = {"ins_x": 3000.0, "ins_y": 0.0,
                      "width": 1500.0, "height": 1500.0, "sill_height": 900.0}
            expect_w, expect_h = 1500.0, 1500.0
            expect_ds = 900.0   # window 模式 DoorSill 承载窗台高 (Handoff 33 修复后)
            expect_sh = None    # TCH_OPENING 不暴露 SillHeight (Handoff 33 枚举证伪)
        else:
            print(f"unknown mode: {mode}")
            return 2

        op_r = await execute_opening(backend, mode, params)
        after_op = await count(backend)
        # P1 诊断: 单独读 entlast 类型 + CMDACTIVE, 区分"没插入"与"插入但类型错"。
        last_type = await backend.execute_lisp(LAST_TYPE)
        ca = await backend.drawing_get_variables(["CMDACTIVE"])
        ca_val = ca.payload.get("CMDACTIVE") if ca.ok else "?"
        print(f"[{mode}] ok={op_r.ok} payload={op_r.payload!r} "
              f"count {after_wall}->{after_op} last_type={last_type.payload!r} CMDACTIVE={ca_val}")

        # 3) 读回
        rb = await backend.execute_lisp(READBACK_LISP)
        rb_payload = rb.payload or ""
        print(f"[readback] ok={rb.ok} payload={rb_payload!r}")

        # 4) 判定
        delta_ok = after_op == after_wall + 1
        type_ok = "TCH_OPENING" in rb_payload
        print()
        print(f"=== Step35 [{mode}] verdict ===")
        print(f"  entity delta=+1: {'PASS' if delta_ok else 'FAIL'}")
        print(f"  type=TCH_OPENING: {'PASS' if type_ok else 'FAIL'}")
        print(f"  expected: W={expect_w} H={expect_h} DS={expect_ds} SH={expect_sh}")
        print(f"  raw readback: {rb_payload}")

        if mode == "window":
            # 最终门禁: 自动切换后仍读 DXF group 71 (1=窗)。
            # IPC payload 把 LISP 的 int 也以字符串形式回传, 所以 1 / "1" 都视为窗模式。
            g71 = await backend.execute_lisp(GROUP71)
            g71_val = g71.payload
            print(f"  [preflight] DXF group 71 = {g71_val!r} (1=窗模式, 0=门模式)")
            verdict_ok = delta_ok and type_ok and g71_val in (1, "1")
        else:
            verdict_ok = delta_ok and type_ok
    finally:
        # P0: 无论 PASS/FAIL/SKIP/异常, 都执行 cleanup — 撤实体 + 复位四环境变量。
        cleanup_ok = await _cleanup(backend, base)

    print(f"  cleanup clean (entity baseline + "
          f"CMDACTIVE=0/CMDDIA=1/FILEDIA=1/OSMODE=0): "
          f"{'PASS' if cleanup_ok else 'FAIL'}")
    return 0 if (verdict_ok and cleanup_ok) else 2


async def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    return await run(sys.argv[1])


if __name__ == "__main__":
    _lock = live_lock_or_exit(__file__)
    raise SystemExit(asyncio.run(main()))
