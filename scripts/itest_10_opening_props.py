"""真机联调 Step 10 — TCH_OPENING ActiveX 属性探测 + TAXISGRID 试验.

  A. 画墙 → TOPENING 插门窗 → 探测/试写 VLA 属性 (Width/Height/SillHeight/类型)
  B. TAXISGRID 最小试验 (带弹框自动恢复)

用法: uv run python scripts/itest_10_opening_props.py
"""

from __future__ import annotations

import asyncio
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import win32con
import win32gui
import win32process

from t20_mcp.backends.file_ipc import FileIPCBackend, _process_image_name
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

PROBE_GET = """
(setq t20mcp:obj (vlax-ename->vla-object (entlast)))
(setq t20mcp:r "")
(foreach p (list {PROPS})
  (setq t20mcp:v (vl-catch-all-apply 'vlax-get-property (list t20mcp:obj p)))
  (setq t20mcp:r
        (strcat t20mcp:r p "="
                (if (vl-catch-all-error-p t20mcp:v)
                    "<no>"
                    (vl-princ-to-string (if (= (type t20mcp:v) 'VARIANT)
                                            (vlax-variant-value t20mcp:v)
                                            t20mcp:v)))
                ";")))
t20mcp:r
"""

PROBE_PUT = """
(setq t20mcp:obj (vlax-ename->vla-object (entlast)))
(setq t20mcp:r "")
(foreach pv (list {PAIRS})
  (setq t20mcp:e (vl-catch-all-apply 'vlax-put-property
                                     (list t20mcp:obj (car pv) (cdr pv))))
  (setq t20mcp:r (strcat t20mcp:r (car pv) "->"
                         (if (vl-catch-all-error-p t20mcp:e) "putFAIL" "putOK") ";")))
t20mcp:r
"""

OPENING_PROPS = [
    "Width", "Height", "SillHeight", "Elevation", "Kind", "Type", "OpeningKind",
    "Style", "Number", "Tag", "WinType", "DoorType", "UpLevel", "DoorSill",
    "SubKind", "Distance",
]

RESTORE_ENV = '(progn (setvar "CMDDIA" 1) (setvar "FILEDIA" 1) "env-restored")'


def acad_windows() -> set[int]:
    out: set[int] = set()

    def cb(hwnd, _):
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


def dismiss_new_windows(baseline: set[int]) -> list[str]:
    closed = []
    for hwnd in acad_windows() - baseline:
        closed.append(f"{win32gui.GetClassName(hwnd)!r}:{win32gui.GetWindowText(hwnd)!r}")
        win32gui.PostMessage(hwnd, win32con.WM_KEYDOWN, win32con.VK_ESCAPE, 0)
        win32gui.PostMessage(hwnd, win32con.WM_KEYUP, win32con.VK_ESCAPE, 0)
        time.sleep(0.4)
        if win32gui.IsWindow(hwnd) and win32gui.IsWindowVisible(hwnd):
            win32gui.PostMessage(hwnd, win32con.WM_CLOSE, 0, 0)
    return closed


async def count(backend: FileIPCBackend) -> int:
    r = await backend.entity_count()
    return r.payload["count"] if r.ok else -999


async def run(backend: FileIPCBackend, cmd: str, args: str) -> "object":
    code = _load_prelude() + "\n" + TRIAL.replace("{CMD}", cmd).replace("{ARGS}", args)
    return await backend.execute_lisp(code)


async def main() -> int:
    backend = FileIPCBackend()
    init = await backend.initialize()
    if not init.ok:
        print(f"FAIL: initialize: {init.error}")
        return 1

    # --- A: 门窗属性 ---
    await run(backend, "TGWALL", '(t20mcp:pt 0 0) (t20mcp:pt 3000 0) ""')
    await run(backend, "TOPENING", '(t20mcp:pt 1500 0) ""')
    props = " ".join(f'"{p}"' for p in OPENING_PROPS)
    got = await backend.execute_lisp(PROBE_GET.replace("{PROPS}", props))
    print(f"[A1 TCH_OPENING get] {got.payload if got.ok else got.error}")

    pairs = '(cons "Width" 1200.0) (cons "Height" 2000.0) (cons "SillHeight" 600.0)'
    put = await backend.execute_lisp(PROBE_PUT.replace("{PAIRS}", pairs))
    print(f"[A2 put 试写] {put.payload if put.ok else put.error}")
    verify = await backend.execute_lisp(
        PROBE_GET.replace("{PROPS}", '"Width" "Height" "SillHeight"'))
    print(f"[A3 回读验证] {verify.payload if verify.ok else verify.error}")

    await backend.undo()  # opening
    await backend.undo()  # wall
    print(f"清理后实体数: {await count(backend)}")

    # --- B: TAXISGRID ---
    baseline = acad_windows()
    before = await count(backend)
    result = await run(backend, "TAXISGRID", '""')
    if not result.ok and "Timeout" in (result.error or ""):
        closed = dismiss_new_windows(baseline)
        print(f"[B TAXISGRID] TIMEOUT(弹框) -> 自动关闭: {closed or '(未发现新窗口)'}")
        time.sleep(1.0)
        ping = await backend._dispatch("ping", {})
        await backend.execute_lisp(RESTORE_ENV)
        print(f"  恢复: ping ok={ping.ok}")
    else:
        after = await count(backend)
        print(f"[B TAXISGRID] ok={result.ok} entities {before}->{after} error={result.error!r}")
        if after > before:
            await backend.undo()
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
