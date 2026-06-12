"""真机联调 Step 7 — export_t3 / door,window / axis_grid 行为试验 (§3.1 第 2/3 项).

  A. TSAVEAS (图形导出): FILEDIA=0 下试命令行驱动, 验证是否产出 .dwg 文件
     (若弹天正自绘文件框, 本次 dispatch 会超时, 需人工关框 —— 即编目坑 1 成立)
  B. TOPENING (门窗): 先画一段墙, 在墙中点插门窗, 看是否生成 TCH_OPENING
  C. TRECTAXIS (直线轴网): 最小驱动试验, 看是否可命令行化

用法: uv run python scripts/itest_07_export_opening_axis.py
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from t20_mcp.backends.file_ipc import FileIPCBackend
from t20_mcp.config import IPC_DIR
from t20_mcp.tools.tangent import _load_prelude

TRIAL = """
(defun c:t20mcp-trial ( / t20mcp:saved *error*)
  (setq t20mcp:saved (t20mcp:begin "trial"))
  (defun *error* (m) (t20mcp:on-error m t20mcp:saved))
  (if (t20mcp:call "{CMD}" (list {ARGS}))
      (t20mcp:end "trial" t20mcp:saved)
      (t20mcp:fail "trial" t20mcp:saved "command-failed"))
  (princ))
(c:t20mcp-trial)
"""

LAST_TYPE = '(if (entlast) (cdr (assoc 0 (entget (entlast)))) "none")'


async def count(backend: FileIPCBackend) -> int:
    r = await backend.entity_count()
    assert r.ok, r.error
    return r.payload["count"]


async def trial(backend: FileIPCBackend, label: str, cmd: str, args: str) -> int:
    """执行试验, 返回实体增量 (超时返回 -1)。"""
    before = await count(backend)
    code = _load_prelude() + "\n" + TRIAL.replace("{CMD}", cmd).replace("{ARGS}", args)
    result = await backend.execute_lisp(code)
    if not result.ok and "Timeout" in (result.error or ""):
        print(f"[{label}] TIMEOUT —— 命令可能弹出了对话框, 请在 AutoCAD 中手动关闭!")
        return -1
    after = await count(backend)
    last_type = await backend.execute_lisp(LAST_TYPE)
    print(f"[{label}] ok={result.ok} entities {before}->{after} "
          f"last={last_type.payload!r} error={result.error!r}")
    return after - before


async def main() -> int:
    backend = FileIPCBackend()
    init = await backend.initialize()
    if not init.ok:
        print(f"FAIL: initialize: {init.error}")
        return 1

    # --- A: TSAVEAS 图形导出 ---
    out = (Path(IPC_DIR) / "itest_export_t3.dwg")
    out.unlink(missing_ok=True)
    out_lisp = str(out).replace("\\", "/")
    delta = await trial(backend, "A TSAVEAS [路径]", "TSAVEAS", f'"{out_lisp}"')
    if delta >= 0:
        print(f"  导出文件存在: {out.exists()}")

    # --- B: TOPENING 门窗 (需先有墙) ---
    await trial(backend, "B0 画墙备用", "TGWALL", '(t20mcp:pt 0 0) (t20mcp:pt 3000 0) ""')
    delta = await trial(backend, "B1 TOPENING [墙中点]", "TOPENING", '(t20mcp:pt 1500 0) ""')
    # 清理: 先撤门窗(若有), 再撤墙
    if delta > 0:
        await backend.undo()
    await backend.undo()
    print(f"  清理后实体数: {await count(backend)}")

    # --- C: TRECTAXIS 直线轴网 ---
    delta = await trial(backend, "C TRECTAXIS 最小试验", "TRECTAXIS", '""')
    if delta > 0:
        await backend.undo()

    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
