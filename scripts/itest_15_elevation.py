"""真机联调 Step 15 — elevation / TMElev 端到端验收.

走 tangent.generate_lisp("elevation") → backend.execute_lisp, 验证实体增量与
TCH_ELEVATION 类型。完成后 UNDO 还原并复位环境。

用法: uv run python scripts/itest_15_elevation.py
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


async def main() -> int:
    backend = FileIPCBackend()
    init = await backend.initialize()
    if not init.ok:
        print(f"FAIL: initialize: {init.error}")
        return 1

    await backend.execute_lisp(RESET_ENV)
    before = await count(backend)
    code = generate_lisp(
        "elevation",
        {"base_x": 0, "base_y": 0, "label_x": 1000, "label_y": 1000},
    )
    result = await backend.execute_lisp(code)
    after = await count(backend)
    last_type = await backend.execute_lisp(LAST_TYPE)

    ok = result.ok and after == before + 1 and last_type.payload == "TCH_ELEVATION"
    print(
        f"[elevation] ok={ok} exec={result.ok} "
        f"entities {before}->{after} type={last_type.payload!r} error={result.error!r}"
    )

    if after > before:
        undo = await backend.undo()
        print(f"[cleanup] undo ok={undo.ok} error={undo.error!r}")

    final_count = await count(backend)
    reset = await backend.execute_lisp(RESET_ENV)
    env = await backend.drawing_get_variables(["CMDACTIVE", "CMDDIA", "FILEDIA", "OSMODE"])
    print(f"[cleanup] entities={final_count} reset={reset.payload!r} env={env.payload}")

    print()
    print("=== Step15 标高验收 ===")
    print(f"  elevation: {'PASS' if ok else 'FAIL'}")
    print(f"  清理还原: {'PASS' if final_count == 0 else 'FAIL'}")
    return 0 if ok and final_count == 0 else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
