"""真机联调 Step 12 — 端到端验收: 生产路径跑 wall / dimension / door.

走 tangent.generate_lisp (含 prelude 拼接) → backend.execute_lisp, 之后回读
实体类型与 COM 属性, 验证参数注入真实生效。全部完成后 UNDO 还原并复位环境。

用法: uv run python scripts/itest_12_e2e.py
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.stdout.reconfigure(errors="replace")  # 控制台代码页不全时不致崩
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from t20_mcp.backends.file_ipc import FileIPCBackend
from t20_mcp.tools.tangent import generate_lisp

LAST_TYPE = '(if (entlast) (cdr (assoc 0 (entget (entlast)))) "none")'

RESET_ENV = """
(progn
  (setq n 0)
  (while (and (< n 6) (> (getvar "CMDACTIVE") 0))
    (command)
    (setq n (1+ n)))
  (setvar "CMDDIA" 1)
  (setvar "FILEDIA" 1)
  (setvar "OSMODE" 0)
  "env-reset")
"""

READBACK = """
(setq t20mcp:obj (vlax-ename->vla-object (entlast)))
(setq t20mcp:r "")
(foreach p (list {PROPS})
  (setq t20mcp:v (vl-catch-all-apply 'vlax-get-property (list t20mcp:obj p)))
  (setq t20mcp:r
        (strcat t20mcp:r p "="
                (if (vl-catch-all-error-p t20mcp:v)
                    "<no>"
                    (vl-princ-to-string t20mcp:v))
                ";")))
t20mcp:r
"""


async def count(backend: FileIPCBackend) -> int:
    r = await backend.entity_count()
    assert r.ok, r.error
    return r.payload["count"]


async def main() -> int:
    backend = FileIPCBackend()
    init = await backend.initialize()
    if not init.ok:
        print(f"FAIL: initialize: {init.error}")
        return 1

    # 清场: 撤销之前运行残留的实体 (scratch 图纸)
    guard = 0
    while await count(backend) > 0 and guard < 8:
        await backend.undo()
        guard += 1

    results: dict[str, bool] = {}

    # --- 1. wall ---
    before = await count(backend)
    code = generate_lisp("wall", {
        "x1": 0, "y1": 0, "x2": 6000, "y2": 0,
        "left_width": 240, "right_width": 120, "height": 3300, "wall_type": "砖",
    })
    r = await backend.execute_lisp(code)
    after = await count(backend)
    t = await backend.execute_lisp(LAST_TYPE)
    rb = await backend.execute_lisp(
        READBACK.replace("{PROPS}", '"LeftWidth" "RightWidth" "Height" "Style"'))
    ok = (after == before + 1 and t.payload == "TCH_WALL"
          and "LeftWidth=240.0" in str(rb.payload) and "Height=3300.0" in str(rb.payload))
    results["wall"] = ok
    print(f"[wall] ok={ok} exec={r.ok} type={t.payload!r} readback={rb.payload!r}")

    # --- 2. dimension (标注刚画的墙两端) ---
    before = await count(backend)
    code = generate_lisp("dimension", {
        "p1_x": 0, "p1_y": 0, "p2_x": 6000, "p2_y": 0, "pos_x": 3000, "pos_y": 1500,
    })
    r = await backend.execute_lisp(code)
    after = await count(backend)
    t = await backend.execute_lisp(LAST_TYPE)
    ok = after == before + 1 and str(t.payload).startswith("TCH_DIM")
    results["dimension"] = ok
    print(f"[dimension] ok={ok} exec={r.ok} type={t.payload!r}")

    # --- 3. door (插在墙中段) ---
    before = await count(backend)
    code = generate_lisp("door", {
        "ins_x": 3000, "ins_y": 0, "width": 1000, "height": 2000, "sill_distance": 0,
    })
    r = await backend.execute_lisp(code)
    after = await count(backend)
    t = await backend.execute_lisp(LAST_TYPE)
    rb = await backend.execute_lisp(READBACK.replace("{PROPS}", '"Width" "Height" "DoorSill"'))
    ok = (after == before + 1 and t.payload == "TCH_OPENING"
          and "Width=1000.0" in str(rb.payload) and "Height=2000.0" in str(rb.payload))
    results["door"] = ok
    print(f"[door] ok={ok} exec={r.ok} type={t.payload!r} readback={rb.payload!r}")

    # --- 3b. opening ancillary COM properties (SillHeight/OpType/Kind) ---
    extra_rb = await backend.execute_lisp(
        READBACK.replace("{PROPS}",
            '"SillHeight" "WindowSillHeight" "OpType" "Kind" "Type" "WinType"'))
    results["door_extra_props"] = (
        extra_rb.ok and "SillHeight" in str(extra_rb.payload)
    )
    print(f"[door_extra_props] ok={results['door_extra_props']} readback={extra_rb.payload!r}")

    # --- 清理与环境复位 ---
    for _ in range(3):
        await backend.undo()
    final_count = await count(backend)
    await backend.execute_lisp(
        '(progn '
        '(setq t20mcp:layers (vla-get-Layers (vla-get-ActiveDocument (vlax-get-acad-object)))) '
        '(vl-catch-all-apply '
        "  '(lambda () (vla-Delete (vla-Item t20mcp:layers \"T20MCP测试图层\")))) "
        '"layer-cleanup")'
    )
    await backend.execute_lisp(RESET_ENV)
    env = await backend.drawing_get_variables(["CMDDIA", "FILEDIA", "OSMODE", "CMDACTIVE"])
    print(f"[cleanup] entities={final_count} env={env.payload}")

    print()
    print("=== Step12 端到端验收 ===")
    for name, ok in results.items():
        print(f"  {name}: {'PASS' if ok else 'FAIL'}")
    clean_env = (
        env.ok
        and env.payload.get("CMDACTIVE") == 0
        and env.payload.get("CMDDIA") == 1
        and env.payload.get("FILEDIA") == 1
        and env.payload.get("OSMODE") == 0
    )
    print(f"  清理还原: {'PASS' if final_count == 0 and clean_env else 'FAIL'}")
    return 0 if all(results.values()) and final_count == 0 and clean_env else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
