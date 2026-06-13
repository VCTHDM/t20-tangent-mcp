"""真机联调 Step 28 — TRectAxis「绘制轴网」对话框控件侦察 (只取证, ESC 恢复).

目的: dialog_automation (BM_CLICK 白名单, itest_24 验证) 若要扩展到轴网,
需先知道「绘制轴网」框内有什么控件 (按钮/编辑框/列表)。本脚本只:
  启动 TRECTAXIS → 等模态框 → 枚举全部子控件 (类名+文本) → ESC 取消 →
  环境复位断言。不点击任何按钮, 不填任何字段。

用法: uv run python scripts/itest_28_rectaxis_recon.py
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.stdout.reconfigure(errors="replace")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import win32con
import win32gui
import win32process

from t20_mcp.backends.file_ipc import FileIPCBackend, _process_image_name
from t20_mcp.tools.tangent import _load_prelude

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

LAUNCH = """
(defun c:t20mcp-recon ( / t20mcp:saved *error*)
  (setq t20mcp:saved (t20mcp:begin "rectaxis-recon"))
  (defun *error* (m) (t20mcp:on-error m t20mcp:saved))
  (t20mcp:call "TRECTAXIS" nil)
  (t20mcp:end "rectaxis-recon" t20mcp:saved)
  (princ))
(c:t20mcp-recon)
"""


def acad_windows() -> set[int]:
    out: set[int] = set()

    def cb(hwnd: int, _: object) -> bool:
        if win32gui.IsWindowVisible(hwnd):
            try:
                _, pid = win32process.GetWindowThreadProcessId(hwnd)
            except Exception:
                return True
            if _process_image_name(pid) == "acad.exe":
                out.add(hwnd)
        return True

    win32gui.EnumWindows(cb, None)
    return out


def dump_controls(hwnd: int) -> list[str]:
    rows: list[str] = []

    def cb(child: int, _: object) -> bool:
        try:
            rows.append(
                f"{win32gui.GetClassName(child)} | {win32gui.GetWindowText(child)!r}"
            )
        except Exception:
            pass
        return True

    try:
        win32gui.EnumChildWindows(hwnd, cb, None)
    except Exception:
        pass
    return rows


async def main() -> int:
    backend = FileIPCBackend()
    init = await backend.initialize()
    if not init.ok:
        print(f"FAIL: initialize: {init.error}")
        return 1
    await backend.execute_lisp(RESET_ENV)
    baseline = acad_windows()

    task = asyncio.ensure_future(backend.execute_lisp(_load_prelude() + LAUNCH))

    dialog = None
    for _ in range(24):
        await asyncio.sleep(0.25)
        new = acad_windows() - baseline
        if new:
            dialog = next(iter(new))
            break

    if dialog is None:
        print("对话框未出现 (TRectAxis 行为变化?)")
    else:
        cls = win32gui.GetClassName(dialog)
        title = win32gui.GetWindowText(dialog)
        print(f"[dialog] class={cls} title={title!r}")
        for row in dump_controls(dialog):
            print(f"  {row}")
        win32gui.PostMessage(dialog, win32con.WM_KEYDOWN, win32con.VK_ESCAPE, 0)
        win32gui.PostMessage(dialog, win32con.WM_KEYUP, win32con.VK_ESCAPE, 0)

    try:
        result = await asyncio.wait_for(task, timeout=20.0)
        print(f"[lisp] ok={result.ok} error={result.error!r}")
    except asyncio.TimeoutError:
        task.cancel()
        print("[lisp] task-timeout")

    await asyncio.sleep(0.5)
    if backend._command_hwnd:
        for _ in range(2):
            win32gui.PostMessage(
                backend._command_hwnd, win32con.WM_KEYDOWN, win32con.VK_ESCAPE, 0
            )
            win32gui.PostMessage(
                backend._command_hwnd, win32con.WM_KEYUP, win32con.VK_ESCAPE, 0
            )
    reset = await backend.execute_lisp(RESET_ENV)
    env = await backend.drawing_get_variables(["CMDACTIVE", "CMDDIA", "FILEDIA", "OSMODE"])
    cnt = await backend.entity_count()
    print(f"[cleanup] reset={reset.ok} env={env.payload} entities={cnt.payload}")
    ok = (
        env.ok
        and env.payload.get("CMDACTIVE") == 0
        and env.payload.get("CMDDIA") == 1
        and env.payload.get("FILEDIA") == 1
    )
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
