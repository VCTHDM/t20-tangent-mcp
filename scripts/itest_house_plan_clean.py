"""两室一厅朝南户型绘制 - 纯净标注版.

户型: 12000 x 10000 mm
标注原则:
  - 只用 dimension (整体尺寸) + wall_thickness_dimension (墙厚)
  - 不使用 two_point_dimension (会乱标)
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from _live_lock import live_lock_or_exit  # noqa: E402
from t20_mcp.backends.file_ipc import FileIPCBackend, find_autocad_window  # noqa: E402
from t20_mcp.tools.tangent import execute_opening, generate_lisp  # noqa: E402


async def execute_tangent(backend, operation, data):
    """执行 tangent 命令"""
    print(f"\n--- 执行: {operation} ---")
    if operation in {"door", "window"}:
        result = await execute_opening(backend, operation, data)
    else:
        code = generate_lisp(operation, data)
        result = await backend.execute_lisp(code)
    print(f"  ok={result.ok}, payload={result.payload!r}")
    if result.error:
        print(f"  error={result.error}")
    return result


async def main() -> int:
    hwnd = find_autocad_window()
    print(f"[1] 找到 AutoCAD 窗口: hwnd={hwnd}")
    if not hwnd:
        print("FAIL: 未找到 acad.exe 窗口")
        return 1

    backend = FileIPCBackend()
    init = await backend.initialize()
    print(f"[2] 初始化后端: ok={init.ok}")
    if not init.ok:
        print(f"    error: {init.error}")
        return 1

    WALL_THICKNESS = 240
    HALF_WALL = WALL_THICKNESS / 2

    print("\n" + "=" * 60)
    print("开始绘制两室一厅 (纯净标注版)")
    print("=" * 60)

    # ========== 外墙体 ==========
    print("\n【外墙体】")
    await execute_tangent(
        backend,
        "wall",
        {
            "x1": 0,
            "y1": 0,
            "x2": 12000,
            "y2": 0,
            "left_width": HALF_WALL,
            "right_width": HALF_WALL,
            "height": 3000,
        },
    )
    await execute_tangent(
        backend,
        "wall",
        {
            "x1": 0,
            "y1": 10000,
            "x2": 12000,
            "y2": 10000,
            "left_width": HALF_WALL,
            "right_width": HALF_WALL,
            "height": 3000,
        },
    )
    await execute_tangent(
        backend,
        "wall",
        {
            "x1": 0,
            "y1": 0,
            "x2": 0,
            "y2": 10000,
            "left_width": HALF_WALL,
            "right_width": HALF_WALL,
            "height": 3000,
        },
    )
    await execute_tangent(
        backend,
        "wall",
        {
            "x1": 12000,
            "y1": 0,
            "x2": 12000,
            "y2": 10000,
            "left_width": HALF_WALL,
            "right_width": HALF_WALL,
            "height": 3000,
        },
    )

    # ========== 内墙体 ==========
    print("\n【内墙体】")
    await execute_tangent(
        backend,
        "wall",
        {
            "x1": 4800,
            "y1": 4500,
            "x2": 12000,
            "y2": 4500,
            "left_width": HALF_WALL,
            "right_width": HALF_WALL,
            "height": 3000,
        },
    )
    await execute_tangent(
        backend,
        "wall",
        {
            "x1": 8400,
            "y1": 1200,
            "x2": 8400,
            "y2": 4500,
            "left_width": HALF_WALL,
            "right_width": HALF_WALL,
            "height": 3000,
        },
    )
    await execute_tangent(
        backend,
        "wall",
        {
            "x1": 3600,
            "y1": 1200,
            "x2": 3600,
            "y2": 4500,
            "left_width": HALF_WALL,
            "right_width": HALF_WALL,
            "height": 3000,
        },
    )
    await execute_tangent(
        backend,
        "wall",
        {
            "x1": 4800,
            "y1": 4500,
            "x2": 4800,
            "y2": 10000,
            "left_width": HALF_WALL,
            "right_width": HALF_WALL,
            "height": 3000,
        },
    )
    await execute_tangent(
        backend,
        "wall",
        {
            "x1": 4800,
            "y1": 7500,
            "x2": 10800,
            "y2": 7500,
            "left_width": HALF_WALL,
            "right_width": HALF_WALL,
            "height": 3000,
        },
    )
    await execute_tangent(
        backend,
        "wall",
        {
            "x1": 2400,
            "y1": 7000,
            "x2": 4800,
            "y2": 7000,
            "left_width": HALF_WALL,
            "right_width": HALF_WALL,
            "height": 3000,
        },
    )
    await execute_tangent(
        backend,
        "wall",
        {
            "x1": 2400,
            "y1": 7000,
            "x2": 2400,
            "y2": 10000,
            "left_width": HALF_WALL,
            "right_width": HALF_WALL,
            "height": 3000,
        },
    )

    # ========== 门 ==========
    print("\n【门】")
    await execute_tangent(
        backend, "door", {"ins_x": 6000, "ins_y": 0, "width": 1000, "height": 2100}
    )
    await execute_tangent(
        backend, "door", {"ins_x": 9600, "ins_y": 4500, "width": 900, "height": 2100}
    )
    await execute_tangent(
        backend, "door", {"ins_x": 2400, "ins_y": 4500, "width": 900, "height": 2100}
    )
    await execute_tangent(
        backend, "door", {"ins_x": 10800, "ins_y": 7500, "width": 900, "height": 2100}
    )
    await execute_tangent(
        backend, "door", {"ins_x": 2400, "ins_y": 7000, "width": 800, "height": 2100}
    )

    # ========== 窗户 ==========
    print("\n【窗户】")
    await execute_tangent(
        backend,
        "window",
        {"ins_x": 6000, "ins_y": 0, "width": 2400, "height": 1800, "sill_height": 300},
    )
    await execute_tangent(
        backend,
        "window",
        {"ins_x": 10200, "ins_y": 0, "width": 1800, "height": 1500, "sill_height": 900},
    )
    await execute_tangent(
        backend,
        "window",
        {"ins_x": 1800, "ins_y": 0, "width": 1800, "height": 1500, "sill_height": 900},
    )
    await execute_tangent(
        backend,
        "window",
        {"ins_x": 8400, "ins_y": 10000, "width": 1500, "height": 1500, "sill_height": 900},
    )
    await execute_tangent(
        backend,
        "window",
        {"ins_x": 1200, "ins_y": 10000, "width": 1200, "height": 1200, "sill_height": 1200},
    )

    # ========== 尺寸标注 (纯净版) ==========
    print("\n【尺寸标注】")

    # 整体水平尺寸 (底部)
    await execute_tangent(
        backend,
        "dimension",
        {
            "p1_x": 0,
            "p1_y": 0,
            "p2_x": 12000,
            "p2_y": 0,
            "pos_x": 6000,
            "pos_y": -1500,
        },
    )

    # 整体垂直尺寸 (左侧)
    await execute_tangent(
        backend,
        "dimension",
        {
            "p1_x": 0,
            "p1_y": 0,
            "p2_x": 0,
            "p2_y": 10000,
            "pos_x": -1500,
            "pos_y": 5000,
        },
    )

    # ========== 墙厚标注 (只在外墙，不标注内墙) ==========
    print("\n【墙厚标注】")
    wall_thick_pos = [
        (6000, -200, 6000, 200),  # 南外墙
        (6000, 9800, 6000, 10200),  # 北外墙
        (-200, 5000, 200, 5000),  # 西外墙
        (11800, 5000, 12200, 5000),  # 东外墙
    ]
    for p1x, p1y, p2x, p2y in wall_thick_pos:
        await execute_tangent(
            backend,
            "wall_thickness_dimension",
            {
                "p1_x": p1x,
                "p1_y": p1y,
                "p2_x": p2x,
                "p2_y": p2y,
            },
        )

    # ========== 符号 ==========
    print("\n【符号】")
    await execute_tangent(backend, "north_arrow", {"pos_x": 14000, "pos_y": 5000})
    await execute_tangent(
        backend,
        "drawing_name",
        {"ins_x": 6000, "ins_y": -3000, "name_text": "两室一厅户型平面图", "scale_text": "1:100"},
    )

    print("\n" + "=" * 60)
    print("绘制完成！")
    print("=" * 60)
    return 0


if __name__ == "__main__":
    _lock = live_lock_or_exit(__file__)
    raise SystemExit(asyncio.run(main()))
