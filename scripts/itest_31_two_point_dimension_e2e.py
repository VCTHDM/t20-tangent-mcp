"""真机联调 Step 31 — TDimTP / two_point_dimension 两点标注验收.

场景: 新建三道短墙 (x=0/3000/6000, y=-600..600), 再用一条水平穿越线
(-1000,0)->(7000,0) 和标注位置 (3000,1500) 驱动 TDimTP。

用法: uv run python scripts/itest_31_two_point_dimension_e2e.py
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
  (while (and (< n 8) (> (getvar "CMDACTIVE") 0))
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


async def cleanup_to(backend: FileIPCBackend, target_count: int) -> None:
    guard = 0
    while await count(backend) > target_count and guard < 16:
        await backend.undo()
        guard += 1
    await backend.execute_lisp(RESET_ENV)


async def make_three_walls(backend: FileIPCBackend) -> None:
    for x in (0, 3000, 6000):
        await backend.execute_lisp(
            generate_lisp(
                "wall",
                {
                    "x1": x,
                    "y1": -600,
                    "x2": x,
                    "y2": 600,
                    "left_width": 120,
                    "right_width": 120,
                    "height": 3000,
                    "wall_type": "砖墙",
                },
            )
        )


async def main() -> int:
    backend = FileIPCBackend()
    init = await backend.initialize()
    if not init.ok:
        print(f"FAIL: initialize: {init.error}")
        return 1

    await backend.execute_lisp(RESET_ENV)
    base = await count(backend)

    await make_three_walls(backend)
    wall_count = await count(backend)
    walls_ok = wall_count == base + 3

    dim_result = await backend.execute_lisp(
        generate_lisp(
            "two_point_dimension",
            {
                "p1_x": -1000,
                "p1_y": 0,
                "p2_x": 7000,
                "p2_y": 0,
                "pos_x": 3000,
                "pos_y": 1500,
            },
        )
    )
    after_dim = await count(backend)
    last_type = await backend.execute_lisp(LAST_TYPE)
    dim_ok = (
        walls_ok
        and dim_result.ok
        and after_dim == wall_count + 1
        and str(last_type.payload).startswith("TCH_DIM")
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
    print("=== Step31 TDimTP 两点标注验收 ===")
    print(f"  三墙基线场景: {'PASS' if walls_ok else 'FAIL'} (count {base}->{wall_count})")
    print(
        f"  two_point_dimension: {'PASS' if dim_ok else 'FAIL'} "
        f"(exec={dim_result.ok}, count {wall_count}->{after_dim}, type={last_type.payload!r})"
    )
    print(f"  清理还原: {'PASS' if clean else 'FAIL'}")
    return 0 if walls_ok and dim_ok and clean else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
