"""真机联调 Step 5 — wall 参数序列验证 + TCH_WALL 实体解剖 + TDIMMP 标注试验.

  A. 用模板当前的推测序列 (L/R/H/T 关键字) 驱动 TGWALL, 验证是否可行
  B. 最小序列画墙后 entget 全量 dump TCH_WALL 组码, 找宽度/高度所在组码
  C. TDIMMP 逐点标注: 试 [点1 点2 回车 位置点] 序列, 看是否生成天正标注

每步后 UNDO 还原。用法: uv run python scripts/itest_05_wall_deep.py
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from t20_mcp.backends.file_ipc import FileIPCBackend
from t20_mcp.tools.tangent import _load_prelude

TRIAL = """
(defun c:t20mcp-trial ( / t20mcp:saved *error*)
  (setq t20mcp:saved (t20mcp:begin "trial"))
  (defun *error* (m) (t20mcp:on-error m t20mcp:saved))
  (if (t20mcp:call "{CMD}" (list {ARGS}))
      (progn (setvar "USERS1" "end") (t20mcp:end "trial" t20mcp:saved))
      (progn (setvar "USERS1" "fail") (t20mcp:fail "trial" t20mcp:saved "command-failed")))
  (princ))
(c:t20mcp-trial)
"""

DUMP_LAST = """
(setq t20mcp:dump "")
(if (entlast)
    (foreach pair (entget (entlast))
      (setq t20mcp:dump
            (strcat t20mcp:dump (vl-princ-to-string pair) " "))))
t20mcp:dump
"""


async def count(backend: FileIPCBackend) -> int:
    r = await backend.entity_count()
    assert r.ok, r.error
    return r.payload["count"]


async def trial(backend: FileIPCBackend, label: str, cmd: str, args: str, undo: bool = True) -> bool:
    before = await count(backend)
    code = _load_prelude() + "\n" + TRIAL.replace("{CMD}", cmd).replace("{ARGS}", args)
    result = await backend.execute_lisp(code)
    branch = await backend.drawing_get_variables(["USERS1"])
    after = await count(backend)
    created = after > before
    print(f"[{label}] ok={result.ok} branch={branch.payload.get('USERS1') if branch.ok else '?'} "
          f"entities {before}->{after} error={result.error!r}")
    if created and undo:
        await backend.undo()
    return created


async def main() -> int:
    backend = FileIPCBackend()
    init = await backend.initialize()
    if not init.ok:
        print(f"FAIL: initialize: {init.error}")
        return 1

    # --- A: 模板当前推测的 L/R/H/T 关键字序列 ---
    guessed = ('"L" "120" "R" "120" "H" "3000" "T" "砖墙" '
               '(t20mcp:pt 0 0) (t20mcp:pt 3000 0) ""')
    await trial(backend, "A TGWALL 推测序列(L/R/H/T)", "TGWALL", guessed)

    # --- B: 最小序列画墙 + 全量 dump ---
    created = await trial(backend, "B TGWALL 最小序列", "TGWALL",
                          '(t20mcp:pt 0 0) (t20mcp:pt 3000 0) ""', undo=False)
    if created:
        dump = await backend.execute_lisp(DUMP_LAST)
        print(f"[B] TCH_WALL entget dump:\n  {dump.payload}")
        await backend.undo()

    # --- C: TDIMMP 逐点标注序列试验 ---
    await trial(backend, "C1 TDIMMP [p1 p2 回车 位置]", "TDIMMP",
                '(t20mcp:pt 0 0) (t20mcp:pt 3000 0) "" (t20mcp:pt 1500 1000)')
    await trial(backend, "C2 TDIMMP [位置 p1 p2 回车]", "TDIMMP",
                '(t20mcp:pt 1500 1000) (t20mcp:pt 0 0) (t20mcp:pt 3000 0) ""')

    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
