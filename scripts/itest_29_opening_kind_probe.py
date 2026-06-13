"""真机联调 Step 29 — TCH_OPENING 门/窗类型切换 COM 方法探测.

安装目录调研 (docs/research/2026-06-13_install_dir_prompt_strings.md §7) 发现
ARX 内部符号 SetKind@TDbOpening / SetSubKind@TDbOpening。本脚本探测这些
是否经 ActiveX 暴露为方法/属性 (在自建墙+门上, UNDO 清理):

1. vlax-invoke 候选方法: GetKind/SetKind/GetSubKind/SetSubKind;
2. vlax-get/put 候选属性: Kind/SubKind (再确认 itest_16 结论);
3. 若 SetKind 可调: 调用后回读实体类型/属性变化, 判断是否切到窗。

用法: uv run python scripts/itest_29_opening_kind_probe.py
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.stdout.reconfigure(errors="replace")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from t20_mcp.backends.file_ipc import FileIPCBackend
from t20_mcp.tools.tangent import generate_lisp

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

PROBE = """
(progn
  (setq o (vlax-ename->vla-object (entlast)))
  (setq acc "")
  (foreach m '("GetKind" "GetSubKind" "Kind" "SubKind" "OpeningKind" "InsertMode")
    (setq v (vl-catch-all-apply 'vlax-invoke (list o (read m))))
    (setq acc (strcat acc "inv:" m "="
                      (if (vl-catch-all-error-p v) "<no>" (vl-princ-to-string v)) "; ")))
  (foreach pv '(("SetKind" 1) ("SetSubKind" 1) ("SetKind" 2) ("SetSubKind" 2))
    (setq v (vl-catch-all-apply 'vlax-invoke (list o (read (car pv)) (cadr pv))))
    (setq acc (strcat acc "inv:" (car pv) "(" (itoa (cadr pv)) ")="
                      (if (vl-catch-all-error-p v) "<no>" "OK") "; ")))
  (setq ty (cdr (assoc 0 (entget (entlast)))))
  (setq w (vl-catch-all-apply 'vlax-get-property (list o "Width")))
  (setq acc (strcat acc " finalType=" ty
                    " Width=" (if (vl-catch-all-error-p w)
                                  "<no>" (vl-princ-to-string w))))
  acc)
"""


async def count(backend: FileIPCBackend) -> int:
    r = await backend.entity_count()
    return r.payload["count"] if r.ok else -1


async def main() -> int:
    backend = FileIPCBackend()
    init = await backend.initialize()
    if not init.ok:
        print(f"FAIL: initialize: {init.error}")
        return 1
    await backend.execute_lisp(RESET_ENV)
    before = await count(backend)

    wall = await backend.execute_lisp(
        generate_lisp(
            "wall",
            {"x1": 0, "y1": 0, "x2": 3000, "y2": 0,
             "left_width": 120, "right_width": 120, "height": 3000, "wall_type": "砖"},
        )
    )
    door = await backend.execute_lisp(
        generate_lisp(
            "door",
            {"ins_x": 1500, "ins_y": 0, "width": 1000, "height": 2000, "sill_distance": 0},
        )
    )
    print(f"[setup] wall={wall.ok} door={door.ok} entities {before}->{await count(backend)}")
    if not door.ok:
        print("FAIL: 门创建失败")
        return 1

    probe = await backend.execute_lisp(PROBE)
    print(f"[probe] ok={probe.ok}")
    print(f"  {probe.payload if probe.ok else probe.error}")

    rounds = 0
    while (c := await count(backend)) > before and c >= 0 and rounds < 10:
        undo = await backend.undo()
        rounds += 1
        if not undo.ok:
            break
    reset = await backend.execute_lisp(RESET_ENV)
    env = await backend.drawing_get_variables(["CMDACTIVE", "CMDDIA", "FILEDIA", "OSMODE"])
    print(f"[cleanup] entities={await count(backend)} reset={reset.ok} env={env.payload}")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
