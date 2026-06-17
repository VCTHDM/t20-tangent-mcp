"""真机联调 Step 21 — P1-2 补盲验收: 模态对话框探测 (含 WPF HwndWrapper).

验证 `_autocad_modal_dialog_present` 的新「主窗口被禁用」信号:

1. 基线: 无对话框时探测必须为 False (非模态天正面板不得误报)。
2. TGETXML (#32770 模态框, itest_17 已证可 ESC 恢复): 弹框期间探测应为 True,
   且 _dispatch 应立即拒绝 (不再傻等超时); ESC 恢复后探测回 False。
3. TSAVEAS (天正 WPF 导出框, 原 #32770 探测的盲区): 弹框期间探测应为 True
   (仅靠 IsWindowEnabled 信号), 记录弹框窗口类名; ESC 恢复。

恢复只发 ESC, 严禁 WM_CLOSE (PROJECT_RULES.md 铁律)。

用法: uv run python scripts/itest_21_wpf_dialog_guard.py
"""

from __future__ import annotations

import asyncio
import sys
import time
from pathlib import Path

sys.stdout.reconfigure(errors="replace")
sys.path.insert(0, str(Path(__file__).resolve().parent))  # for _live_lock
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import win32con
import win32gui
import win32process

from _live_lock import live_lock_or_exit  # noqa: E402
from t20_mcp.backends.file_ipc import FileIPCBackend, _process_image_name  # noqa: E402
from t20_mcp.tools.tangent import _load_prelude  # noqa: E402

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


def acad_windows() -> list[tuple[int, str, str]]:
    out: list[tuple[int, str, str]] = []

    def cb(hwnd: int, _: object) -> bool:
        if win32gui.IsWindowVisible(hwnd):
            try:
                _, pid = win32process.GetWindowThreadProcessId(hwnd)
            except Exception:
                return True
            if _process_image_name(pid) == "acad.exe":
                out.append((hwnd, win32gui.GetClassName(hwnd), win32gui.GetWindowText(hwnd)))
        return True

    win32gui.EnumWindows(cb, None)
    return out


def send_esc_to_new_windows(baseline: list[tuple[int, str, str]]) -> list[tuple[str, str]]:
    """对基线之外新出现的 acad 窗口发 ESC (只发 ESC, 禁 WM_CLOSE)。"""
    base = {hwnd for hwnd, _, _ in baseline}
    seen: list[tuple[str, str]] = []
    for hwnd, cls, title in acad_windows():
        if hwnd in base:
            continue
        seen.append((cls, title))
        win32gui.PostMessage(hwnd, win32con.WM_KEYDOWN, win32con.VK_ESCAPE, 0)
        win32gui.PostMessage(hwnd, win32con.WM_KEYUP, win32con.VK_ESCAPE, 0)
    return seen


def trial_lisp(command: str) -> str:
    tag = command.lower()
    return (
        _load_prelude()
        + "\n"
        + f"""
(defun c:t20mcp-trial ( / t20mcp:saved *error* t20mcp:prev t20mcp:new)
  (setq t20mcp:saved (t20mcp:begin "{tag}"))
  (defun *error* (m) (t20mcp:on-error m t20mcp:saved))
  (setq t20mcp:prev (entlast))
  (t20mcp:call "{command}" (list ""))
  (setq t20mcp:new (entlast))
  (if (and t20mcp:new (not (eq t20mcp:prev t20mcp:new)))
      (t20mcp:end "{tag}:entity-created" t20mcp:saved)
      (t20mcp:fail "{tag}" t20mcp:saved "no-entity"))
  (princ))
(c:t20mcp-trial)
"""
    )


async def probe_dialog_command(backend: FileIPCBackend, command: str) -> dict:
    """触发弹框命令, 弹框期间采样探测信号, ESC 恢复, 返回采样结果。"""
    baseline = acad_windows()
    outcome: dict = {
        "command": command,
        "detected_during": False,
        "refused_during": False,
        "new_windows": [],
        "recovered": False,
    }

    task = asyncio.create_task(backend.execute_lisp(trial_lisp(command)))

    # 等弹框出现 (最多 6s), 期间采样探测信号
    deadline = time.time() + 6.0
    while time.time() < deadline:
        await asyncio.sleep(0.3)
        if backend._autocad_modal_dialog_present():
            outcome["detected_during"] = True
            break
    # 记录弹框期间新窗口类名 (仅记录, 不动它)
    base = {hwnd for hwnd, _, _ in baseline}
    outcome["new_windows"] = [
        (cls, title) for hwnd, cls, title in acad_windows() if hwnd not in base
    ]

    # 弹框期间 _dispatch 应立即拒绝
    if outcome["detected_during"]:
        probe = await backend.entity_count()
        outcome["refused_during"] = (not probe.ok) and "对话框" in (probe.error or "")

    # ESC 恢复 (新窗口 + 命令行各两轮), 然后等 LISP 任务收尾
    for _ in range(2):
        send_esc_to_new_windows(baseline)
        await asyncio.sleep(0.7)
        if not backend._autocad_modal_dialog_present():
            break
    if backend._command_hwnd:
        for _ in range(2):
            win32gui.PostMessage(
                backend._command_hwnd, win32con.WM_KEYDOWN, win32con.VK_ESCAPE, 0
            )
            win32gui.PostMessage(
                backend._command_hwnd, win32con.WM_KEYUP, win32con.VK_ESCAPE, 0
            )
    try:
        result = await asyncio.wait_for(task, timeout=20.0)
        outcome["lisp_result"] = f"ok={result.ok} error={result.error!r}"
    except asyncio.TimeoutError:
        task.cancel()
        outcome["lisp_result"] = "task-timeout"

    await asyncio.sleep(0.5)
    if backend._autocad_modal_dialog_present():
        # 仍有弹框: 不再尝试任何强制手段, 留给人工处理
        print(f"  !! {command}: ESC 后探测仍为 True, 停手待人工")
        return outcome

    reset = await backend.execute_lisp(RESET_ENV)
    env = await backend.drawing_get_variables(["CMDACTIVE", "CMDDIA", "FILEDIA", "OSMODE"])
    outcome["recovered"] = (
        reset.ok
        and env.ok
        and env.payload.get("CMDACTIVE") == 0
        and env.payload.get("CMDDIA") == 1
        and env.payload.get("FILEDIA") == 1
        and env.payload.get("OSMODE") == 0
    )
    outcome["env"] = env.payload if env.ok else env.error
    return outcome


async def main() -> int:
    backend = FileIPCBackend()
    init = await backend.initialize()
    if not init.ok:
        print(f"FAIL: initialize: {init.error}")
        return 1

    await backend.execute_lisp(RESET_ENV)

    # 1. 基线: 无弹框时必须 False (天正非模态面板不得误报)
    baseline_clear = not backend._autocad_modal_dialog_present()
    print(f"[baseline] modal_detected=False expected, got_clear={baseline_clear}")
    if not baseline_clear:
        print("FAIL: 基线误报 — 非模态面板被当成模态框, 不能合入")
        return 1

    ok = True
    for command in ("TGETXML", "TSAVEAS"):
        outcome = await probe_dialog_command(backend, command)
        print(
            f"[{command}] detected={outcome['detected_during']} "
            f"refused={outcome['refused_during']} recovered={outcome['recovered']}\n"
            f"  windows={outcome['new_windows'] or '(none)'}\n"
            f"  lisp={outcome.get('lisp_result')} env={outcome.get('env')}"
        )
        ok = ok and outcome["detected_during"] and outcome["recovered"]

    final_clear = not backend._autocad_modal_dialog_present()
    ping = await backend.execute_lisp('"pong"')
    print(f"[final] clear={final_clear} ping_ok={ping.ok}")
    return 0 if ok and final_clear and ping.ok else 1


if __name__ == "__main__":
    _lock = live_lock_or_exit(__file__)
    raise SystemExit(asyncio.run(main()))
