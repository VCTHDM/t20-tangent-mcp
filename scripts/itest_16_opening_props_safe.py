"""真机联调 Step 16 — TCH_OPENING 属性探测 (不触碰轴网/弹框命令).

画一段墙, 用 TOPENING 插入当前面板模式下的门窗对象, 只探测 TCH_OPENING
ActiveX 属性并试写候选窗台/类型属性。完成后 UNDO 清理。

用法: uv run python scripts/itest_16_opening_props_safe.py
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.stdout.reconfigure(errors="replace")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from t20_mcp.backends.file_ipc import FileIPCBackend
from t20_mcp.tools.tangent import generate_lisp

LAST_TYPE = '(if (entlast) (cdr (assoc 0 (entget (entlast)))) "none")'

OPENING_PROPS = [
    "Width", "Height", "DoorSill", "SillHeight", "Elevation",
    "Kind", "Type", "OpeningKind", "Style", "Number", "Tag",
    "WinType", "DoorType", "OpType", "SubType", "SubKind", "Category",
    "Distance", "UpLevel", "Bottom", "Sill", "WindowSill", "WindowSillHeight",
]

PROBE_GET = """
(setq t20mcp:obj (vlax-ename->vla-object (entlast)))
(setq t20mcp:r "")
(foreach p (list {PROPS})
  (setq t20mcp:v (vl-catch-all-apply 'vlax-get-property (list t20mcp:obj p)))
  (setq t20mcp:r
        (strcat t20mcp:r p "="
                (if (vl-catch-all-error-p t20mcp:v)
                    "<no>"
                    (vl-princ-to-string (if (= (type t20mcp:v) 'VARIANT)
                                            (vlax-variant-value t20mcp:v)
                                            t20mcp:v)))
                ";")))
t20mcp:r
"""

PROBE_PUT = """
(setq t20mcp:obj (vlax-ename->vla-object (entlast)))
(setq t20mcp:r "")
(foreach pv (list {PAIRS})
  (setq t20mcp:e (vl-catch-all-apply 'vlax-put-property
                                     (list t20mcp:obj (car pv) (cdr pv))))
  (setq t20mcp:r
        (strcat t20mcp:r (car pv) "->"
                (if (vl-catch-all-error-p t20mcp:e) "putFAIL" "putOK") ";")))
t20mcp:r
"""

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


async def count(backend: FileIPCBackend) -> int:
    result = await backend.entity_count()
    assert result.ok, result.error
    return result.payload["count"]


async def main() -> int:
    backend = FileIPCBackend()
    init = await backend.initialize()
    if not init.ok:
        print(f"FAIL: initialize: {init.error}")
        return 1

    await backend.execute_lisp(RESET_ENV)
    before = await count(backend)

    wall = await backend.execute_lisp(
        generate_lisp(
            "wall",
            {
                "x1": 0, "y1": 0, "x2": 3000, "y2": 0,
                "left_width": 120, "right_width": 120, "height": 3000,
                "wall_type": "砖",
            },
        )
    )
    opening = await backend.execute_lisp(
        generate_lisp(
            "door",
            {"ins_x": 1500, "ins_y": 0, "width": 1000, "height": 2000, "sill_distance": 0},
        )
    )
    last_type = await backend.execute_lisp(LAST_TYPE)
    print(
        f"[create] wall={wall.ok} opening={opening.ok} "
        f"type={last_type.payload!r} entities {before}->{await count(backend)}"
    )

    props = " ".join(f'"{prop}"' for prop in OPENING_PROPS)
    got = await backend.execute_lisp(PROBE_GET.replace("{PROPS}", props))
    print(f"[get] {got.payload if got.ok else got.error}")

    pairs = " ".join(
        [
            '(cons "SillHeight" 600.0)',
            '(cons "WindowSillHeight" 600.0)',
            '(cons "OpType" 1)',
            '(cons "Kind" 1)',
            '(cons "Type" 1)',
            '(cons "WinType" 1)',
        ]
    )
    put = await backend.execute_lisp(PROBE_PUT.replace("{PAIRS}", pairs))
    print(f"[put] {put.payload if put.ok else put.error}")

    verify = await backend.execute_lisp(
        PROBE_GET.replace(
            "{PROPS}",
            '"Width" "Height" "DoorSill" "SillHeight" "WindowSillHeight" '
            '"OpType" "Kind" "Type" "WinType"',
        )
    )
    print(f"[verify] {verify.payload if verify.ok else verify.error}")

    while await count(backend) > before:
        undo = await backend.undo()
        print(f"[cleanup] undo ok={undo.ok} error={undo.error!r}")

    reset = await backend.execute_lisp(RESET_ENV)
    env = await backend.drawing_get_variables(["CMDACTIVE", "CMDDIA", "FILEDIA", "OSMODE"])
    final_count = await count(backend)
    print(f"[cleanup] entities={final_count} reset={reset.payload!r} env={env.payload}")
    return 0 if final_count == before and last_type.payload == "TCH_OPENING" else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
