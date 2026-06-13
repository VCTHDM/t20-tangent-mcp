"""真机联调 Step 35 — symmetry / north_arrow / break_line 符号标注验收.

验证三个符号标注子命令 (均为命令行点序列驱动, 无对话框):
- symmetry    TSYMMETRY   起点->终点                 -> TCH_SYMMETRY
- north_arrow TNORTHTHUMB 位置点->方向点             -> TCH_NORTHTHUMB
- break_line  TSYMBCUT    起点->终点->回车(<不切割>)  -> TCH_RUPTURE

用法: uv run python scripts/itest_35_symbol_e2e.py
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

# 子命令 -> (参数, 期望实体类型)
CASES = [
    ("symmetry",    {"x1": 0, "y1": 0, "x2": 0, "y2": 3000},              "TCH_SYMMETRY"),
    ("north_arrow", {"pos_x": 0, "pos_y": 0, "dir_x": 0, "dir_y": 1000},  "TCH_NORTHTHUMB"),
    ("break_line",  {"x1": 0, "y1": 0, "x2": 3000, "y2": 0},              "TCH_RUPTURE"),
]


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

    all_ok = True
    print()
    print("=== Step35 符号标注 E2E 验收 ===")
    for op, params, expect in CASES:
        await backend.execute_lisp(RESET_ENV)
        base = await count(backend)
        result = await backend.execute_lisp(generate_lisp(op, params))
        after = await count(backend)
        last_type = await backend.execute_lisp(LAST_TYPE)
        ok = result.ok and after == base + 1 and last_type.payload == expect
        all_ok = all_ok and ok
        print(
            f"  {op:12}: {'PASS' if ok else 'FAIL'} "
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
