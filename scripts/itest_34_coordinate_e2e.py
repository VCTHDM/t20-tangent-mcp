"""真机联调 Step 34 — TCoord / coordinate 坐标标注验收.

验证 tangent.coordinate:
- TCOORD 点序列: 标注点 -> 坐标标注方向点 -> 回车
- 新增实体类型: TCH_COORD

用法: uv run python scripts/itest_34_coordinate_e2e.py
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


async def cleanup_to(backend: FileIPCBackend, target_count: int) -> None:
    guard = 0
    while await count(backend) > target_count and guard < 8:
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

    result = await backend.execute_lisp(
        generate_lisp(
            "coordinate",
            {
                "point_x": 1234,
                "point_y": 5678,
                "label_x": 1234,
                "label_y": 6678,
            },
        )
    )
    after = await count(backend)
    last_type = await backend.execute_lisp(LAST_TYPE)
    coord_ok = result.ok and after == base + 1 and last_type.payload == "TCH_COORD"

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
    print("=== Step34 TCoord 坐标标注验收 ===")
    print(
        f"  coordinate: {'PASS' if coord_ok else 'FAIL'} "
        f"(exec={result.ok}, count {base}->{after}, type={last_type.payload!r})"
    )
    print(f"  清理还原: {'PASS' if clean else 'FAIL'}")
    return 0 if coord_ok and clean else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
