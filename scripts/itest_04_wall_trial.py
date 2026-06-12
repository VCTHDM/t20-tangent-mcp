"""真机联调 Step 4 — wall 行为验证 (§3.1 排程第 1 项).

TGWALL 与 TWALL 在真机均存在 (Step 3), 行为区分: 各自以「两点 + 回车」最小
序列驱动, 比对执行前后实体数与新实体类型 (期望天正墙体 TCH_WALL)。
每次试验后 UNDO 还原, 不在图中留垃圾。

用法: uv run python scripts/itest_04_wall_trial.py
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from t20_mcp.backends.file_ipc import FileIPCBackend
from t20_mcp.tools.tangent import _load_prelude

TRIAL_SNIPPET = """
(defun c:t20mcp-trial ( / t20mcp:saved *error*)
  (setq t20mcp:saved (t20mcp:begin "trial"))
  (defun *error* (m) (t20mcp:on-error m t20mcp:saved))
  (if (t20mcp:call "{CMD}" (list {ARGS}))
      (progn (setvar "USERS1" "end") (t20mcp:end "trial" t20mcp:saved))
      (progn (setvar "USERS1" "fail") (t20mcp:fail "trial" t20mcp:saved "command-failed")))
  (princ))
(c:t20mcp-trial)
"""

LAST_ENT_TYPE = '(if (entlast) (cdr (assoc 0 (entget (entlast)))) "none")'


async def entity_count(backend: FileIPCBackend) -> int:
    r = await backend.entity_count()
    assert r.ok, r.error
    return r.payload["count"]


async def run_trial(backend: FileIPCBackend, cmd: str, args: str) -> None:
    before = await entity_count(backend)
    code = _load_prelude() + "\n" + TRIAL_SNIPPET.replace("{CMD}", cmd).replace("{ARGS}", args)
    result = await backend.execute_lisp(code)
    branch = await backend.drawing_get_variables(["USERS1"])
    after = await entity_count(backend)
    last_type = await backend.execute_lisp(LAST_ENT_TYPE)
    print(f"[{cmd}] exec ok={result.ok} branch={branch.payload.get('USERS1') if branch.ok else '?'} "
          f"entities {before}->{after} last_type={last_type.payload!r} error={result.error!r}")
    if after > before:
        undo = await backend.undo()
        cleaned = await entity_count(backend)
        print(f"  UNDO -> ok={undo.ok}, entities now {cleaned}")


async def main() -> int:
    backend = FileIPCBackend()
    init = await backend.initialize()
    if not init.ok:
        print(f"FAIL: initialize: {init.error}")
        return 1

    # 最小序列: 起点, 终点, 回车结束 (天正绘制墙体记忆面板参数)
    pts = '(t20mcp:pt 0 0) (t20mcp:pt 3000 0) ""'
    for cmd in ("TGWALL", "TWALL"):
        await run_trial(backend, cmd, pts)

    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
