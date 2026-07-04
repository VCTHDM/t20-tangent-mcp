"""cusp_roof (TCuspRoof) 压力测试 — 排查 E2E suite 中的崩溃.

E2E suite 运行~17条命令后 cusp_roof 崩溃 AutoCAD, 但隔离测试 PASS。
本脚本连续运行 cusp_roof N 次 (每次 cleanup), 看是否稳定。
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

N_ITERATIONS = 5


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
    print(f"base count={base}")

    for i in range(N_ITERATIONS):
        before = await count(backend)
        r = await backend.execute_lisp(generate_lisp("cusp_roof", {
            "center_x": 3000 + i * 100, "center_y": 3000,
            "base_x": 6000 + i * 100, "base_y": 3000,
        }))
        after = await count(backend)
        t = await backend.execute_lisp(LAST_TYPE)
        ok = r.ok and after == before + 1 and str(t.payload) == "TCH_CUSPROOF"
        print(f"[iter {i+1}/{N_ITERATIONS}] ok={ok} exec={r.ok} {before}->{after} type={t.payload!r}")
        if not ok:
            print(f"  FAIL at iteration {i+1}")
            break
        # cleanup
        guard = 0
        while await count(backend) > base and guard < 8:
            await backend.undo()
            guard += 1
        await backend.execute_lisp(RESET_ENV)

    final = await count(backend)
    print(f"\ncleanup: {'PASS' if final == base else 'FAIL'} (count {final}=={base})")
    return 0


if __name__ == "__main__":
    _lock = live_lock_or_exit(__file__)
    raise SystemExit(asyncio.run(main()))
