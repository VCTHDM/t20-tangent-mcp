"""真机联调 Step 2 — P0-4 真机验收: 错误命令名走 fail 分支且不污染环境.

流程:
  1. 记录执行前 CMDDIA/FILEDIA/OSMODE 与实体数
  2. 下发 prelude + 骨架, 内含不存在的命令名 T20MCPNOSUCHCMD;
     用 USERS1 系统变量回传走了 end 还是 fail 分支
  3. 比对执行后三值与实体数 —— 必须与执行前一致, 且 USERS1 = "fail-branch"

用法: uv run python scripts/itest_02_errorpath.py
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))  # for _live_lock
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from _live_lock import live_lock_or_exit  # noqa: E402
from t20_mcp.backends.file_ipc import FileIPCBackend  # noqa: E402
from t20_mcp.tools.tangent import _load_prelude  # noqa: E402

ENV_VARS = ["CMDDIA", "FILEDIA", "OSMODE", "ATTDIA", "ATTREQ", "EXPERT", "DIMZIN"]

SNIPPET = """
(defun c:t20mcp-errtest ( / t20mcp:saved *error*)
  (setq t20mcp:saved (t20mcp:begin "errtest"))
  (defun *error* (m) (t20mcp:on-error m t20mcp:saved))
  (if (t20mcp:call "T20MCPNOSUCHCMD" (list "L" "100" "200,300" ""))
      (progn (setvar "USERS1" "end-branch") (t20mcp:end "errtest" t20mcp:saved))
      (progn (setvar "USERS1" "fail-branch") (t20mcp:fail "errtest" t20mcp:saved "command-failed-or-unknown")))
  (princ))
(c:t20mcp-errtest)
"""


async def get_state(backend: FileIPCBackend) -> tuple[dict, int]:
    env = await backend.drawing_get_variables(ENV_VARS)
    count = await backend.entity_count()
    assert env.ok and count.ok, f"状态读取失败: {env.error or count.error}"
    return env.payload, count.payload["count"]


async def main() -> int:
    backend = FileIPCBackend()
    init = await backend.initialize()
    if not init.ok:
        print(f"FAIL: initialize: {init.error}")
        return 1

    # 清空 USERS1, 记录执行前状态
    await backend.execute_lisp('(setvar "USERS1" "")')
    env_before, count_before = await get_state(backend)
    print(f"[before] env={env_before} entities={count_before}")

    code = _load_prelude() + "\n" + SNIPPET
    result = await backend.execute_lisp(code)
    print(f"[exec]   ok={result.ok} payload={result.payload!r} error={result.error!r}")

    branch = await backend.drawing_get_variables(["USERS1"])
    env_after, count_after = await get_state(backend)
    print(f"[after]  env={env_after} entities={count_after} branch={branch.payload!r}")

    fail_branch = branch.ok and branch.payload.get("USERS1") == "fail-branch"
    env_same = env_before == env_after
    no_garbage = count_before == count_after

    print()
    print("=== Step2 结果 (P0-4 真机验收) ===")
    print(f"未知命令走 fail 分支:        {'PASS' if fail_branch else 'FAIL'}")
    print(f"环境七值执行前后一致:        {'PASS' if env_same else 'FAIL'}")
    print(f"无新增垃圾实体:              {'PASS' if no_garbage else 'FAIL'}")
    return 0 if (fail_branch and env_same and no_garbage) else 1


if __name__ == "__main__":
    _lock = live_lock_or_exit(__file__)
    raise SystemExit(asyncio.run(main()))
