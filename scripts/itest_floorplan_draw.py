"""画真实建筑平面图 + dump 全实体几何数据.

绘制两室一厅户型 (12000x10000mm), 然后 dump 所有实体的
类型/图层/坐标/关键属性到 JSON, 供视觉检查智能体分析。
"""

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
from t20_mcp.tools.tangent import generate_lisp  # noqa: E402


async def execute_tangent(backend, operation, data):
    code = generate_lisp(operation, data)
    result = await backend.execute_lisp(code)
    status = "OK" if result.ok else f"FAIL({result.error})"
    print(f"  {operation:30s} {status}")
    return result


# Dump all entities: type, layer, handle, key DXF groups, COM geometry
DUMP_LISP = """
(progn
  (setq t20mcp:ss (ssget "X"))
  (setq t20mcp:n (sslength t20mcp:ss))
  (setq t20mcp:i 0)
  (setq t20mcp:out "")
  (while (< t20mcp:i t20mcp:n)
    (setq t20mcp:e (ssname t20mcp:ss t20mcp:i))
    (setq t20mcp:ed (entget t20mcp:e))
    (setq t20mcp:ty (cdr (assoc 0 t20mcp:ed)))
    (setq t20mcp:ly (cdr (assoc 8 t20mcp:ed)))
    (setq t20mcp:hd (cdr (assoc 5 t20mcp:ed)))
    ;; try COM geometry for common types
    (setq t20mcp:geo "")
    (setq t20mcp:o (vl-catch-all-apply 'vlax-ename->vla-object (list t20mcp:e)))
    (if (not (vl-catch-all-error-p t20mcp:o))
      (progn
        (setq t20mcp:sp (vl-catch-all-apply 'vlax-get-property (list t20mcp:o "StartPoint")))
        (setq t20mcp:ep (vl-catch-all-apply 'vlax-get-property (list t20mcp:o "EndPoint")))
        (setq t20mcp:ip (vl-catch-all-apply 'vlax-get-property (list t20mcp:o "InsertionPoint")))
        (setq t20mcp:wd (vl-catch-all-apply 'vlax-get-property (list t20mcp:o "Width")))
        (setq t20mcp:ht (vl-catch-all-apply 'vlax-get-property (list t20mcp:o "Height")))
        (setq t20mcp:lw (vl-catch-all-apply 'vlax-get-property (list t20mcp:o "LeftWidth")))
        (setq t20mcp:rw (vl-catch-all-apply 'vlax-get-property (list t20mcp:o "RightWidth")))
        (if (not (vl-catch-all-error-p t20mcp:sp))
          (setq t20mcp:geo (strcat t20mcp:geo "SP=" (vl-princ-to-string t20mcp:sp) " ")))
        (if (not (vl-catch-all-error-p t20mcp:ep))
          (setq t20mcp:geo (strcat t20mcp:geo "EP=" (vl-princ-to-string t20mcp:ep) " ")))
        (if (not (vl-catch-all-error-p t20mcp:ip))
          (setq t20mcp:geo (strcat t20mcp:geo "IP=" (vl-princ-to-string t20mcp:ip) " ")))
        (if (not (vl-catch-all-error-p t20mcp:wd))
          (setq t20mcp:geo (strcat t20mcp:geo "W=" (vl-princ-to-string t20mcp:wd) " ")))
        (if (not (vl-catch-all-error-p t20mcp:ht))
          (setq t20mcp:geo (strcat t20mcp:geo "H=" (vl-princ-to-string t20mcp:ht) " ")))
        (if (not (vl-catch-all-error-p t20mcp:lw))
          (setq t20mcp:geo (strcat t20mcp:geo "LW=" (vl-princ-to-string t20mcp:lw) " ")))
        (if (not (vl-catch-all-error-p t20mcp:rw))
          (setq t20mcp:geo (strcat t20mcp:geo "RW=" (vl-princ-to-string t20mcp:rw) " ")))))
    (setq t20mcp:out (strcat t20mcp:out t20mcp:hd "|" t20mcp:ty "|" t20mcp:ly "|"
                     t20mcp:geo "\\n"))
    (setq t20mcp:i (1+ t20mcp:i)))
  t20mcp:out)
"""

ZOOM_EXTENTS = '(progn (command "_.ZOOM" "_E") (princ))'


async def main() -> int:
    backend = FileIPCBackend()
    init = await backend.initialize()
    if not init.ok:
        print(f"FAIL: initialize: {init.error}")
        return 1

    # 清场
    await backend.execute_lisp('(progn (command "_.ERASE" "_ALL" "") (princ))')
    await backend.execute_lisp('(setvar "OSMODE" 0)')

    WALL_THICKNESS = 240
    HALF_WALL = WALL_THICKNESS / 2

    print("=== 绘制两室一厅户型 ===\n")

    print("【外墙体】")
    await execute_tangent(backend, "wall", {"x1":0,"y1":0,"x2":12000,"y2":0,"left_width":HALF_WALL,"right_width":HALF_WALL,"height":3000})
    await execute_tangent(backend, "wall", {"x1":0,"y1":10000,"x2":12000,"y2":10000,"left_width":HALF_WALL,"right_width":HALF_WALL,"height":3000})
    await execute_tangent(backend, "wall", {"x1":0,"y1":0,"x2":0,"y2":10000,"left_width":HALF_WALL,"right_width":HALF_WALL,"height":3000})
    await execute_tangent(backend, "wall", {"x1":12000,"y1":0,"x2":12000,"y2":10000,"left_width":HALF_WALL,"right_width":HALF_WALL,"height":3000})

    print("\n【内墙体】")
    await execute_tangent(backend, "wall", {"x1":4800,"y1":4500,"x2":12000,"y2":4500,"left_width":HALF_WALL,"right_width":HALF_WALL,"height":3000})
    await execute_tangent(backend, "wall", {"x1":8400,"y1":1200,"x2":8400,"y2":4500,"left_width":HALF_WALL,"right_width":HALF_WALL,"height":3000})
    await execute_tangent(backend, "wall", {"x1":3600,"y1":1200,"x2":3600,"y2":4500,"left_width":HALF_WALL,"right_width":HALF_WALL,"height":3000})
    await execute_tangent(backend, "wall", {"x1":4800,"y1":4500,"x2":4800,"y2":10000,"left_width":HALF_WALL,"right_width":HALF_WALL,"height":3000})
    await execute_tangent(backend, "wall", {"x1":4800,"y1":7500,"x2":10800,"y2":7500,"left_width":HALF_WALL,"right_width":HALF_WALL,"height":3000})
    await execute_tangent(backend, "wall", {"x1":2400,"y1":7000,"x2":4800,"y2":7000,"left_width":HALF_WALL,"right_width":HALF_WALL,"height":3000})
    await execute_tangent(backend, "wall", {"x1":2400,"y1":7000,"x2":2400,"y2":10000,"left_width":HALF_WALL,"right_width":HALF_WALL,"height":3000})

    print("\n【门】")
    await execute_tangent(backend, "door", {"ins_x":6000,"ins_y":0,"width":1000,"height":2100})
    await execute_tangent(backend, "door", {"ins_x":9600,"ins_y":4500,"width":900,"height":2100})
    await execute_tangent(backend, "door", {"ins_x":2400,"ins_y":4500,"width":900,"height":2100})
    await execute_tangent(backend, "door", {"ins_x":10800,"ins_y":7500,"width":900,"height":2100})
    await execute_tangent(backend, "door", {"ins_x":2400,"ins_y":7000,"width":800,"height":2100})

    print("\n【窗户】")
    await execute_tangent(backend, "window", {"ins_x":6000,"ins_y":0,"width":2400,"height":1800,"sill_height":300})
    await execute_tangent(backend, "window", {"ins_x":10200,"ins_y":0,"width":1800,"height":1500,"sill_height":900})
    await execute_tangent(backend, "window", {"ins_x":1800,"ins_y":0,"width":1800,"height":1500,"sill_height":900})
    await execute_tangent(backend, "window", {"ins_x":8400,"ins_y":10000,"width":1500,"height":1500,"sill_height":900})
    await execute_tangent(backend, "window", {"ins_x":1200,"ins_y":10000,"width":1200,"height":1200,"sill_height":1200})

    print("\n【尺寸标注】")
    await execute_tangent(backend, "dimension", {"p1_x":0,"p1_y":0,"p2_x":12000,"p2_y":0,"pos_x":6000,"pos_y":-1500})
    await execute_tangent(backend, "dimension", {"p1_x":0,"p1_y":0,"p2_x":0,"p2_y":10000,"pos_x":-1500,"pos_y":5000})

    print("\n【墙厚标注】")
    for p1x, p1y, p2x, p2y in [(6000,-200,6000,200),(6000,9800,6000,10200),(-200,5000,200,5000),(11800,5000,12200,5000)]:
        await execute_tangent(backend, "wall_thickness_dimension", {"p1_x":p1x,"p1_y":p1y,"p2_x":p2x,"p2_y":p2y})

    print("\n【符号】")
    await execute_tangent(backend, "north_arrow", {"pos_x":14000,"pos_y":5000})
    await execute_tangent(backend, "drawing_name", {"ins_x":6000,"ins_y":-3000,"name_text":"两室一厅户型平面图","scale_text":"1:100"})

    # Zoom extents
    await backend.execute_lisp(ZOOM_EXTENTS)
    await asyncio.sleep(1)

    # Entity count
    c = await backend.entity_count()
    print(f"\n=== 总实体数: {c.payload} ===\n")

    # Dump all entities
    print("=== Dump 全实体 ===")
    dump_r = await backend.execute_lisp(DUMP_LISP)
    dump_text = str(dump_r.payload) if dump_r.payload else ""

    # Parse and save
    entities = []
    for line in dump_text.split("\\n"):
        line = line.strip()
        if not line:
            continue
        parts = line.split("|")
        if len(parts) >= 3:
            entities.append({
                "handle": parts[0],
                "type": parts[1],
                "layer": parts[2],
                "geometry": parts[3] if len(parts) > 3 else "",
            })

    # Save dump
    dump_path = Path(__file__).parent / "floorplan_entities.json"
    dump_path.write_text(json.dumps(entities, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Dump saved: {dump_path} ({len(entities)} entities)")

    # Print summary by type
    by_type: dict[str, int] = {}
    by_layer: dict[str, int] = {}
    for e in entities:
        by_type[e["type"]] = by_type.get(e["type"], 0) + 1
        by_layer[e["layer"]] = by_layer.get(e["layer"], 0) + 1
    print("\n=== 按类型统计 ===")
    for t, n in sorted(by_type.items()):
        print(f"  {t:30s} {n}")
    print("\n=== 按图层统计 ===")
    for l, n in sorted(by_layer.items()):
        print(f"  {l:30s} {n}")

    # Print all entities for log
    print("\n=== 全实体明细 ===")
    for e in entities:
        print(f"  {e['handle']:6s} {e['type']:20s} {e['layer']:15s} {e['geometry']}")

    return 0


if __name__ == "__main__":
    _lock = live_lock_or_exit(__file__)
    raise SystemExit(asyncio.run(main()))
