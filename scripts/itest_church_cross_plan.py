"""真机绘制并验收拉丁十字形教堂平面。"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

sys.stdout.reconfigure(errors="replace")
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from _live_lock import live_lock_or_exit  # noqa: E402
from t20_mcp.backends.file_ipc import FileIPCBackend  # noqa: E402
from t20_mcp.tools.tangent import execute_opening, generate_lisp  # noqa: E402


DUMP_LISP = r"""
(progn
  (setq t20mcp:ss (ssget "X"))
  (setq t20mcp:i 0 t20mcp:out "")
  (while (< t20mcp:i (sslength t20mcp:ss))
    (setq t20mcp:e (ssname t20mcp:ss t20mcp:i))
    (setq t20mcp:ed (entget t20mcp:e))
    (setq t20mcp:out
      (strcat t20mcp:out
              (cdr (assoc 5 t20mcp:ed)) "|"
              (cdr (assoc 0 t20mcp:ed)) "|"
              (cdr (assoc 8 t20mcp:ed)) "@@"))
    (setq t20mcp:i (1+ t20mcp:i)))
  t20mcp:out)
"""


async def tangent(backend: FileIPCBackend, operation: str, data: dict) -> bool:
    if operation in {"door", "window"}:
        result = await execute_opening(backend, operation, data)
    else:
        result = await backend.execute_lisp(generate_lisp(operation, data))
    print(f"  {operation:30s} {'OK' if result.ok else 'FAIL'}")
    if result.error:
        print(f"    {result.error}")
    if not result.ok:
        raise RuntimeError(f"{operation} failed: {result.error}")
    # T20 在连续处理智能墙转角时需要短暂完成内部重生成。
    await asyncio.sleep(0.15)
    return result.ok


async def main() -> int:
    backend = FileIPCBackend()
    init = await backend.initialize()
    if not init.ok:
        print(f"FAIL: initialize: {init.error}")
        return 1

    await backend.execute_lisp('(progn (command "_.ERASE" "_ALL" "") (setvar "OSMODE" 0) (princ))')
    half = 120
    wall_data = {"left_width": half, "right_width": half, "height": 7200}

    print("=== 拉丁十字形教堂平面 ===")
    print("\n【十字形外墙】")
    outline = [
        (5000, 0, 13000, 0),
        (13000, 0, 13000, 15000),
        (13000, 15000, 18000, 15000),
        (18000, 15000, 18000, 23000),
        (13000, 23000, 18000, 23000),
        (13000, 23000, 13000, 30000),
        (13000, 30000, 5000, 30000),
        (5000, 30000, 5000, 23000),
        (5000, 23000, 0, 23000),
        (0, 23000, 0, 15000),
        (0, 15000, 5000, 15000),
        (5000, 15000, 5000, 0),
    ]
    for x1, y1, x2, y2 in outline:
        await tangent(backend, "wall", {"x1": x1, "y1": y1, "x2": x2, "y2": y2, **wall_data})

    print("\n【内部空间】")
    internal = [
        (5000, 4000, 13000, 4000),  # 门厅 / 中殿
        (5000, 24500, 13000, 24500),  # 圣坛区
        (3500, 15000, 3500, 23000),  # 西侧小礼拜堂
        (14500, 15000, 14500, 23000),  # 东侧小礼拜堂
    ]
    for x1, y1, x2, y2 in internal:
        await tangent(backend, "wall", {"x1": x1, "y1": y1, "x2": x2, "y2": y2, **wall_data})

    print("\n【入口与内门】")
    doors = [
        (9000, 0, 1800),
        (9000, 4000, 1600),
        (0, 19000, 1400),
        (18000, 19000, 1400),
        (9000, 24500, 1600),
        (3500, 19000, 1200),
        (14500, 19000, 1200),
    ]
    for x, y, width in doors:
        await tangent(backend, "door", {"ins_x": x, "ins_y": y, "width": width, "height": 2400})

    print("\n【高窗与玫瑰窗】")
    windows = [
        (5000, 8000, 1800, 1500, 1200),
        (13000, 8000, 1800, 1500, 1200),
        (5000, 12000, 1800, 1500, 1200),
        (13000, 12000, 1800, 1500, 1200),
        (2500, 15000, 1600, 1500, 1200),
        (15500, 15000, 1600, 1500, 1200),
        (2500, 23000, 1600, 1500, 1200),
        (15500, 23000, 1600, 1500, 1200),
        (9000, 30000, 2400, 2400, 1500),
    ]
    for x, y, width, height, sill in windows:
        await tangent(
            backend,
            "window",
            {
                "ins_x": x,
                "ins_y": y,
                "width": width,
                "height": height,
                "sill_height": sill,
            },
        )

    print("\n【祭坛、长椅与空间名】")
    await backend.create_rectangle(7500, 27400, 10500, 28400, "FURNITURE")
    for y in (6500, 8200, 9900, 11600, 13300):
        await backend.create_rectangle(6100, y, 8500, y + 500, "FURNITURE")
        await backend.create_rectangle(9500, y, 11900, y + 500, "FURNITURE")
    labels = [
        (7600, 1800, 2800, "门厅"),
        (7600, 9500, 2800, "中殿"),
        (700, 19300, 2800, "西耳堂"),
        (14800, 19300, 2800, "东耳堂"),
        (7600, 26200, 2800, "圣坛"),
    ]
    for x, y, width, text in labels:
        await backend.create_mtext(x, y, width, text, 420, "PUB_TEXT")

    print("\n【确定性总尺寸】")
    await backend.execute_lisp('(setvar "CLAYER" "PUB_DIM")')
    dims = [
        await backend.create_dimension_linear(0, 23000, 18000, 23000, 9000, 32500),
        await backend.create_dimension_linear(5000, 0, 5000, 30000, -2500, 15000),
        await backend.create_dimension_linear(5000, 0, 13000, 0, 9000, -2500),
    ]
    await backend.execute_lisp('(setvar "CLAYER" "0")')
    for name, result in zip(("transept=18000", "length=30000", "nave=8000"), dims):
        print(f"  {name:30s} {'OK' if result.ok else 'FAIL'}")

    print("\n【图名与指北针】")
    await tangent(backend, "north_arrow", {"pos_x": 21500, "pos_y": 23500})
    await tangent(
        backend,
        "drawing_name",
        {
            "ins_x": 9000,
            "ins_y": -4800,
            "name_text": "十字形教堂首层平面图",
            "scale_text": "1:100",
        },
    )
    await backend.execute_lisp('(progn (command "_.ZOOM" "_E") (princ))')
    await asyncio.sleep(1)

    dump = await backend.execute_lisp(DUMP_LISP)
    if not dump.ok:
        print(f"FAIL: dump: {dump.error}")
        return 1
    entities: list[dict[str, str]] = []
    for record in (dump.payload or "").split("@@"):
        if not record:
            continue
        handle, entity_type, layer = record.split("|", 2)
        entities.append({"handle": handle, "type": entity_type, "layer": layer})

    output = Path(__file__).with_name("church_cross_entities.json")
    output.write_text(json.dumps(entities, ensure_ascii=False, indent=2), encoding="utf-8")
    by_type: dict[str, int] = {}
    by_layer: dict[str, int] = {}
    for entity in entities:
        by_type[entity["type"]] = by_type.get(entity["type"], 0) + 1
        by_layer[entity["layer"]] = by_layer.get(entity["layer"], 0) + 1

    checks = {
        "walls>=16": by_type.get("TCH_WALL", 0) >= 16,
        "openings=16": by_type.get("TCH_OPENING", 0) == 16,
        "doors=7": by_layer.get("DOOR_FIRE", 0) == 7,
        "windows=9": by_layer.get("WINDOW", 0) == 9,
        "linear_dimensions=3": by_type.get("DIMENSION", 0) == 3,
        "furniture_rectangles=11": by_type.get("LWPOLYLINE", 0) == 11,
        "labels=5": by_type.get("MTEXT", 0) == 5,
        "north_arrow=1": by_type.get("TCH_NORTHTHUMB", 0) == 1,
        "drawing_name=1": by_type.get("TCH_DRAWINGNAME", 0) == 1,
    }
    print(f"\n=== 实体总数: {len(entities)} ===")
    print("类型:", by_type)
    print("图层:", by_layer)
    print("\n=== 验收 ===")
    for name, passed in checks.items():
        print(f"  {name:30s} {'PASS' if passed else 'FAIL'}")
    print(f"实体清单: {output}")
    return 0 if all(checks.values()) else 1


if __name__ == "__main__":
    _lock = live_lock_or_exit(__file__)
    raise SystemExit(asyncio.run(main()))
