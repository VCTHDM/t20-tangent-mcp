"""Real-machine Step 46 - P3 Gate A TGColumn dialog inventory.

This is a design-gate probe, not a wrapper and not an E2E promotion.
It inventories the first dialog/panel opened by TGColumn, then recovers with
ESC only. It never fills fields, clicks buttons, sends WM_CLOSE, or edits any
infrastructure.

Usage:
  uv run python scripts/itest_46_column_gate_a_inventory.py

Exit code 2 means TGCOLUMN is not registered in the current T20 session.
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
from t20_mcp.config import ACAD_PROCESS_NAME
from t20_mcp.tools.tangent import _load_prelude

RESET_ENV = """
(progn
  (setq n 0)
  (while (and (< n 8) (> (getvar "CMDACTIVE") 0))
    (command)
    (setq n (1+ n)))
  (setvar "CMDDIA" 1)
  (setvar "FILEDIA" 1)
  (setvar "OSMODE" 0)
  "env-reset")
"""

LAUNCH_TGCOLUMN = (
    _load_prelude()
    + """
(defun c:t20mcp-gate-a-column ( / r)
  (setvar "CMDECHO" 1)
  (setq r (vl-catch-all-apply 'vl-cmdf (list "TGCOLUMN")))
  (strcat "active=" (itoa (getvar "CMDACTIVE"))))
(c:t20mcp-gate-a-column)
"""
)


def acad_windows() -> list[dict[str, object]]:
    windows: list[dict[str, object]] = []

    def callback(hwnd: int, _: object) -> bool:
        if not win32gui.IsWindowVisible(hwnd):
            return True
        try:
            _, pid = win32process.GetWindowThreadProcessId(hwnd)
        except Exception:
            return True
        if _process_image_name(pid) != ACAD_PROCESS_NAME:
            return True
        try:
            rect = win32gui.GetWindowRect(hwnd)
        except Exception:
            rect = None
        windows.append(
            {
                "hwnd": hwnd,
                "class": win32gui.GetClassName(hwnd),
                "title": win32gui.GetWindowText(hwnd),
                "enabled": bool(win32gui.IsWindowEnabled(hwnd)),
                "rect": rect,
            }
        )
        return True

    win32gui.EnumWindows(callback, None)
    return windows


def dump_controls(hwnd: int, max_depth: int = 4) -> list[str]:
    rows: list[str] = []

    def walk(parent: int, depth: int) -> None:
        if depth > max_depth:
            return
        child = win32gui.GetWindow(parent, win32con.GW_CHILD)
        while child:
            try:
                try:
                    ctrl_id = win32gui.GetDlgCtrlID(child)
                except Exception:
                    ctrl_id = None
                try:
                    rect = win32gui.GetWindowRect(child)
                except Exception:
                    rect = None
                rows.append(
                    "  "
                    + ("  " * depth)
                    + f"hwnd={child} id={ctrl_id} class={win32gui.GetClassName(child)!r} "
                    + f"text={win32gui.GetWindowText(child)!r} "
                    + f"enabled={bool(win32gui.IsWindowEnabled(child))} rect={rect}"
                )
                walk(child, depth + 1)
            except Exception as exc:
                rows.append("  " + ("  " * depth) + f"<control-read-error {exc!r}>")
            child = win32gui.GetWindow(child, win32con.GW_HWNDNEXT)

    walk(hwnd, 0)
    return rows


def post_escape(hwnd: int, times: int = 2) -> None:
    for _ in range(times):
        win32gui.PostMessage(hwnd, win32con.WM_KEYDOWN, win32con.VK_ESCAPE, 0)
        win32gui.PostMessage(hwnd, win32con.WM_KEYUP, win32con.VK_ESCAPE, 0)


async def entity_count(backend: FileIPCBackend) -> int:
    result = await backend.entity_count()
    if not result.ok or not isinstance(result.payload, dict):
        print(f"[entity_count] failed payload={result.payload!r} error={result.error!r}")
        return -999
    count = result.payload.get("count")
    if not isinstance(count, int):
        print(f"[entity_count] bad payload={result.payload!r}")
        return -999
    return count


async def command_registered(backend: FileIPCBackend) -> bool:
    result = await backend.execute_lisp('(if (getcname "TGCOLUMN") "yes" "no")')
    registered = result.ok and str(result.payload).strip('"') == "yes"
    print(f"[preflight] TGCOLUMN registered={registered} raw={result.payload!r}")
    return registered


async def reset_and_env(backend: FileIPCBackend) -> tuple[bool, dict | str]:
    reset = await backend.execute_lisp(RESET_ENV)
    env = await backend.drawing_get_variables(["CMDACTIVE", "CMDDIA", "FILEDIA", "OSMODE"])
    ok = (
        reset.ok
        and env.ok
        and env.payload.get("CMDACTIVE") == 0
        and env.payload.get("CMDDIA") == 1
        and env.payload.get("FILEDIA") == 1
        and env.payload.get("OSMODE") == 0
    )
    return ok, env.payload if env.ok else (env.error or "env-read-failed")


async def main() -> int:
    backend = FileIPCBackend()
    init = await backend.initialize()
    if not init.ok:
        print(f"FAIL: initialize: {init.error}")
        return 1

    await backend.execute_lisp(RESET_ENV)
    if not await command_registered(backend):
        await reset_and_env(backend)
        return 2

    before = await entity_count(backend)
    if before < 0:
        print("FAIL: baseline entity_count failed")
        return 1

    baseline = acad_windows()
    base_hwnds = {int(row["hwnd"]) for row in baseline}
    print(f"[baseline] entities={before} windows={len(baseline)}")

    task = asyncio.create_task(backend.execute_lisp(LAUNCH_TGCOLUMN))
    inventory: list[dict[str, object]] = []

    try:
        for _ in range(32):
            await asyncio.sleep(0.25)
            current = [row for row in acad_windows() if int(row["hwnd"]) not in base_hwnds]
            if current:
                inventory = current
                break

        if inventory:
            print("[inventory] new acad windows:")
            for row in inventory:
                hwnd = int(row["hwnd"])
                print(
                    f"  hwnd={hwnd} class={row['class']!r} title={row['title']!r} "
                    f"enabled={row['enabled']} rect={row['rect']}"
                )
                for control in dump_controls(hwnd):
                    print(control)
        else:
            print("[inventory] no new acad window observed")

        for row in inventory:
            post_escape(int(row["hwnd"]))
        if backend._command_hwnd:
            post_escape(backend._command_hwnd)

        try:
            result = await asyncio.wait_for(task, timeout=15.0)
            print(f"[launch] ok={result.ok} payload={result.payload!r} error={result.error!r}")
        except asyncio.TimeoutError:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
            print("[launch] task-timeout after ESC")
        except Exception as exc:
            print(f"[launch] failed after ESC: {exc!r}")
    finally:
        for row in inventory:
            post_escape(int(row["hwnd"]))
        if backend._command_hwnd:
            post_escape(backend._command_hwnd)

    recovered, env = await reset_and_env(backend)
    after = await entity_count(backend)
    residual_windows = [row for row in acad_windows() if int(row["hwnd"]) not in base_hwnds]
    print(f"[cleanup] recovered={recovered} env={env} entities={before}->{after}")
    print(f"[cleanup] residual_windows={residual_windows or '(none)'}")

    ok = bool(inventory) and recovered and after == before and not residual_windows
    print(f"summary gate_a_inventory={bool(inventory)} clean={ok}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
