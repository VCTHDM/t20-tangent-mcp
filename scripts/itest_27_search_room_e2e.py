"""真机联调 Step 27 — search_room 子命令 E2E 验收.

四段闭合 TCH_WALL → generate_lisp("search_room") 下发 → 断言新增实体为
TCH_SPACE → UNDO 全部清理 → 环境干净。

用法: uv run python scripts/itest_27_search_room_e2e.py
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

LAST_TYPE = '(if (entlast) (cdr (assoc 0 (entget (entlast)))) "none")'


async def count(backend: FileIPCBackend) -> int:
    result = await backend.entity_count()
    if not result.ok:
        print(f"[count] blocked/failed: {result.error}")
        return -1
    return result.payload["count"]


async def main() -> int:
    backend = FileIPCBackend()
    init = await backend.initialize()
    if not init.ok:
        print(f"FAIL: initialize: {init.error}")
        return 1
    await backend.execute_lisp(RESET_ENV)
    before = await count(backend)

    for seg in [(0, 0, 4000, 0), (4000, 0, 4000, 3000), (4000, 3000, 0, 3000), (0, 3000, 0, 0)]:
        r = await backend.execute_lisp(
            generate_lisp(
                "wall",
                {"x1": seg[0], "y1": seg[1], "x2": seg[2], "y2": seg[3],
                 "left_width": 120, "right_width": 120, "height": 3000, "wall_type": "砖"},
            )
        )
        if not r.ok:
            print(f"FAIL: 墙体创建失败 {seg}: {r.error}")
            return 1
    walls = await count(backend)
    print(f"[walls] entities {before}->{walls}")

    result = await backend.execute_lisp(generate_lisp("search_room", {}))
    last_type = await backend.execute_lisp(LAST_TYPE)
    after = await count(backend)
    print(
        f"[search_room] ok={result.ok} error={result.error!r} "
        f"last_type={last_type.payload!r} entities={after}"
    )

    space_created = result.ok and after == walls + 1 and "TCH_SPACE" in str(last_type.payload)

    rounds = 0
    while (c := await count(backend)) > before and c >= 0 and rounds < 12:
        undo = await backend.undo()
        rounds += 1
        if not undo.ok:
            print(f"[cleanup] undo failed: {undo.error}")
            break
    reset = await backend.execute_lisp(RESET_ENV)
    env = await backend.drawing_get_variables(["CMDACTIVE", "CMDDIA", "FILEDIA", "OSMODE"])
    final = await count(backend)
    print(f"[cleanup] entities={final} reset={reset.ok} env={env.payload}")

    checks = {
        "space_created": space_created,
        "final_empty": final == before,
        "env_clean": env.ok
        and env.payload.get("CMDACTIVE") == 0
        and env.payload.get("CMDDIA") == 1
        and env.payload.get("FILEDIA") == 1,
    }
    print(f"[verdict] {checks}")
    return 0 if all(checks.values()) else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
