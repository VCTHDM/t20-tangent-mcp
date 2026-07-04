"""真机验证: 门/窗图层修复 (door->DOOR_FIRE, window->WINDOW)."""

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


async def main() -> int:
    backend = FileIPCBackend()
    init = await backend.initialize()
    if not init.ok:
        print(f"FAIL: initialize: {init.error}")
        return 1

    # 清场
    await backend.execute_lisp('(progn (command "_.ERASE" "_ALL" "") (princ))')
    await backend.execute_lisp('(setvar "OSMODE" 0)')

    # 画一面墙
    await backend.execute_lisp(generate_lisp(
        "wall", {"x1": 0, "y1": 0, "x2": 6000, "y2": 0,
                 "left_width": 120, "right_width": 120, "height": 3000, "wall_type": "砖"},
    ))

    # 画一个门
    r1 = await backend.execute_lisp(generate_lisp(
        "door", {"ins_x": 2000, "ins_y": 0, "width": 900, "height": 2100},
    ))
    print(f"door exec: ok={r1.ok}")

    # 画一个窗
    r2 = await backend.execute_lisp(generate_lisp(
        "window", {"ins_x": 4000, "ins_y": 0, "width": 1500, "height": 1500, "sill_height": 900},
    ))
    print(f"window exec: ok={r2.ok}")

    # 回读两个 TCH_OPENING 的图层和 DoorSill
    check_code = '''
(progn
  (vl-load-com)
  (setq ss (ssget "X" (quote ((0 . "TCH_OPENING")))))
  (setq n (sslength ss))
  (setq i 0)
  (setq out "")
  (while (< i n)
    (setq e (ssname ss i))
    (setq o (vlax-ename->vla-object e))
    (setq ly (vl-catch-all-apply (quote vlax-get-property) (list o "Layer")))
    (setq ds (vl-catch-all-apply (quote vlax-get-property) (list o "DoorSill")))
    (setq wd (vl-catch-all-apply (quote vlax-get-property) (list o "Width")))
    (setq out (strcat out "layer=" (if (vl-catch-all-error-p ly) "<no>" (vl-princ-to-string ly))
                     " DoorSill=" (if (vl-catch-all-error-p ds) "<no>" (vl-princ-to-string ds))
                     " Width=" (if (vl-catch-all-error-p wd) "<no>" (vl-princ-to-string wd))
                     " | "))
    (setq i (1+ i)))
  out)
'''
    r = await backend.execute_lisp(check_code)
    print(f"\n=== TCH_OPENING 回读 ===")
    print(f"payload: {r.payload}")

    # 判断
    payload = str(r.payload)
    door_ok = "DOOR_FIRE" in payload and "DoorSill=0.0" in payload
    window_ok = "WINDOW" in payload and "DoorSill=900.0" in payload
    print(f"\n门在 DOOR_FIRE 图层: {'PASS' if door_ok else 'FAIL'}")
    print(f"窗在 WINDOW 图层: {'PASS' if window_ok else 'FAIL'}")

    # cleanup
    await backend.execute_lisp('(progn (command "_.ERASE" "_ALL" "") (princ))')
    return 0 if door_ok and window_ok else 1


if __name__ == "__main__":
    _lock = live_lock_or_exit(__file__)
    raise SystemExit(asyncio.run(main()))
