"""真机验证: two_point_dimension (TDIMTP) 平行墙穿越线修复.

修复: 原 E2E suite 用 3 面共线墙 (沿 y=0), TDIMTP 视为 1 面连续墙
→ "对象数目太少" 不生成标注。改为 3 面平行墙 + 垂直穿越线。
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.stdout.reconfigure(errors="replace")
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from _live_lock import live_lock_or_exit  # noqa: E402
from t20_mcp.backends.file_ipc import FileIPCBackend  # noqa: E402
from t20_mcp.tools.tangent import generate_lisp  # noqa: E402

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
    r = await backend.entity_count()
    assert r.ok, r.error
    return r.payload["count"]


async def main() -> int:
    backend = FileIPCBackend()
    init = await backend.initialize()
    if not init.ok:
        print(f"FAIL: initialize: {init.error}")
        return 1

    await backend.execute_lisp(RESET_ENV)
    base = await count(backend)

    # 3 面平行墙 (不同 y), 垂直穿越线穿过全部 3 面
    await backend.execute_lisp(generate_lisp(
        "wall", {"x1": 0, "y1": 0, "x2": 3000, "y2": 0,
                 "left_width": 120, "right_width": 120, "height": 3000, "wall_type": "砖"},
    ))
    await backend.execute_lisp(generate_lisp(
        "wall", {"x1": 0, "y1": 2000, "x2": 3000, "y2": 2000,
                 "left_width": 120, "right_width": 120, "height": 3000, "wall_type": "砖"},
    ))
    await backend.execute_lisp(generate_lisp(
        "wall", {"x1": 0, "y1": 4000, "x2": 3000, "y2": 4000,
                 "left_width": 120, "right_width": 120, "height": 3000, "wall_type": "砖"},
    ))
    before = await count(backend)
    print(f"3 parallel walls created, count={before}")

    r = await backend.execute_lisp(generate_lisp("two_point_dimension", {
        "p1_x": 1500, "p1_y": -500, "p2_x": 1500, "p2_y": 4500,
        "pos_x": 2500, "pos_y": 2000,
    }))
    after = await count(backend)
    t = await backend.execute_lisp(LAST_TYPE)
    ok = r.ok and after == before + 1 and str(t.payload).startswith("TCH_DIM")
    print(f"[two_point_dimension] ok={ok} exec={r.ok} {before}->{after} type={t.payload!r}")

    # cleanup
    guard = 0
    while await count(backend) > base and guard < 16:
        await backend.undo()
        guard += 1
    await backend.execute_lisp(RESET_ENV)
    final = await count(backend)
    clean = final == base
    print(f"cleanup: {'PASS' if clean else 'FAIL'} (count {final}=={base})")
    return 0 if ok and clean else 1


if __name__ == "__main__":
    _lock = live_lock_or_exit(__file__)
    raise SystemExit(asyncio.run(main()))
