"""真机联调收尾 — 删除测试图层 (COM 方式, 不走命令行避免挂起), 复位环境.

用法: uv run python scripts/itest_14_cleanup.py
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.stdout.reconfigure(errors="replace")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from t20_mcp.backends.file_ipc import FileIPCBackend

CLEANUP = """
(progn
  (setvar "CMDDIA" 1)
  (setvar "FILEDIA" 1)
  (setq t20mcp:layers (vla-get-Layers
                        (vla-get-ActiveDocument (vlax-get-acad-object))))
  (setq t20mcp:r (vl-catch-all-apply
                   '(lambda ()
                      (vla-Delete (vla-Item t20mcp:layers "T20MCP测试图层")))))
  (if (vl-catch-all-error-p t20mcp:r) "layer-delete-skipped" "layer-deleted"))
"""


async def main() -> int:
    backend = FileIPCBackend()
    init = await backend.initialize()
    if not init.ok:
        print(f"FAIL: initialize: {init.error}")
        return 1
    r = await backend.execute_lisp(CLEANUP)
    env = await backend.drawing_get_variables(["CMDDIA", "FILEDIA", "CMDACTIVE"])
    cnt = await backend.entity_count()
    print(f"cleanup={r.payload!r} env={env.payload} entities={cnt.payload}")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
