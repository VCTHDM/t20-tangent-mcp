"""真机联调 Step 32 — LOGFILEMODE 命令行提示捕获.

AutoCAD ``LOGFILEMODE=1`` 时会把命令行文字写入 ``LOGFILENAME`` 指向的
日志文件。该方法比 LASTPROMPT/截图更可靠, 已用于捕获 TDimTP / TSWall
等天正命令的真实提示流。

用法:
  uv run python -X utf8 scripts/itest_32_prompt_capture_log.py path
  uv run python -X utf8 scripts/itest_32_prompt_capture_log.py run TDIMTP tdimtp_fence none
  uv run python -X utf8 scripts/itest_32_prompt_capture_log.py run TSWALL tswall_ss line

命名场景:
  tswall_ss      选择所有 LINE 后回车
  tswall_ss_w    选择所有 LINE 后回车, 再输入 240
  tdimtp_fence   水平穿越线: (-500,0)->(6500,0)
  tdimtp_cross   垂直穿越线: (1500,-800)->(1500,800)

注意:
  - 该脚本只捕获提示和候选输入消费情况, 不宣称命令 E2E 成功。
  - 若命令参数不足导致仍处于活动状态, 脚本会发 ESC 取消并复位环境。
  - 严禁把该脚本改成强关天正 ARX 对话框; 只允许 ESC/命令取消恢复。
"""

from __future__ import annotations

import asyncio
import ctypes
import sys
from pathlib import Path

sys.stdout.reconfigure(errors="replace")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import win32gui

from t20_mcp.backends.file_ipc import FileIPCBackend
from t20_mcp.tools.tangent import _load_prelude, generate_lisp

RESET_ENV = (
    '(progn (setq n 0)'
    ' (while (and (< n 6) (> (getvar "CMDACTIVE") 0)) (command) (setq n (1+ n)))'
    ' (setvar "CMDDIA" 1) (setvar "FILEDIA" 1) (setvar "OSMODE" 0) "rst")'
)

NAMED_SCENARIOS = {
    "tswall_ss": '(list (ssget "_X" (list (cons 0 "LINE"))) "")',
    "tswall_ss_w": '(list (ssget "_X" (list (cons 0 "LINE"))) "" "240")',
    "tdimtp_fence": "(list (t20mcp:pt -500 0) (t20mcp:pt 6500 0))",
    "tdimtp_cross": "(list (t20mcp:pt 1500 -800) (t20mcp:pt 1500 800))",
    "empty": "(list)",
}


async def get_logpath(backend: FileIPCBackend) -> str:
    await backend.execute_lisp('(progn (setvar "LOGFILEMODE" 1) "on")')
    result = await backend.execute_lisp('(getvar "LOGFILENAME")')
    return (result.payload or "").strip('"') if result.ok else ""


def build_run_lisp(command: str, arglist_src: str) -> str:
    return (
        _load_prelude()
        + f"""
(defun c:t20mcp-run ( / *error*)
  (defun *error* (m) (princ (strcat "\\nT20MCP-RUNERR " (if m m "?"))))
  (setvar "CMDECHO" 1)
  (princ "\\n@@@PROBE-START@@@\\n")
  (vl-catch-all-apply 'vl-cmdf (cons "{command}" {arglist_src}))
  (princ (strcat "\\n@@@AFTER active=" (itoa (getvar "CMDACTIVE")) "@@@\\n"))
  (princ))
(c:t20mcp-run)
(strcat "active=" (itoa (getvar "CMDACTIVE")))
"""
    )


def command_target_hwnd(main_hwnd: int) -> int:
    mdi_children: list[int] = []

    def callback(hwnd: int, _: object) -> bool:
        if win32gui.GetClassName(hwnd) == "MDIClient":
            mdi_children.append(hwnd)
            return False
        return True

    win32gui.EnumChildWindows(main_hwnd, callback, None)
    return mdi_children[0] if mdi_children else main_hwnd


def post_escape(hwnd: int, times: int = 3) -> None:
    post_message = ctypes.windll.user32.PostMessageW
    for _ in range(times):
        post_message(hwnd, 0x0100, 0x1B, 0)
        post_message(hwnd, 0x0101, 0x1B, 0)


def decode_log_tail(raw: bytes) -> str:
    for encoding in ("gbk", "utf-8", "cp1252"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    return raw.decode("cp1252", errors="replace")


async def prepare_prereq(backend: FileIPCBackend, prereq: str) -> None:
    if prereq == "wall":
        await backend.execute_lisp(
            generate_lisp(
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
        )
    elif prereq == "line":
        await backend.create_line(0, 0, 3000, 0)
    elif prereq != "none":
        raise ValueError(f"unknown prereq: {prereq}")


async def entity_count(backend: FileIPCBackend) -> int:
    count = await backend.entity_count()
    return count.payload["count"] if count.ok else -1


async def cleanup_to(backend: FileIPCBackend, target_count: int) -> None:
    await backend.execute_lisp(RESET_ENV)
    rounds = 0
    while rounds < 12:
        count = await entity_count(backend)
        if count < 0 or count <= target_count:
            break
        await backend.undo()
        rounds += 1


async def run_capture(backend: FileIPCBackend, logpath: str) -> int:
    if len(sys.argv) < 3:
        print("usage: ... run <CMD> [arglist-or-named-scene] [wall|line|none]")
        return 2

    command = sys.argv[2]
    arglist = sys.argv[3] if len(sys.argv) > 3 else "(list)"
    arglist = NAMED_SCENARIOS.get(arglist, arglist)
    prereq = sys.argv[4] if len(sys.argv) > 4 else "none"

    baseline = await entity_count(backend)
    await prepare_prereq(backend, prereq)

    path = Path(logpath)
    pre_len = path.stat().st_size if path.exists() else 0
    result = await backend.execute_lisp(build_run_lisp(command, arglist))
    print(f"run ok={result.ok} payload={result.payload!r} error={result.error!r}")

    await asyncio.sleep(0.6)
    post_escape(command_target_hwnd(backend._hwnd))
    await asyncio.sleep(0.4)
    await backend.execute_lisp('(progn (setvar "LOGFILEMODE" 0) "off")')

    if path.exists():
        text = decode_log_tail(path.read_bytes()[pre_len:])
        start = text.find("@@@PROBE-START@@@")
        print("===== LOG TAIL =====")
        print(text[start:] if start >= 0 else text[-2000:])
        print("===== END =====")
    else:
        print("log file not found")

    await cleanup_to(backend, baseline)
    return 0


async def main() -> int:
    action = sys.argv[1] if len(sys.argv) > 1 else "path"
    backend = FileIPCBackend()
    init = await backend.initialize()
    if not init.ok:
        print(f"init FAIL: {init.error}")
        return 1

    logpath = await get_logpath(backend)
    print(f"LOGFILENAME: {logpath!r}")
    if action == "path":
        await backend.execute_lisp('(progn (setvar "LOGFILEMODE" 0) "off")')
        return 0
    if action == "run":
        return await run_capture(backend, logpath)

    print(f"unknown action: {action}")
    await backend.execute_lisp('(progn (setvar "LOGFILEMODE" 0) "off")')
    return 2


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
