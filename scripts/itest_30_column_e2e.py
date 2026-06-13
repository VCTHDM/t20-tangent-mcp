"""真机联调 Step 30 — TGColumn / column 子命令 E2E 验收.

generate_lisp("column") 下发 -> 断言新增实体为 TCH_COLUMN -> UNDO 清理
-> 环境干净。截面尺寸来自标准柱面板记忆值, 本脚本只验证最小点序列封装。

用法: uv run python scripts/itest_30_column_e2e.py
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
    before = await count(backend)

    result = await backend.execute_lisp(generate_lisp("column", {"x": 0, "y": 0}))
    after = await count(backend)
    last_type = await backend.execute_lisp(LAST_TYPE)
    ok = result.ok and after == before + 1 and last_type.payload == "TCH_COLUMN"
    print(
        f"[column] ok={ok} exec={result.ok} error={result.error!r} "
        f"entities {before}->{after} type={last_type.payload!r}"
    )

    await cleanup_to(backend, before)
    final_count = await count(backend)
    env = await backend.drawing_get_variables(["CMDACTIVE", "CMDDIA", "FILEDIA", "OSMODE"])
    clean = (
        final_count == before
        and env.ok
        and env.payload.get("CMDACTIVE") == 0
        and env.payload.get("CMDDIA") == 1
        and env.payload.get("FILEDIA") == 1
        and env.payload.get("OSMODE") == 0
    )

    print()
    print("=== Step30 标准柱封装验收 ===")
    print(f"  column: {'PASS' if ok else 'FAIL'}")
    print(f"  清理还原: {'PASS' if clean else 'FAIL'}")
    return 0 if ok and clean else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
