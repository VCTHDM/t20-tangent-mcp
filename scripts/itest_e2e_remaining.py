"""补跑 E2E 剩余 case (跳过 cusp_roof 已知崩溃).

精度改动 (8->2 位小数) 后的回归验证: 运行 E2E suite 中
rect_roof 之后的 8 个 case, 跳过 cusp_roof (TCUSPROOF 崩溃, 需隔离测试).
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

# cusp_roof 之后的 case (跳过 cusp_roof 本身)
REMAINING_CASES: list[tuple[str, str, dict, str, str]] = [
    ("insight", "insight",
     {"x": 1500, "y": 800},
     "TCH_TDBINSIGHT", "1"),
    ("tree", "tree",
     {"x": 1500, "y": 800},
     "INSERT", "1"),
    ("line_stair", "line_stair",
     {"x": 1500, "y": 800},
     "TCH_LINESTAIR", "1"),
    ("arc_stair", "arc_stair",
     {"x": 1500, "y": 800},
     "TCH_ARCSTAIR", "1"),
    ("double_stair", "double_stair",
     {"x": 0, "y": 0},
     "TCH_RECTSTAIR", "1"),
    ("multi_stair", "multi_stair",
     {"x1": 0, "y1": 0, "x2": 0, "y2": 6000},
     "TCH_MULTISTAIR", "1"),
    ("line_pattern", "line_pattern",
     {"x1": 0, "y1": 0, "x2": 3000, "y2": 0},
     "TCH_PATH_ARRAY", "1"),
    ("wheelchair_diameter", "wheelchair_diameter",
     {"center_x": 0, "center_y": 0, "edge_x": 1500, "edge_y": 0},
     "TCH_RADIUSDIM", ">0"),
]


async def count(backend: FileIPCBackend) -> int:
    r = await backend.entity_count()
    assert r.ok, r.error
    return r.payload["count"]


async def cleanup_to(backend: FileIPCBackend, target: int) -> None:
    guard = 0
    while await count(backend) > target and guard < 16:
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
    base = await count(backend)
    results: dict[str, bool] = {}

    for label, sub, params, expect_type, mode in REMAINING_CASES:
        before = await count(backend)
        r = await backend.execute_lisp(generate_lisp(sub, params))
        after = await count(backend)
        t = await backend.execute_lisp(LAST_TYPE)
        ok = r.ok
        if mode == "1":
            ok = ok and after == before + 1
        elif mode == ">0":
            ok = ok and after > before
        if expect_type and mode != "wall":
            ok = ok and str(t.payload) == expect_type
        results[label] = ok
        print(f"[{label}] ok={ok} exec={r.ok} {before}->{after} type={t.payload!r}")
        await cleanup_to(backend, base)

    final_count = await count(backend)
    env = await backend.drawing_get_variables(["CMDACTIVE", "CMDDIA", "FILEDIA", "OSMODE"])
    clean = (
        final_count == base
        and env.ok
        and env.payload.get("CMDACTIVE") == 0
        and env.payload.get("CMDDIA") == 1
        and env.payload.get("FILEDIA") == 1
        and env.payload.get("OSMODE") == 0
    )

    print()
    print("=== 补跑 E2E (跳过 cusp_roof) ===")
    passed = sum(1 for v in results.values() if v)
    total = len(results)
    for name, ok in results.items():
        print(f"  {name}: {'PASS' if ok else 'FAIL'}")
    print(f"  ({passed}/{total} passed)")
    print(f"  清理还原: {'PASS' if clean else 'FAIL'} (count {final_count}=={base})")
    return 0 if passed == total and clean else 1


if __name__ == "__main__":
    _lock = live_lock_or_exit(__file__)
    raise SystemExit(asyncio.run(main()))
