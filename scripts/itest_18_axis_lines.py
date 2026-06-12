"""真机联调 Step 18 — axis_lines 普通线轴网替代路径验收.

走 tangent.generate_lisp("axis_lines") → backend.execute_lisp, 验证生成普通 LINE
数量。完成后 UNDO 还原并复位环境。

用法: uv run python scripts/itest_18_axis_lines.py
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.stdout.reconfigure(errors="replace")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from t20_mcp.backends.file_ipc import FileIPCBackend
from t20_mcp.tools.tangent import generate_lisp

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
    hspacings = [3000, 3000]
    vspacings = [2000]
    expected_delta = len(hspacings) + 1 + len(vspacings) + 1
    code = generate_lisp(
        "axis_lines",
        {
            "base_x": 0,
            "base_y": 0,
            "hspacings": hspacings,
            "vspacings": vspacings,
            "angle": 0,
            "layer": "AXIS",
        },
    )
    result = await backend.execute_lisp(code)
    after = await count(backend)
    delta = after - before
    ok = result.ok and delta == expected_delta
    print(
        f"[axis_lines] ok={ok} exec={result.ok} "
        f"entities {before}->{after} delta={delta} expected={expected_delta} error={result.error!r}"
    )

    if after > before:
        undo = await backend.undo()
        print(f"[cleanup] undo ok={undo.ok} error={undo.error!r}")

    final_count = await count(backend)
    reset = await backend.execute_lisp(RESET_ENV)
    env = await backend.drawing_get_variables(["CMDACTIVE", "CMDDIA", "FILEDIA", "OSMODE"])
    clean = (
        final_count == before
        and reset.ok
        and env.ok
        and env.payload.get("CMDACTIVE") == 0
        and env.payload.get("CMDDIA") == 1
        and env.payload.get("FILEDIA") == 1
        and env.payload.get("OSMODE") == 0
    )
    print(f"[cleanup] entities={final_count} reset={reset.payload!r} env={env.payload}")

    print()
    print("=== Step18 普通线轴网验收 ===")
    print(f"  axis_lines: {'PASS' if ok else 'FAIL'}")
    print(f"  清理还原: {'PASS' if clean else 'FAIL'}")
    return 0 if ok and clean else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
