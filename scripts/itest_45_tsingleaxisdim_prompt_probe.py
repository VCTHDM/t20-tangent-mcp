"""Real-machine Step 45 - TSingleAxisDim prompt-flow probe.

This P2 probe captures command-line prompts with LOGFILEMODE. It does not claim
E2E success and does not create a wrapper. If the command remains active, the
script cancels with ESC/command cancel and restores environment variables.

Usage:
  uv run python -X utf8 scripts/itest_45_tsingleaxisdim_prompt_probe.py

Exit code 2 means TSINGLEAXISDIM is not registered in the current T20 session.
"""

from __future__ import annotations

import asyncio
import ctypes
import sys
from pathlib import Path

sys.stdout.reconfigure(errors="replace")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import win32gui
import win32process

from t20_mcp.backends.file_ipc import FileIPCBackend, _process_image_name
from t20_mcp.tools.tangent import _load_prelude, generate_lisp

RESET_ENV = (
    '(progn (setq n 0)'
    ' (while (and (< n 8) (> (getvar "CMDACTIVE") 0)) (command) (setq n (1+ n)))'
    ' (setvar "CMDDIA" 1) (setvar "FILEDIA" 1) (setvar "OSMODE" 0) "rst")'
)

SCENARIOS = [
    ("empty", "(list)"),
    ("two-points", "(list (t20mcp:pt 0 0) (t20mcp:pt 3000 0) \"\")"),
    ("axis-lines-pick", '(list (ssget "_X" (list (cons 0 "LINE"))) "")'),
]


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


async def get_logpath(backend: FileIPCBackend) -> str:
    await backend.execute_lisp('(progn (setvar "LOGFILEMODE" 1) "on")')
    result = await backend.execute_lisp('(getvar "LOGFILENAME")')
    return (result.payload or "").strip('"') if result.ok else ""


async def command_registered(backend: FileIPCBackend) -> bool:
    result = await backend.execute_lisp('(if (getcname "TSINGLEAXISDIM") "yes" "no")')
    registered = result.ok and str(result.payload).strip('"') == "yes"
    print(f"[preflight] TSINGLEAXISDIM registered={registered} raw={result.payload!r}")
    return registered


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
        post_escape(hwnd)
    return seen


def decode_log_tail(raw: bytes) -> str:
    for encoding in ("gbk", "utf-8", "cp1252"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    return raw.decode("cp1252", errors="replace")


def build_probe_lisp(label: str, arglist_src: str) -> str:
    return (
        _load_prelude()
        + f"""
(defun c:t20mcp-probe ( / t20mcp:prev t20mcp:new t20mcp:type)
  (setvar "CMDECHO" 1)
  (princ "\\n@@@TSINGLEAXISDIM-{label}-START@@@\\n")
  (setq t20mcp:prev (entlast))
  (vl-catch-all-apply 'vl-cmdf (cons "TSINGLEAXISDIM" {arglist_src}))
  (setq t20mcp:new (entlast))
  (setq t20mcp:type (if t20mcp:new (cdr (assoc 0 (entget t20mcp:new))) "none"))
  (princ
    (strcat
      "\\n@@@TSINGLEAXISDIM-{label}-AFTER active="
      (itoa (getvar "CMDACTIVE"))
      " type="
      t20mcp:type
      " changed="
      (if (and t20mcp:new (not (eq t20mcp:prev t20mcp:new))) "yes" "no")
      "@@@\\n"))
  (princ))
(c:t20mcp-probe)
(strcat "active=" (itoa (getvar "CMDACTIVE")))
"""
    )


async def prepare_axis_lines(backend: FileIPCBackend) -> None:
    await backend.execute_lisp(
        generate_lisp(
            "axis_lines",
            {
                "base_x": 0,
                "base_y": 0,
                "hspacings": [3000],
                "vspacings": [3000],
            },
        )
    )


async def cleanup_to(backend: FileIPCBackend, target_count: int) -> None:
    await backend.execute_lisp(RESET_ENV)
    for _ in range(12):
        count = await entity_count(backend)
        if count < 0:
            print("[cleanup] entity_count failed; leaving cleanup after RESET_ENV")
            break
        if count <= target_count:
            break
        await backend.undo()
    await backend.execute_lisp(RESET_ENV)


async def run_scenario(backend: FileIPCBackend, logpath: str, label: str, args_src: str) -> None:
    baseline = await entity_count(backend)
    if baseline < 0:
        raise RuntimeError(f"{label}: entity_count failed before probe")
    window_baseline = acad_windows()
    if label == "axis-lines-pick":
        await prepare_axis_lines(backend)

    path = Path(logpath)
    pre_len = path.stat().st_size if path.exists() else 0
    result = await backend.execute_lisp(build_probe_lisp(label, args_src))
    print(f"[{label}] ok={result.ok} payload={result.payload!r} error={result.error!r}")

    await asyncio.sleep(0.6)
    if not result.ok and "Timeout" in (result.error or ""):
        windows = send_esc_to_new_windows(window_baseline)
        print(f"[{label}] timeout windows: {windows or '(none)'}")
    if backend._hwnd:
        post_escape(command_target_hwnd(backend._hwnd))
    await asyncio.sleep(0.4)

    if path.exists():
        text = decode_log_tail(path.read_bytes()[pre_len:])
        marker = f"@@@TSINGLEAXISDIM-{label}-START@@@"
        start = text.find(marker)
        print(f"===== {label} LOG TAIL =====")
        print(text[start:] if start >= 0 else text[-2000:])
        print("===== END =====")
    else:
        print(f"[{label}] log file not found")

    await cleanup_to(backend, baseline)


async def main() -> int:
    backend = FileIPCBackend()
    init = await backend.initialize()
    if not init.ok:
        print(f"FAIL: initialize: {init.error}")
        return 1

    if not await command_registered(backend):
        await backend.execute_lisp(RESET_ENV)
        return 2

    logpath = await get_logpath(backend)
    print(f"LOGFILENAME: {logpath!r}")
    if not logpath:
        print("FAIL: LOGFILENAME is empty")
        return 1
    try:
        for label, args_src in SCENARIOS:
            await run_scenario(backend, logpath, label, args_src)
    finally:
        await backend.execute_lisp('(progn (setvar "LOGFILEMODE" 0) "off")')
        await backend.execute_lisp(RESET_ENV)

    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
