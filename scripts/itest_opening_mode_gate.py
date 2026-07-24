"""真机验证门窗面板模式门禁、错误实体回滚与正确模式重试。

每次调用只验证一个请求/预期组合，便于在两次调用之间切换天正门窗面板：

    uv run python scripts/itest_opening_mode_gate.py --requested window --expect mismatch
    uv run python scripts/itest_opening_mode_gate.py --requested window --expect ok

脚本在现有图纸上追加一面远离原点的临时墙，并通过 UNDO 恢复到基线实体数；
不会清空图纸。四个组合（window mismatch/ok、door mismatch/ok）共同构成
Handoff 38 的双向证据。
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

sys.stdout.reconfigure(errors="replace")
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from _live_lock import live_lock_or_exit  # noqa: E402
from t20_mcp.backends.file_ipc import FileIPCBackend  # noqa: E402
from t20_mcp.tools.tangent import (  # noqa: E402
    generate_lisp,
    parse_opening_status,
)


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

LAST_ENTITY = """
(if (entlast)
  (progn
    (setq e (entlast) ed (entget e))
    (strcat
      "type=" (cdr (assoc 0 ed))
      "|layer=" (cdr (assoc 8 ed))
      "|group71="
      (if (assoc 71 ed) (itoa (cdr (assoc 71 ed))) "none")))
  "type=none|layer=none|group71=none")
"""


async def count(backend: FileIPCBackend) -> int:
    result = await backend.entity_count()
    if not result.ok:
        raise RuntimeError(result.error or "entity_count failed")
    return int(result.payload["count"])


async def cleanup_to(backend: FileIPCBackend, target: int) -> tuple[bool, int]:
    """Undo only operations made by this probe and verify the original count."""
    guard = 0
    current = await count(backend)
    while current > target and guard < 12:
        result = await backend.undo()
        if not result.ok:
            break
        current = await count(backend)
        guard += 1
    await backend.execute_lisp(RESET_ENV)
    final = await count(backend)
    return final == target, final


async def main(requested: str, expect: str) -> int:
    backend = FileIPCBackend()
    init = await backend.initialize()
    if not init.ok:
        print(f"FAIL: initialize: {init.error}")
        return 1

    await backend.execute_lisp(RESET_ENV)
    base = await count(backend)
    expected_group71 = 0 if requested == "door" else 1
    actual_group71 = 1 - expected_group71 if expect == "mismatch" else expected_group71
    x0 = 870000 if requested == "door" else 880000

    checks: dict[str, bool] = {}
    notes: dict[str, object] = {}
    try:
        wall = await backend.execute_lisp(
            generate_lisp(
                "wall",
                {
                    "x1": x0,
                    "y1": 870000,
                    "x2": x0 + 6000,
                    "y2": 870000,
                    "left_width": 120,
                    "right_width": 120,
                    "height": 3000,
                    "wall_type": "砖",
                },
            )
        )
        wall_count = await count(backend)
        checks["temporary_wall_created"] = wall.ok and wall_count == base + 1

        data = {
            "ins_x": x0 + 3000,
            "ins_y": 870000,
            "width": 1200 if requested == "window" else 900,
            "height": 1500 if requested == "window" else 2100,
        }
        if requested == "window":
            data["sill_height"] = 900
        else:
            data["sill_distance"] = 0

        before = await count(backend)
        result = await backend.execute_lisp(generate_lisp(requested, data))
        after = await count(backend)
        status = parse_opening_status(result.payload)
        last = await backend.execute_lisp(LAST_ENTITY)
        last_payload = str(last.payload or "")
        notes.update(
            {
                "base": base,
                "before_opening": before,
                "after_opening": after,
                "status": status,
                "last_entity": last_payload,
            }
        )

        checks["execute_lisp_completed"] = result.ok
        checks["requested_mode_echoed"] = status.get("requested") == requested
        if expect == "mismatch":
            checks["mismatch_detected"] = status.get("status") == "MODE-MISMATCH"
            checks["actual_mode_is_opposite"] = (
                status.get("actual") == str(actual_group71)
            )
            checks["wrong_entity_rolled_back"] = status.get("rollback") == "ok"
            checks["entity_count_unchanged"] = after == before
        else:
            checks["correct_mode_accepted"] = status.get("status") == "OK"
            checks["actual_mode_matches"] = (
                status.get("actual") == str(actual_group71)
            )
            checks["entity_count_incremented"] = after == before + 1
            checks["entity_type"] = "type=TCH_OPENING" in last_payload
            checks["group71"] = f"group71={expected_group71}" in last_payload
    finally:
        clean, final = await cleanup_to(backend, base)
        checks["cleanup_to_baseline"] = clean
        notes["final"] = final

    print(f"=== opening mode gate: requested={requested} expect={expect} ===")
    for name, passed in checks.items():
        print(f"  {name:32s} {'PASS' if passed else 'FAIL'}")
    print("evidence:", notes)
    return 0 if checks and all(checks.values()) else 1


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--requested", choices=("door", "window"), required=True)
    parser.add_argument("--expect", choices=("ok", "mismatch"), required=True)
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    _lock = live_lock_or_exit(__file__)
    raise SystemExit(asyncio.run(main(args.requested, args.expect)))
