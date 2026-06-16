"""Real-machine Step 44 - TPARTSAVEAS argument-shape probe.

This is a P2 reconnaissance script, not a wrapper and not an E2E promotion.
It probes whether TPARTSAVEAS has a silent output-file path that can replace
export_t3/TSAVEAS. Recovery is ESC-only; never send WM_CLOSE to T20 dialogs.

Usage:
  uv run python scripts/itest_44_tpartsaveas_args_probe.py

Exit code 2 means TPARTSAVEAS is not registered in the current T20 session.
"""

from __future__ import annotations

import asyncio
import sys
import time
from pathlib import Path

sys.stdout.reconfigure(errors="replace")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import win32con
import win32gui
import win32process

from t20_mcp.backends.file_ipc import FileIPCBackend, _process_image_name
from t20_mcp.config import IPC_DIR
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

CASES = [
    ("path-only", '(list "{{OUT_PATH}}")'),
    ("version-then-path", '(list "3" "{{OUT_PATH}}")'),
    ("path-then-version", '(list "{{OUT_PATH}}" "3")'),
    ("empty-then-path", '(list "" "{{OUT_PATH}}")'),
]


def acad_windows() -> list[tuple[int, str, str]]:
    windows: list[tuple[int, str, str]] = []

    def callback(hwnd: int, _: object) -> bool:
        if win32gui.IsWindowVisible(hwnd):
            try:
                _, pid = win32process.GetWindowThreadProcessId(hwnd)
            except Exception:
                return True
            if _process_image_name(pid) == "acad.exe":
                windows.append((hwnd, win32gui.GetClassName(hwnd), win32gui.GetWindowText(hwnd)))
        return True

    win32gui.EnumWindows(callback, None)
    return windows


def send_esc_to_new_windows(baseline: list[tuple[int, str, str]]) -> list[tuple[str, str]]:
    base = {hwnd for hwnd, _, _ in baseline}
    seen: list[tuple[str, str]] = []
    for hwnd, cls, title in acad_windows():
        if hwnd in base:
            continue
        seen.append((cls, title))
        win32gui.PostMessage(hwnd, win32con.WM_KEYDOWN, win32con.VK_ESCAPE, 0)
        win32gui.PostMessage(hwnd, win32con.WM_KEYUP, win32con.VK_ESCAPE, 0)
    return seen


def post_command_esc(backend: FileIPCBackend, times: int = 3) -> None:
    if not backend._command_hwnd:
        return
    for _ in range(times):
        win32gui.PostMessage(backend._command_hwnd, win32con.WM_KEYDOWN, win32con.VK_ESCAPE, 0)
        win32gui.PostMessage(backend._command_hwnd, win32con.WM_KEYUP, win32con.VK_ESCAPE, 0)


def trial_lisp(label: str, args_src: str, out_path: Path) -> str:
    safe_path = str(out_path).replace("\\", "/")
    arglist = args_src.replace("{{OUT_PATH}}", safe_path)
    return (
        _load_prelude()
        + "\n"
        + f"""
(defun c:t20mcp-probe ( / t20mcp:saved *error* t20mcp:before t20mcp:after)
  (setq t20mcp:saved (t20mcp:begin "tpartsaveas-{label}"))
  (defun *error* (m) (t20mcp:on-error m t20mcp:saved))
  (setq t20mcp:before (entlast))
  (t20mcp:call "TPARTSAVEAS" {arglist})
  (setq t20mcp:after (entlast))
  (if (findfile "{safe_path}")
      (t20mcp:end "tpartsaveas-{label}:file-created" t20mcp:saved)
      (t20mcp:fail "tpartsaveas-{label}" t20mcp:saved "no-output-file"))
  (princ))
(c:t20mcp-probe)
"""
    )


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


async def command_registered(backend: FileIPCBackend) -> bool:
    result = await backend.execute_lisp('(if (getcname "TPARTSAVEAS") "yes" "no")')
    registered = result.ok and str(result.payload).strip('"') == "yes"
    print(f"[preflight] TPARTSAVEAS registered={registered} raw={result.payload!r}")
    return registered


async def run_case(backend: FileIPCBackend, label: str, args_src: str) -> bool:
    out_path = Path(IPC_DIR) / f"itest_44_{label}.dwg"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    if out_path.exists():
        out_path.unlink()

    baseline = acad_windows()
    before = await entity_count(backend)
    if before < 0:
        raise RuntimeError(f"{label}: entity_count failed before probe")
    try:
        result = await backend.execute_lisp(trial_lisp(label, args_src, out_path))
        after = await entity_count(backend)
        created = out_path.exists()
        print(
            f"[{label}] ok={result.ok} payload={result.payload!r} error={result.error!r} "
            f"file={created} entities {before}->{after}"
        )

        if not result.ok and "Timeout" in (result.error or ""):
            windows = send_esc_to_new_windows(baseline)
            print(f"  timeout windows: {windows or '(none)'}")
            post_command_esc(backend)
            time.sleep(1.0)

        return bool(created)
    finally:
        recovered, env = await reset_and_env(backend)
        print(f"  recovered={recovered} env={env}")


async def main() -> int:
    backend = FileIPCBackend()
    init = await backend.initialize()
    if not init.ok:
        print(f"FAIL: initialize: {init.error}")
        return 1

    await backend.execute_lisp(RESET_ENV)
    if not await command_registered(backend):
        print("summary any_file_created=False all_recovered=True reason=not-registered")
        await reset_and_env(backend)
        return 2

    any_file = False
    all_recovered = True
    try:
        for label, args_src in CASES:
            case_file = await run_case(backend, label, args_src)
            recovered, _ = await reset_and_env(backend)
            any_file = any_file or case_file
            all_recovered = all_recovered and recovered
    finally:
        recovered, _ = await reset_and_env(backend)
        all_recovered = all_recovered and recovered

    print(f"summary any_file_created={any_file} all_recovered={all_recovered}")
    return 0 if all_recovered else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
