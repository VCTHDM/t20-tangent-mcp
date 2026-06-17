"""一次性探针: 窗模式下用 3 个不同 sill_height (600/1200/300) 插入窗,
回读 DoorSill 与传入参数比对 + DXF group71=1 校验。

仅用于 D1 闭合证据采集; 跑完即可删除或归档。本脚本走与 itest_35 相同的
入口 (FileIPCBackend + tangent.generate_lisp), 不引入新逻辑。
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

RESET = (
    '(progn (setq n 0)'
    ' (while (and (< n 8) (> (getvar "CMDACTIVE") 0)) (command) (setq n (1+ n)))'
    ' (setvar "CMDDIA" 1) (setvar "FILEDIA" 1) (setvar "OSMODE" 0) "rst")'
)

RB_LISP = '''
(setq t20mcp:rb-etyp "no-entity" t20mcp:rb-w nil t20mcp:rb-h nil t20mcp:rb-ds nil t20mcp:rb-g71 nil)
(if (entlast)
  (progn
    (setq t20mcp:rb-etyp (cdr (assoc 0 (entget (entlast)))))
    (setq t20mcp:rb-g71 (cdr (assoc 71 (entget (entlast)))))
    (setq o (vlax-ename->vla-object (entlast)))
    (setq t20mcp:rb-w  (vl-catch-all-apply 'vlax-get-property (list o "Width")))
    (setq t20mcp:rb-h  (vl-catch-all-apply 'vlax-get-property (list o "Height")))
    (setq t20mcp:rb-ds (vl-catch-all-apply 'vlax-get-property (list o "DoorSill")))))
(strcat "type=" (vl-prin1-to-string t20mcp:rb-etyp)
        " g71=" (vl-prin1-to-string t20mcp:rb-g71)
        " W="  (vl-prin1-to-string t20mcp:rb-w)
        " H="  (vl-prin1-to-string t20mcp:rb-h)
        " DS=" (vl-prin1-to-string t20mcp:rb-ds))
'''


async def count(b: FileIPCBackend) -> int:
    r = await b.entity_count()
    return r.payload["count"] if r.ok else -1


async def main() -> int:
    b = FileIPCBackend()
    init = await b.initialize()
    if not init.ok:
        print(f"FAIL init: {init.error}")
        return 1
    await b.execute_lisp(RESET)
    # baseline cleanup
    for _ in range(8):
        if await count(b) <= 0:
            break
        await b.undo()
    base = await count(b)
    print(f"baseline={base}")

    # wall
    wall = generate_lisp("wall", {
        "x1": 0, "y1": 0, "x2": 6000, "y2": 0,
        "left_width": 240, "right_width": 120,
        "height": 3300, "wall_type": "砖",
    })
    wr = await b.execute_lisp(wall)
    print(f"wall ok={wr.ok} count->{await count(b)}")

    sweep = [
        # (sill_height, width, height, ins_x)
        (600.0, 800.0, 1500.0, 1000.0),
        (1200.0, 600.0, 1800.0, 2500.0),
        (300.0, 1200.0, 1500.0, 4000.0),
    ]

    results = []
    try:
        for sh, w, h, ix in sweep:
            params = {"ins_x": ix, "ins_y": 0.0, "width": w, "height": h, "sill_height": sh}
            code = generate_lisp("window", params)
            r = await b.execute_lisp(code)
            rb = await b.execute_lisp(RB_LISP)
            print(f"  [sh={sh} w={w} h={h} ix={ix}] ok={r.ok} -> {rb.payload}")
            results.append((sh, w, h, ix, rb.payload or ""))
    finally:
        # cleanup
        for _ in range(20):
            if await count(b) <= base:
                break
            await b.undo()
        await b.execute_lisp(RESET)
        print(f"final={await count(b)} (baseline {base})")

    print()
    print("=== sweep summary ===")
    all_pass = True
    for sh, w, h, ix, p in results:
        ds_ok = f"DS={sh}" in p
        g71_ok = "g71=1" in p
        type_ok = 'type="TCH_OPENING"' in p
        ok = ds_ok and g71_ok and type_ok
        all_pass = all_pass and ok
        verdict = "PASS" if ok else "FAIL"
        print(f"  sh={sh:7.1f} W={w:6.1f} H={h:6.1f}  -> {verdict}  ({p})")
    print()
    print(f"overall: {'PASS' if all_pass else 'FAIL'}")
    return 0 if all_pass else 2


if __name__ == "__main__":
    _lock = live_lock_or_exit(__file__)
    raise SystemExit(asyncio.run(main()))
