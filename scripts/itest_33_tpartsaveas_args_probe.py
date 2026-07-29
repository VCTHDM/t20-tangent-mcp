"""真机联调 Step 33 — TPartSaveAs 局部导出参数形态窄探针.

目标 (Handoff 32 P1-A 路线):
    找出 TPartSaveAs (天正"局部存盘") 是否存在可静默导出的参数形态。

铁律:
    1. 不向任何 #32770 / WPF 模态框发 WM_CLOSE; 恢复只用 ESC + 命令取消。
    2. 不把 vl-cmdf 返回值 / clean exit 当成功; 成功判据 = 真实输出文件存在
       + CMDACTIVE 归零 + CMDDIA/FILEDIA/OSMODE 恢复 + 无残留模态框。
    3. 每次只试一个参数形态; 出现 modal 立即停止该路线。
    4. 探针, 不是 wrapper; 不写入 SUBCOMMANDS, 不动 dialog_automation.py。

阶段:
    Phase A (no-arg) — getcname 注册确认 + 命令存在性。
    Phase B (path-only) — vl-cmdf "TPartSaveAs" "<path>" "" 单参数形态;
        若立即弹 #32770, 记录后 ESC 返回, 路线判定阻塞。
    Phase C (selection-set + path) — 已通过 LOGFILEMODE 捕获到提示
        "请选择要导出的对象<退出>:", 证明 TPartSaveAs 是 selection-first 命令;
        本阶段先创建一道临时 TCH_WALL, 再 (ssget "_X") 全选, 配合
        FILEDIA=0 + 路径字符串, 看是否能静默落地 dwg。
    后续 (selection-set + path) 仅在 Phase B 给出"需要选择对象"线索后才尝试,
        本次脚本不预先尝试。

用法:
    uv run python scripts/itest_33_tpartsaveas_args_probe.py phase_a
    uv run python scripts/itest_33_tpartsaveas_args_probe.py phase_b
    uv run python scripts/itest_33_tpartsaveas_args_probe.py phase_c
"""

from __future__ import annotations

import asyncio
import ctypes
import os
import sys
import time
from pathlib import Path

sys.stdout.reconfigure(errors="replace")
sys.path.insert(0, str(Path(__file__).resolve().parent))  # for _live_lock
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import win32gui
import win32process

from _live_lock import live_lock_or_exit  # noqa: E402
from t20_mcp.backends.file_ipc import FileIPCBackend  # noqa: E402
from t20_mcp.tools.tangent import _load_prelude  # noqa: E402

RESET_ENV = (
    "(progn (setq n 0)"
    ' (while (and (< n 8) (> (getvar "CMDACTIVE") 0)) (command) (setq n (1+ n)))'
    ' (setvar "CMDDIA" 1) (setvar "FILEDIA" 1) (setvar "OSMODE" 0) "rst")'
)

# 阶段 A: 仅检查命令是否注册, 不启动它。
PHASE_A_LISP = (
    _load_prelude() + "\n(progn"
    '  (setq cn (getcname "TPartSaveAs"))'
    '  (princ (strcat "\\n@@@CNAME=" (vl-prin1-to-string cn) "@@@\\n"))'
    '  (strcat "cname=" (vl-prin1-to-string cn)))'
)


def build_phase_b_lisp(out_path: str) -> str:
    """阶段 B: 仅试 path-only 参数形态; vl-catch-all 包裹防 LISP 异常。"""
    safe = out_path.replace("\\", "/").replace('"', '\\"')
    return (
        _load_prelude()
        + f'''
(defun c:t20mcp-tpsa ( / *error*)
  (defun *error* (m) (princ (strcat "\\nT20MCP-PSA-ERR " (if m m "?"))))
  (setvar "CMDECHO" 1)
  (setvar "FILEDIA" 0)   ;; 期望: 命令行参数若被支持, 应跳过对话框
  (princ "\\n@@@PROBE-START@@@\\n")
  (vl-catch-all-apply 'vl-cmdf (list "TPartSaveAs" "{safe}" ""))
  (princ (strcat "\\n@@@AFTER active=" (itoa (getvar "CMDACTIVE")) "@@@\\n"))
  (princ))
(c:t20mcp-tpsa)
(strcat "active=" (itoa (getvar "CMDACTIVE")))
'''
    )


def command_target_hwnd(main_hwnd: int) -> int:
    mdi: list[int] = []

    def cb(h, _):
        if win32gui.GetClassName(h) == "MDIClient":
            mdi.append(h)
            return False
        return True

    win32gui.EnumChildWindows(main_hwnd, cb, None)
    return mdi[0] if mdi else main_hwnd


def post_escape(hwnd: int, times: int = 4) -> None:
    pm = ctypes.windll.user32.PostMessageW
    for _ in range(times):
        pm(hwnd, 0x0100, 0x1B, 0)
        pm(hwnd, 0x0101, 0x1B, 0)


def popup_classes(pid: int) -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []

    def cb(h, _):
        if win32gui.IsWindowVisible(h):
            _, wp = win32process.GetWindowThreadProcessId(h)
            if wp == pid:
                cls = win32gui.GetClassName(h)
                title = win32gui.GetWindowText(h)
                if (
                    cls in ("#32770",)
                    or "WPF" in cls
                    or "天正" in title
                    or ".dwg" not in title.lower()
                ):
                    out.append((cls, title))
        return True

    win32gui.EnumWindows(cb, None)
    return out


async def assert_env_clean(backend: FileIPCBackend) -> dict:
    env = await backend.drawing_get_variables(["CMDACTIVE", "CMDDIA", "FILEDIA", "OSMODE"])
    return env.payload if env.ok else {}


async def phase_a(backend: FileIPCBackend) -> int:
    print("=== Phase A: getcname 注册确认 ===")
    r = await backend.execute_lisp(PHASE_A_LISP)
    print(f"  ok={r.ok} payload={r.payload!r} error={r.error!r}")
    cname = r.payload or ""
    registered = "nil" not in cname.lower() and "TPartSaveAs".lower() in cname.lower()
    print(f"  registered: {'PASS' if registered else 'FAIL'} (payload={cname})")
    env = await assert_env_clean(backend)
    print(f"  env={env}")
    return 0 if registered else 1


async def phase_b(backend: FileIPCBackend) -> int:
    out = Path(os.environ.get("TEMP", ".")) / "t20_mcp_tpartsaveas_probe.dwg"
    if out.exists():
        out.unlink()
    print(f"=== Phase B: path-only 形态; 目标输出 {out} ===")

    _, pid = win32process.GetWindowThreadProcessId(backend._hwnd)
    pre_popups = popup_classes(pid)
    pre_env = await assert_env_clean(backend)
    print(f"  pre env={pre_env} pre_popups={pre_popups}")

    r = await backend.execute_lisp(build_phase_b_lisp(str(out)))
    print(f"  cmdf ok={r.ok} payload={r.payload!r} error={r.error!r}")
    time.sleep(0.8)
    mid_popups = popup_classes(pid)
    print(f"  mid_popups={mid_popups}")

    # 强制 ESC-only 恢复 (无论是否弹框)
    target = command_target_hwnd(backend._hwnd)
    for _ in range(3):
        post_escape(target, 4)
        time.sleep(0.3)
    await backend.execute_lisp(RESET_ENV)
    time.sleep(0.4)

    post_popups = popup_classes(pid)
    post_env = await assert_env_clean(backend)
    file_ok = out.exists() and out.stat().st_size > 0
    print(f"  post_popups={post_popups}")
    print(f"  post env={post_env}")
    print(f"  output_file_exists={file_ok} ({out})")

    has_modal_during = any(c == "#32770" for c, _ in mid_popups)
    has_modal_left = any(c == "#32770" for c, _ in post_popups)
    env_clean = (
        post_env.get("CMDACTIVE") == 0
        and post_env.get("CMDDIA") == 1
        and post_env.get("FILEDIA") == 1
    )

    print()
    print("=== Phase B verdict ===")
    print(f"  弹 #32770 期间        : {'YES' if has_modal_during else 'no'}")
    print(f"  事后残留 #32770       : {'YES' if has_modal_left else 'no'}")
    print(f"  输出文件真实存在      : {'YES' if file_ok else 'no'}")
    print(f"  环境干净 (cmd/dia等)  : {'YES' if env_clean else 'no'}")

    # 成功判据 (导出类): 输出文件 + 环境干净 + 无 modal 残留
    success = file_ok and env_clean and not has_modal_left
    # 阻塞判据: 期间弹 #32770 + 无文件 -> path-only 形态需要对话框, 路线阻塞
    blocked_by_modal = has_modal_during and not file_ok
    print(
        f"  -> 结论: {'SUCCESS' if success else ('BLOCKED-by-#32770' if blocked_by_modal else 'INDETERMINATE')}"
    )
    return 0


def build_phase_c_lisp(out_path: str) -> str:
    """阶段 C: 选择集 + 路径; 测试 selection-first 形态是否可静默导出。"""
    safe = out_path.replace("\\", "/").replace('"', '\\"')
    return (
        _load_prelude()
        + f'''
(defun c:t20mcp-tpsa-c ( / ss *error*)
  (defun *error* (m) (princ (strcat "\\nT20MCP-PSA-C-ERR " (if m m "?"))))
  (setvar "CMDECHO" 1)
  (setvar "FILEDIA" 0)
  (princ "\\n@@@PROBE-START@@@\\n")
  (setq ss (ssget "_X" (list (cons 0 "TCH_*"))))
  (princ (strcat "\\n@@@SS-LEN=" (if ss (itoa (sslength ss)) "nil") "@@@\\n"))
  (vl-catch-all-apply 'vl-cmdf (list "TPartSaveAs" ss "" "{safe}"))
  (princ (strcat "\\n@@@AFTER active=" (itoa (getvar "CMDACTIVE")) "@@@\\n"))
  (princ))
(c:t20mcp-tpsa-c)
(strcat "active=" (itoa (getvar "CMDACTIVE")))
'''
    )


def _wall_prereq_lisp() -> str:
    from t20_mcp.tools.tangent import generate_lisp

    return generate_lisp(
        "wall",
        {
            "x1": 0,
            "y1": 0,
            "x2": 3000,
            "y2": 0,
            "left_width": 120,
            "right_width": 120,
            "height": 3000,
            "wall_type": "砖",
        },
    )


async def phase_c(backend: FileIPCBackend) -> int:
    out = Path(os.environ.get("TEMP", ".")) / "t20_mcp_tpartsaveas_probe_c.dwg"
    if out.exists():
        out.unlink()
    print(f"=== Phase C: selection-set + path; 目标输出 {out} ===")

    _, pid = win32process.GetWindowThreadProcessId(backend._hwnd)
    pre_count_r = await backend.entity_count()
    pre_count = pre_count_r.payload["count"] if pre_count_r.ok else -1

    # 1) 创建一道临时 TCH_WALL 作为可导出对象
    wall_r = await backend.execute_lisp(_wall_prereq_lisp())
    print(f"  prereq wall ok={wall_r.ok} payload={wall_r.payload!r}")
    after_wall_r = await backend.entity_count()
    after_wall = after_wall_r.payload["count"] if after_wall_r.ok else -1
    print(f"  entity count {pre_count} -> {after_wall}")
    if after_wall <= pre_count:
        print("  FAIL: 临时 wall 未创建, 终止 Phase C")
        return 1

    # 2) 跑 TPartSaveAs (ssget _X TCH_* + 空回车 + 路径)
    pre_popups = popup_classes(pid)
    pre_env = await assert_env_clean(backend)
    print(f"  pre env={pre_env}")
    print(f"  pre_popups (filtered)={pre_popups}")

    r = await backend.execute_lisp(build_phase_c_lisp(str(out)))
    print(f"  cmdf ok={r.ok} payload={r.payload!r} error={r.error!r}")
    time.sleep(0.8)
    mid_popups = popup_classes(pid)
    print(f"  mid_popups (filtered)={mid_popups}")

    # ESC-only 恢复
    target = command_target_hwnd(backend._hwnd)
    for _ in range(3):
        post_escape(target, 4)
        time.sleep(0.3)
    await backend.execute_lisp(RESET_ENV)
    time.sleep(0.4)

    post_popups = popup_classes(pid)
    post_env = await assert_env_clean(backend)
    file_ok = out.exists() and out.stat().st_size > 0
    print(f"  post_popups (filtered)={post_popups}")
    print(f"  post env={post_env}")
    print(f"  output_file_exists={file_ok} size={out.stat().st_size if out.exists() else '-'}")

    # 清理临时 wall
    rounds = 0
    while rounds < 8:
        cur = await backend.entity_count()
        cur_n = cur.payload["count"] if cur.ok else -1
        if cur_n <= pre_count or cur_n < 0:
            break
        await backend.undo()
        rounds += 1
    final_r = await backend.entity_count()
    final_n = final_r.payload["count"] if final_r.ok else -1
    print(f"  cleanup undo rounds={rounds} final entity count={final_n} (baseline {pre_count})")

    has_modal_during = any(c == "#32770" for c, _ in mid_popups)
    has_modal_left = any(c == "#32770" for c, _ in post_popups)
    env_clean = (
        post_env.get("CMDACTIVE") == 0
        and post_env.get("CMDDIA") == 1
        and post_env.get("FILEDIA") == 1
    )

    print()
    print("=== Phase C verdict ===")
    print(f"  弹 #32770 期间        : {'YES' if has_modal_during else 'no'}")
    print(f"  事后残留 #32770       : {'YES' if has_modal_left else 'no'}")
    print(f"  输出文件真实存在      : {'YES' if file_ok else 'no'}")
    print(f"  环境干净              : {'YES' if env_clean else 'no'}")
    print(f"  cleanup 回到 baseline : {'YES' if final_n == pre_count else 'no'}")
    success = file_ok and env_clean and not has_modal_left and final_n == pre_count
    print(
        f"  -> 结论: {'SUCCESS-silent-export' if success else ('BLOCKED-by-modal' if has_modal_during else 'INDETERMINATE')}"
    )
    return 0 if success else 2


async def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    phase = sys.argv[1]
    backend = FileIPCBackend()
    init = await backend.initialize()
    if not init.ok:
        print(f"FAIL init: {init.error}")
        return 1
    if phase == "phase_a":
        return await phase_a(backend)
    if phase == "phase_b":
        return await phase_b(backend)
    if phase == "phase_c":
        return await phase_c(backend)
    print(f"unknown phase: {phase}")
    return 2


if __name__ == "__main__":
    _lock = live_lock_or_exit(__file__)
    raise SystemExit(asyncio.run(main()))
