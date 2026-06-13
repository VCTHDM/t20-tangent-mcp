"""真机联调 Step 36 — section_symbol / drawing_name 符号标注验收 (第二批).

均为命令行点序列驱动, 无对话框, 循环式命令补空回车退出:
- section_symbol TSECTION     第一剖切点->第二剖切点->剖视方向->回车 -> TCH_SYMB_SECTION
- drawing_name   TDRAWINGNAME 插入位置->回车                       -> TCH_DRAWINGNAME

用法: uv run python scripts/itest_36_symbol2_e2e.py
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
    ("section_symbol", {"x1": 0, "y1": 0, "x2": 3000, "y2": 0, "dir_x": 1500, "dir_y": -1000}, "TCH_SYMB_SECTION"),
    ("drawing_name",   {"ins_x": 0, "ins_y": 0},                                              "TCH_DRAWINGNAME"),
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
    print("=== Step36 符号标注 E2E 验收 (第二批) ===")
    for op, params, expect in CASES:
        await backend.execute_lisp(RESET_ENV)
        base = await count(backend)
        result = await backend.execute_lisp(generate_lisp(op, params))
        after = await count(backend)
        last_type = await backend.execute_lisp(LAST_TYPE)
        ok = result.ok and after == base + 1 and last_type.payload == expect
        all_ok = all_ok and ok
        print(
            f"  {op:15}: {'PASS' if ok else 'FAIL'} "
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
