"""真机联调 Step 20 — TDimWall / TDim3 标注封装验收.

验证 tangent 的:
- wall_thickness_dimension -> TDimWall -> TCH_DIMENSION2
- opening_dimension -> TDim3 -> TCH_DIMENSION2

用法: uv run python scripts/itest_20_tangent_dimensions.py
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


async def make_wall(backend: FileIPCBackend) -> None:
    await backend.execute_lisp(
        generate_lisp(
            "wall",
            {
                "x1": 0, "y1": 0, "x2": 3000, "y2": 0,
                "left_width": 120, "right_width": 120, "height": 3000,
                "wall_type": "砖",
            },
        )
    )


async def make_opening(backend: FileIPCBackend) -> None:
    await make_wall(backend)
    await backend.execute_lisp(
        generate_lisp(
            "door",
            {"ins_x": 1500, "ins_y": 0, "width": 1000, "height": 2000, "sill_distance": 0},
        )
    )


async def cleanup_to(backend: FileIPCBackend, target_count: int) -> None:
    guard = 0
    while await count(backend) > target_count and guard < 12:
        await backend.undo()
        guard += 1
    await backend.execute_lisp(RESET_ENV)


async def main() -> int:
    backend = FileIPCBackend()
    init = await backend.initialize()
    if not init.ok:
        print(f"FAIL: initialize: {init.error}")
        return 1

    await backend.execute_lisp(RESET_ENV)
    base = await count(backend)
    results: dict[str, bool] = {}

    await make_wall(backend)
    before = await count(backend)
    wall_dim = await backend.execute_lisp(
        generate_lisp(
            "wall_thickness_dimension",
            {"p1_x": 1500, "p1_y": -500, "p2_x": 1500, "p2_y": 500},
        )
    )
    after = await count(backend)
    last_type = await backend.execute_lisp(LAST_TYPE)
    ok = wall_dim.ok and after == before + 1 and str(last_type.payload).startswith("TCH_DIM")
    results["wall_thickness_dimension"] = ok
    print(
        f"[wall_thickness_dimension] ok={ok} exec={wall_dim.ok} "
        f"entities {before}->{after} type={last_type.payload!r}"
    )
    await cleanup_to(backend, base)

    await make_opening(backend)
    before = await count(backend)
    opening_dim = await backend.execute_lisp(
        generate_lisp(
            "opening_dimension",
            {"p1_x": -200, "p1_y": 600, "p2_x": 3200, "p2_y": 600},
        )
    )
    after = await count(backend)
    last_type = await backend.execute_lisp(LAST_TYPE)
    ok = opening_dim.ok and after == before + 1 and str(last_type.payload).startswith("TCH_DIM")
    results["opening_dimension"] = ok
    print(
        f"[opening_dimension] ok={ok} exec={opening_dim.ok} "
        f"entities {before}->{after} type={last_type.payload!r}"
    )
    await cleanup_to(backend, base)

    final_count = await count(backend)
    env = await backend.drawing_get_variables(["CMDACTIVE", "CMDDIA", "FILEDIA", "OSMODE"])
    clean = (
        final_count == base
        and env.ok
        and env.payload.get("CMDACTIVE") == 0
        and env.payload.get("CMDDIA") == 1
        and env.payload.get("FILEDIA") == 1
        and env.payload.get("OSMODE") == 0
    )

    print()
    print("=== Step20 标注封装验收 ===")
    for name, ok in results.items():
        print(f"  {name}: {'PASS' if ok else 'FAIL'}")
    print(f"  清理还原: {'PASS' if clean else 'FAIL'}")
    return 0 if all(results.values()) and clean else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
