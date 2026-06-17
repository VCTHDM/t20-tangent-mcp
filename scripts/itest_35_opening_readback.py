"""真机联调 Step 35 — TOpening (door / window) Width/Height/SillHeight COM 读回验证.

目标 (Handoff 32 P1-C / P3 door / P3 window 路线):
    使用现有 tangent.door / tangent.window 子命令 (走 opening.lsp 模板, COM 注入
    Width/Height/DoorSill/SillHeight), 在已存在 TCH_WALL 的前提下:
        1. 真机生成 TCH_OPENING;
        2. 通过 ActiveX 读回 Width / Height / DoorSill (door 模式) 或
           Width / Height / SillHeight (window 模式);
        3. 数值与传入参数匹配, entity type 为 TCH_OPENING。

人工前提 (绝不自动化):
    window 模式需要用户已经把天正"门窗面板"切到窗模式; 否则 TOpening 沿用
    门模式生成门对象, SillHeight 写入将被忽略 (DoorSill 取代之)。

本脚本不写新 wrapper, 只做读回探针。失败结论也作为证据写入 handoff。

用法:
    uv run python scripts/itest_35_opening_readback.py door
    uv run python scripts/itest_35_opening_readback.py window
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
from t20_mcp.tools.tangent import generate_lisp  # noqa: E402

RESET_ENV = (
    '(progn (setq n 0)'
    ' (while (and (< n 6) (> (getvar "CMDACTIVE") 0)) (command) (setq n (1+ n)))'
    ' (setvar "CMDDIA" 1) (setvar "FILEDIA" 1) (setvar "OSMODE" 0) "rst")'
)

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


async def count(b: FileIPCBackend) -> int:
    r = await b.entity_count()
    return r.payload["count"] if r.ok else -1


async def run(mode: str) -> int:
    backend = FileIPCBackend()
    init = await backend.initialize()
    if not init.ok:
        print(f"FAIL init: {init.error}")
        return 1
    await backend.execute_lisp(RESET_ENV)
    base = await count(backend)
    print(f"baseline entity count={base}")

    # 1) 准备一道墙
    wall_code = generate_lisp("wall", {
        "x1": 0, "y1": 0, "x2": 5000, "y2": 0,
        "left_width": 120, "right_width": 120,
        "height": 3000, "wall_type": "砖",
    })
    wall_r = await backend.execute_lisp(wall_code)
    after_wall = await count(backend)
    print(f"[wall] ok={wall_r.ok} count {base}->{after_wall}")
    if after_wall <= base:
        print("FAIL: 墙未创建")
        return 1

    # 2) 在墙上插入 door 或 window
    if mode == "door":
        params = {"ins_x": 1500.0, "ins_y": 0.0, "width": 900.0, "height": 2100.0, "sill_distance": 0.0}
        expect_w, expect_h, expect_ds = 900.0, 2100.0, 0.0
        expect_sh = None
    elif mode == "window":
        params = {"ins_x": 2500.0, "ins_y": 0.0, "width": 1500.0, "height": 1500.0, "sill_height": 900.0}
        expect_w, expect_h = 1500.0, 1500.0
        expect_ds = None
        expect_sh = 900.0
    else:
        print(f"unknown mode: {mode}")
        return 2

    op_code = generate_lisp(mode, params)
    op_r = await backend.execute_lisp(op_code)
    after_op = await count(backend)
    print(f"[{mode}] ok={op_r.ok} payload={op_r.payload!r} count {after_wall}->{after_op}")

    # 3) 读回
    rb = await backend.execute_lisp(READBACK_LISP)
    rb_payload = rb.payload or ""
    print(f"[readback] ok={rb.ok} payload={rb_payload!r}")

    # 4) cleanup
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
    env = await backend.drawing_get_variables(["CMDACTIVE", "CMDDIA", "FILEDIA", "OSMODE"])
    print(f"[cleanup] rounds={rounds} final={final} (baseline {base}) env={env.payload}")

    # 5) 解析读回 + 判定
    delta_ok = after_op == after_wall + 1
    type_ok = "TCH_OPENING" in rb_payload
    print()
    print(f"=== Step35 [{mode}] verdict ===")
    print(f"  entity delta=+1: {'PASS' if delta_ok else 'FAIL'}")
    print(f"  type=TCH_OPENING: {'PASS' if type_ok else 'FAIL'}")
    print(f"  expected: W={expect_w} H={expect_h} DS={expect_ds} SH={expect_sh}")
    print(f"  raw readback: {rb_payload}")
    final_ok = (
        final == base
        and env.ok
        and env.payload.get("CMDACTIVE") == 0
    )
    print(f"  cleanup clean (CMDACTIVE=0 + entity baseline): {'PASS' if final_ok else 'FAIL'}")
    return 0 if (delta_ok and type_ok and final_ok) else 2


async def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    return await run(sys.argv[1])


if __name__ == "__main__":
    _lock = live_lock_or_exit(__file__)
    raise SystemExit(asyncio.run(main()))
