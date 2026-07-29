"""真机验证门窗面板模式全自动切换（无人工点击）。

链路:
  FileIPC 启动 TOpening → Win32 识别「门窗参数」ToolbarWindow32 →
  后台鼠标消息切换插窗/插门 → 空回车退出 → opening.lsp 正式创建 →
  DXF group71 最终门禁。

脚本在远离原点处创建一面临时墙，依次自动插窗、插门，再 UNDO 回到基线；
不清空也不保存用户图纸。
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.stdout.reconfigure(errors="replace")
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from _live_lock import live_lock_or_exit  # noqa: E402
from t20_mcp import dialog_automation as da  # noqa: E402
from t20_mcp.backends.file_ipc import FileIPCBackend  # noqa: E402
from t20_mcp.tools.tangent import (  # noqa: E402
    execute_opening,
    generate_lisp,
    parse_opening_status,
)


RESET_ENV = """
(progn
  (setq n 0)
  (while (and (< n 8) (> (getvar "CMDACTIVE") 0))
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
    current = await count(backend)
    rounds = 0
    while current > target and rounds < 12:
        undo = await backend.undo()
        if not undo.ok:
            break
        current = await count(backend)
        rounds += 1
    await backend.execute_lisp(RESET_ENV)
    final = await count(backend)
    return final == target, final


async def main() -> int:
    import win32process

    backend = FileIPCBackend()
    init = await backend.initialize()
    if not init.ok:
        print(f"FAIL: initialize: {init.error}")
        return 1

    await backend.execute_lisp(RESET_ENV)
    base = await count(backend)
    _, acad_pid = win32process.GetWindowThreadProcessId(backend._hwnd)
    x0 = 920000
    y0 = 920000
    checks: dict[str, bool] = {}
    evidence: dict[str, object] = {"base": base}

    try:
        wall = await backend.execute_lisp(
            generate_lisp(
                "wall",
                {
                    "x1": x0,
                    "y1": y0,
                    "x2": x0 + 12000,
                    "y2": y0,
                    "left_width": 120,
                    "right_width": 120,
                    "height": 3000,
                    "wall_type": "砖",
                },
            )
        )
        checks["temporary_wall_created"] = wall.ok and await count(backend) == base + 1

        cases = (
            (
                "window",
                {
                    "ins_x": x0 + 3500,
                    "ins_y": y0,
                    "width": 1500,
                    "height": 1500,
                    "sill_height": 900,
                },
                1,
                "WINDOW",
            ),
            (
                "door",
                {
                    "ins_x": x0 + 8500,
                    "ins_y": y0,
                    "width": 900,
                    "height": 2100,
                    "sill_distance": 0,
                },
                0,
                "DOOR_FIRE",
            ),
        )
        for operation, data, expected_group71, expected_layer in cases:
            before = await count(backend)
            result = await execute_opening(backend, operation, data)
            after = await count(backend)
            status = parse_opening_status(result.payload)
            last = await backend.execute_lisp(LAST_ENTITY)
            last_payload = str(last.payload or "")

            checks[f"{operation}_execute"] = result.ok
            checks[f"{operation}_status"] = status.get("status") == "OK"
            checks[f"{operation}_group71"] = (
                status.get("actual") == str(expected_group71)
                and f"group71={expected_group71}" in last_payload
            )
            checks[f"{operation}_layer"] = f"layer={expected_layer}" in last_payload
            checks[f"{operation}_delta"] = after == before + 1
            checks[f"{operation}_panel_closed"] = da.find_opening_panel(acad_pid) is None
            evidence[operation] = {
                "status": status,
                "last": last_payload,
                "before": before,
                "after": after,
            }
    finally:
        clean, final = await cleanup_to(backend, base)
        checks["cleanup_to_baseline"] = clean
        evidence["final"] = final

    print("=== opening panel automatic mode switch ===")
    for name, passed in checks.items():
        print(f"  {name:32s} {'PASS' if passed else 'FAIL'}")
    print("evidence:", evidence)
    return 0 if checks and all(checks.values()) else 1


if __name__ == "__main__":
    _lock = live_lock_or_exit(__file__)
    raise SystemExit(asyncio.run(main()))
