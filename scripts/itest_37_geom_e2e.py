"""真机联调 Step 37 — rectangle / balcony / step 简单几何构件验收.

均为命令行点序列驱动, 无对话框, 无文字依赖:
- rectangle TRECT     第一角点->第二角点->回车      -> TCH_RECT
- balcony   TBALCONY  各轮廓点->回车                -> TCH_BALCONY
- step      TSTEP     各轮廓点->回车                -> TCH_STEP

阳台/台阶按轮廓可能生成多个实体, 故只校验 (实体增加 且 entlast 类型符合)。

用法: uv run python scripts/itest_37_geom_e2e.py
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

CASES = [
    ("rectangle", {"x1": 0, "y1": 0, "x2": 3000, "y2": 2000},                        "TCH_RECT"),
    ("balcony",   {"points": [[0, 0], [3000, 0], [3000, 1500], [0, 1500]]},          "TCH_BALCONY"),
    ("step",      {"points": [[0, 0], [3000, 0], [3000, 600], [0, 600]]},            "TCH_STEP"),
]


async def count(backend: FileIPCBackend) -> int:
    result = await backend.entity_count()
    assert result.ok, result.error
    return result.payload["count"]


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

    all_ok = True
    print()
    print("=== Step37 简单几何构件 E2E 验收 ===")
    for op, params, expect in CASES:
        await backend.execute_lisp(RESET_ENV)
        base = await count(backend)
        result = await backend.execute_lisp(generate_lisp(op, params))
        after = await count(backend)
        last_type = await backend.execute_lisp(LAST_TYPE)
        ok = result.ok and after > base and last_type.payload == expect
        all_ok = all_ok and ok
        print(
            f"  {op:11}: {'PASS' if ok else 'FAIL'} "
            f"(exec={result.ok}, count {base}->{after}, type={last_type.payload!r}, want={expect})"
        )
        await cleanup_to(backend, base)

    final_count = await count(backend)
    env = await backend.drawing_get_variables(["CMDACTIVE", "CMDDIA", "FILEDIA", "OSMODE"])
    clean = (
        env.ok
        and env.payload.get("CMDACTIVE") == 0
        and env.payload.get("CMDDIA") == 1
        and env.payload.get("FILEDIA") == 1
        and env.payload.get("OSMODE") == 0
    )
    print(f"  清理还原: {'PASS' if clean else 'FAIL'} (final_count={final_count})")
    return 0 if all_ok and clean else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
