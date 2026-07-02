"""真机联调 Step 39 — tangent.column (TGColumn 面板 UI 自动化) E2E.

历史 (Handoff 36):
    Gate B 探针 (本脚本前身, 原始证据 docs/handoff/36_tgcolumn_gate_b_raw.txt)
    真机证实: WM_SETTEXT+通知补发 可写面板 Edit/Combo, 命令行 WM_CHAR 打坐标
    可落 TCH_COLUMN, 五参数 COM 读回精确匹配。原语已提炼进
    src/t20_mcp/dialog_automation.py, 编排在 tangent.execute_column。
    本脚本改为走库路径 (与 MCP 工具同一代码), 防止探针/库实现漂移。

用例:
    1. full   — 五参数全指定 (height=3300 rotation=45 sec 500x400 材料=金属),
                读回精确匹配。
    2. minimal — 只给 x/y (其余走面板记忆值), 实体生成且类型正确。
    3. badmat — 非法 material 参数被 ParamError 拒绝 (离线路径, 不接触面板)。

cleanup 铁律: 每例撤回 baseline + CMDACTIVE=0/CMDDIA=1/FILEDIA=1/OSMODE=0
+ 无残留 #32770 面板。

用法: uv run python scripts/itest_39_column_gate_b_e2e.py
返回码: 0=全部 PASS, 2=任一 FAIL
"""

from __future__ import annotations

import asyncio
import re
import sys
from pathlib import Path

sys.stdout.reconfigure(errors="replace")
sys.path.insert(0, str(Path(__file__).resolve().parent))  # for _live_lock
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import win32process  # noqa: E402

from _live_lock import live_lock_or_exit  # noqa: E402
from t20_mcp.backends.file_ipc import FileIPCBackend  # noqa: E402
from t20_mcp.dialog_automation import find_acad_popups  # noqa: E402
from t20_mcp.tools.tangent import ParamError, execute_column  # noqa: E402

RESET_ENV = (
    '(progn (setq n 0)'
    ' (while (and (< n 8) (> (getvar "CMDACTIVE") 0)) (command) (setq n (1+ n)))'
    ' (setvar "CMDDIA" 1) (setvar "FILEDIA" 1) (setvar "OSMODE" 0)'
    ' (setvar "LOGFILEMODE" 0)'
    ' (strcat "rst CMDACTIVE=" (itoa (getvar "CMDACTIVE"))))'
)
ENV_VARS = ["CMDACTIVE", "CMDDIA", "FILEDIA", "OSMODE"]


async def count(b: FileIPCBackend) -> int:
    r = await b.entity_count()
    return r.payload["count"] if r.ok else -1


async def cleanup(backend: FileIPCBackend, base: int, pid: int, base_modals: set[int]) -> bool:
    rounds = 0
    while rounds < 16:
        c = await count(backend)
        if c <= base or c < 0:
            break
        u = await backend.undo()
        if not u.ok:
            break
        rounds += 1
    final = await count(backend)
    await backend.execute_lisp(RESET_ENV)
    env = await backend.drawing_get_variables(ENV_VARS)
    residual = [h for h in find_acad_popups(pid) if h not in base_modals]
    print(f"[cleanup] rounds={rounds} final={final} (baseline {base}) "
          f"env={env.payload} residual={residual}")
    return (
        final == base
        and env.ok
        and env.payload.get("CMDACTIVE") == 0
        and env.payload.get("CMDDIA") == 1
        and env.payload.get("FILEDIA") == 1
        and env.payload.get("OSMODE") == 0
        and not residual
    )


def rb_val(payload: str, key: str) -> str:
    m = re.search(rf"{key}=(\S+)", payload)
    return m.group(1) if m else "?"


async def main() -> int:
    backend = FileIPCBackend()
    init = await backend.initialize()
    if not init.ok:
        print(f"FAIL init: {init.error}")
        return 2
    _, pid = win32process.GetWindowThreadProcessId(backend._hwnd)

    guard = 0
    while await count(backend) > 0 and guard < 8:
        await backend.undo()
        guard += 1
    await backend.execute_lisp(RESET_ENV)
    base_modals = set(find_acad_popups(pid))
    print(f"start clean: entity={await count(backend)} (undo x{guard})")

    results: list[tuple[str, bool]] = []

    # --- case 1: full 五参数 ---
    base = await count(backend)
    print(f"\n===== [full] baseline={base} =====")
    ok = False
    try:
        r = await execute_column(backend, {
            "x": 20000, "y": 15000, "height": 3300, "rotation": 45,
            "sec_w": 500, "sec_h": 400, "material": "金属",
        })
        print(f"[full] ok={r.ok} payload={r.payload!r} error={r.error!r}")
        if r.ok:
            rb = str(r.payload.get("readback", ""))
            checks = {
                "type": "type=TCH_COLUMN" in rb,
                "H": rb_val(rb, "H") == "3300.0",
                "R": rb_val(rb, "R") == "45.0",
                "W": rb_val(rb, "W") == "500.0",
                "D": rb_val(rb, "D") == "400.0",
                "S": rb_val(rb, "S") == '"金属"',
            }
            print(f"[full] readback checks: {checks}")
            ok = all(checks.values())
    finally:
        clean = await cleanup(backend, base, pid, base_modals)
        results.append(("full 五参数精确匹配", ok and clean))

    # --- case 2: minimal 仅 x/y ---
    base = await count(backend)
    print(f"\n===== [minimal] baseline={base} =====")
    ok = False
    try:
        r = await execute_column(backend, {"x": 25000, "y": 15000})
        print(f"[minimal] ok={r.ok} payload={r.payload!r} error={r.error!r}")
        ok = r.ok and "type=TCH_COLUMN" in str(r.payload.get("readback", "")) if r.ok else False
    finally:
        clean = await cleanup(backend, base, pid, base_modals)
        results.append(("minimal 仅坐标", ok and clean))

    # --- case 3: badmat 参数拒绝 (不触真机) ---
    base = await count(backend)
    try:
        await execute_column(backend, {"x": 0, "y": 0, "material": "木头"})
        results.append(("badmat ParamError 拒绝", False))
        print("\n[badmat] FAIL: 未拒绝非法 material")
    except ParamError as e:
        after = await count(backend)
        print(f"\n[badmat] ParamError 如期拒绝: {e} (entity delta={after - base})")
        results.append(("badmat ParamError 拒绝", after == base))

    print("\n=== Step39 tangent.column E2E 总结 ===")
    all_ok = True
    for name, passed in results:
        print(f"  [{'PASS' if passed else 'FAIL'}] {name}")
        all_ok = all_ok and passed
    return 0 if all_ok else 2


if __name__ == "__main__":
    _lock = live_lock_or_exit(__file__)
    raise SystemExit(asyncio.run(main()))
