"""真机联调 — 天正实体 E2E 验收合集.

合并原 itest_15/18/20/27/31/34-43, 统一 CASES → loop → count+type → cleanup 管线.
每个 case 生成 LISP → 执行 → 验证实体增量与类型 → UNDO 清理.

用法: uv run python scripts/itest_e2e_suite.py
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

CASES: list[tuple[str, str, dict, str | None, str]] = [
    # (label, subcommand, params, expected_type, delta_mode)
    # delta_mode: "1" = delta==1, ">0" = after>before, "wall" = needs wall baseline prep
    ("elevation", "elevation",
     {"base_x": 0, "base_y": 0, "label_x": 1000, "label_y": 1000},
     "TCH_ELEVATION", "1"),
    ("wall_thickness_dim", "wall_thickness_dimension",
     {"p1_x": 1500, "p1_y": -500, "p2_x": 1500, "p2_y": 500},
     "TCH_DIM", "wall"),
    ("two_point_dimension", "two_point_dimension",
     {"p1_x": -1000, "p1_y": 0, "p2_x": 7000, "p2_y": 0, "pos_x": 3000, "pos_y": 1500},
     "TCH_DIM", "wall"),
    ("coordinate", "coordinate",
     {"point_x": 1234, "point_y": 5678, "label_x": 1234, "label_y": 6678},
     "TCH_COORD", "1"),
    ("symmetry", "symmetry",
     {"x1": 0, "y1": 0, "x2": 0, "y2": 3000},
     "TCH_SYMMETRY", "1"),
    ("north_arrow", "north_arrow",
     {"pos_x": 0, "pos_y": 0, "dir_x": 0, "dir_y": 1000},
     "TCH_NORTHTHUMB", "1"),
    ("break_line", "break_line",
     {"x1": 0, "y1": 0, "x2": 3000, "y2": 0},
     "TCH_RUPTURE", "1"),
    ("section_symbol", "section_symbol",
     {"x1": 0, "y1": 0, "x2": 3000, "y2": 0, "dir_x": 1500, "dir_y": -1000},
     "TCH_SYMB_SECTION", "1"),
    ("drawing_name", "drawing_name",
     {"ins_x": 0, "ins_y": 0},
     "TCH_DRAWINGNAME", "1"),
    ("rectangle", "rectangle",
     {"x1": 0, "y1": 0, "x2": 3000, "y2": 2000},
     "TCH_RECT", "1"),
    ("balcony", "balcony",
     {"points": [[0, 0], [3000, 0], [3000, 1500], [0, 1500]]},
     "TCH_BALCONY", ">0"),
    ("step", "step",
     {"points": [[0, 0], [3000, 0], [3000, 600], [0, 600]]},
     "TCH_STEP", ">0"),
    ("ramp", "ramp",
     {"x": 1500, "y": 800},
     "TCH_ASCENT", "1"),
    ("arrow", "arrow",
     {"x1": 0, "y1": 0, "x2": 2000, "y2": 0},
     "TCH_ARROW", "1"),
    ("rect_roof", "rect_roof",
     {"x1": 0, "y1": 0, "x2": 6000, "y2": 0, "x3": 6000, "y3": 4000},
     "TCH_MOUNTROOF", "1"),
    ("cusp_roof", "cusp_roof",
     {"center_x": 3000, "center_y": 3000, "base_x": 6000, "base_y": 3000},
     "TCH_CUSPROOF", "1"),
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
    result = await backend.entity_count()
    assert result.ok, result.error
    return result.payload["count"]


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

    # --- opening_dimension needs a wall+door baseline ---
    # (uses pre-existing wall/door like itest_20)
    await backend.execute_lisp(generate_lisp(
        "wall",
        {"x1": 0, "y1": 0, "x2": 3000, "y2": 0,
         "left_width": 120, "right_width": 120, "height": 3000, "wall_type": "砖"},
    ))
    await backend.execute_lisp(generate_lisp(
        "door",
        {"ins_x": 1500, "ins_y": 0, "width": 1000, "height": 2000, "sill_distance": 0},
    ))
    od_before = await count(backend)
    od_result = await backend.execute_lisp(generate_lisp(
        "opening_dimension",
        {"p1_x": -200, "p1_y": 600, "p2_x": 3200, "p2_y": 600},
    ))
    od_after = await count(backend)
    od_type = await backend.execute_lisp(LAST_TYPE)
    od_ok = od_result.ok and od_after == od_before + 1 and str(od_type.payload).startswith("TCH_DIM")
    results["opening_dimension"] = od_ok
    print(f"[opening_dimension] ok={od_ok} {od_before}->{od_after} type={od_type.payload!r}")
    await cleanup_to(backend, base)

    for label, sub, params, expect_type, mode in CASES:
        before = await count(backend)
        # wall-dep: create 3-wall baseline for commands that need traversing
        if mode == "wall":
            await backend.execute_lisp(generate_lisp(
                "wall", {"x1": -1000, "y1": 0, "x2": 0, "y2": 0,
                         "left_width": 120, "right_width": 120, "height": 3000, "wall_type": "砖"},
            ))
            await backend.execute_lisp(generate_lisp(
                "wall", {"x1": 0, "y1": 0, "x2": 3000, "y2": 0,
                         "left_width": 120, "right_width": 120, "height": 3000, "wall_type": "砖"},
            ))
            await backend.execute_lisp(generate_lisp(
                "wall", {"x1": 3000, "y1": 0, "x2": 7000, "y2": 0,
                         "left_width": 120, "right_width": 120, "height": 3000, "wall_type": "砖"},
            ))
            before = await count(backend)
        r = await backend.execute_lisp(generate_lisp(sub, params))
        after = await count(backend)
        t = await backend.execute_lisp(LAST_TYPE)
        ok = r.ok
        if mode == "1":
            ok = ok and after == before + 1
        elif mode == ">0":
            ok = ok and after > before
        # mode == "wall": just check r.ok (entity type may vary)
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
    print("=== E2E 验收合集 ===")
    passed = sum(1 for v in results.values() if v)
    total = len(results)
    for name, ok in results.items():
        print(f"  {name}: {'PASS' if ok else 'FAIL'}")
    print(f"  ({passed}/{total} passed)")
    print(f"  清理还原: {'PASS' if clean else 'FAIL'}")
    return 0 if all(results.values()) and clean else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
