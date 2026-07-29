"""真机联调 Step 25 — explode_read 子命令 E2E 验收.

走生产路径: generate_lisp("explode_read") 直接下发 (原生 _.EXPLODE 不弹框,
与 tangent 工具 execute 分支同构), 验证:

1. TCH_WALL 副本被分解, 产物 ≥4 条 LINE;
2. parse_explode_payload 平移回原位后, 终点侧坐标落在墙体外轮廓上;
   起点侧允许出现**已知 T20 缺陷**: explode 产物起点顶点归零
   (TEXPLODE/EXPLODE 同源, COM Explode 未暴露, 见 handoff 10);
3. clean=T (模板内 UNDO 回滚成功), 实体数回到只剩原墙;
4. 原墙 UNDO 后图纸回空, 环境干净。

用法: uv run python scripts/itest_25_explode_read_e2e.py
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.stdout.reconfigure(errors="replace")
sys.path.insert(0, str(Path(__file__).resolve().parent))  # for _live_lock
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from _live_lock import live_lock_or_exit  # noqa: E402
from t20_mcp.backends.file_ipc import FileIPCBackend  # noqa: E402
from t20_mcp.tools.tangent import generate_lisp, parse_explode_payload  # noqa: E402

OFF = 1_000_000.0

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
    if not result.ok:
        print(f"[count] blocked/failed: {result.error}")
        return -1
    return result.payload["count"]


async def cleanup_to(backend: FileIPCBackend, target: int) -> tuple[bool, int, object]:
    """Best-effort rollback that also runs after setup or protocol failures."""
    while await count(backend) > target:
        undo = await backend.undo()
        if not undo.ok:
            print(f"[cleanup] undo failed: {undo.error}")
            break
    reset = await backend.execute_lisp(RESET_ENV)
    env = await backend.drawing_get_variables(["CMDACTIVE", "CMDDIA", "FILEDIA", "OSMODE"])
    final = await count(backend)
    env_payload = env.payload if env.ok else {}
    clean = (
        final == target
        and reset.ok
        and env.ok
        and env_payload.get("CMDACTIVE") == 0
        and env_payload.get("CMDDIA") == 1
        and env_payload.get("FILEDIA") == 1
        and env_payload.get("OSMODE") == 0
    )
    print(f"[cleanup] entities={final} reset={reset.ok} env={env_payload}")
    return clean, final, env_payload


async def main() -> int:
    backend = FileIPCBackend()
    init = await backend.initialize()
    if not init.ok:
        print(f"FAIL: initialize: {init.error}")
        return 1

    await backend.execute_lisp(RESET_ENV)
    before = await count(backend)

    checks = {
        "wall_created": False,
        "explode_execute": False,
        "geo": False,
        "coords_translated": False,
        "rollback_clean": False,
    }
    try:
        wall = await backend.execute_lisp(
            generate_lisp(
                "wall",
                {
                    "x1": 0,
                    "y1": 0,
                    "x2": 3000,
                    "y2": 0,
                    "left_width": 120,
                    "right_width": 120,
                    "height": 3000,
                    "wall_type": "砖",
                },
            )
        )
        handle_r = await backend.execute_lisp(
            '(if (entlast) (cdr (assoc 5 (entget (entlast)))) "none")'
        )
        handle = (handle_r.payload or "").strip('"') if handle_r.ok else "none"
        after_wall = await count(backend)
        checks["wall_created"] = wall.ok and handle not in ("none", "")
        print(f"[wall] ok={wall.ok} handle={handle} entities {before}->{after_wall}")

        if checks["wall_created"]:
            code = generate_lisp(
                "explode_read",
                {"handle": handle, "offset_x": OFF, "offset_y": OFF, "max_entities": 50},
            )
            result = await backend.execute_lisp(code)
            checks["explode_execute"] = result.ok
            print(f"[explode_read] ok={result.ok} error={result.error!r}")

            if result.ok:
                parsed = parse_explode_payload(str(result.payload or ""), OFF, OFF)
                print(
                    f"[parsed] rc={parsed['rc']} clean={parsed['clean']} "
                    f"count={parsed['count']} "
                    f"types={[e['type'] for e in parsed['entities']]}"
                )
                lines = [e for e in parsed["entities"] if e["type"] == "LINE"]
                for entity in lines[:6]:
                    print(f"  LINE {entity['points']}")

                checks["geo"] = parsed["rc"] and len(lines) >= 4

                def point_ok(point: list[float]) -> bool:
                    in_outline = -1000 <= point[0] <= 4000 and -1000 <= point[1] <= 1000
                    known_defect_zero = point[0] == -OFF and point[1] == -OFF  # raw (0,0), T20 缺陷
                    return in_outline or known_defect_zero

                coords_ok = all(point_ok(point) for entity in lines for point in entity["points"])
                # 终点侧 (右端 x≈3000) 必须真实存在，证明暂存区平移正确。
                right_side = [
                    point
                    for entity in lines
                    for point in entity["points"]
                    if abs(point[0] - 3000.0) < 1.0
                ]
                checks["coords_translated"] = coords_ok and len(right_side) >= 3
                after_read = await count(backend)
                checks["rollback_clean"] = parsed["clean"] and after_read == after_wall
                print(f"[post] entities={after_read} (期望 {after_wall}, clean={parsed['clean']})")
    finally:
        cleanup_clean, _, _ = await cleanup_to(backend, before)

    checks["cleanup"] = cleanup_clean
    print(f"[verdict] {checks}")
    return 0 if all(checks.values()) else 1


if __name__ == "__main__":
    _lock = live_lock_or_exit(__file__)
    raise SystemExit(asyncio.run(main()))
