"""真机联调 Step 40 — insight / tree 单点插入构件验收.

均为命令行单点循环插入, 无对话框, 无选对象步:
- insight  TINSIGHT     标注位置点->回车退出循环   -> TCH_TDBINSIGHT
- tree     TSINGLETREE  插入点->回车退出循环       -> INSERT (树木图块, 块名形如 tree1)

朝向/编号/树种走天正面板记忆值, 只参数化插入点。
E2E 校验「实体增加 且 entlast 类型符合」。

用法: uv run python scripts/itest_40_insight_tree_e2e.py
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

CASES = [
    ("insight", {"x": 0, "y": 0},       "TCH_TDBINSIGHT"),
    ("tree",    {"x": 8000, "y": 0},    "INSERT"),
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
    print("=== Step40 insight/tree 单点插入构件 E2E 验收 ===")
    for op, params, expect in CASES:
        await backend.execute_lisp(RESET_ENV)
        base = await count(backend)
        result = await backend.execute_lisp(generate_lisp(op, params))
        after = await count(backend)
        last_type = await backend.execute_lisp(LAST_TYPE)
        ok = result.ok and after > base and last_type.payload == expect
        all_ok = all_ok and ok
        print(
            f"  {op:8}: {'PASS' if ok else 'FAIL'} "
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
