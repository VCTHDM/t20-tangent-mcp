"""真机联调 Step 26 — 命令行提示捕获 + TUpdSpace 试驱动.

GPT 两轮调研 (docs/research/2026-06-13_*) 结论: 网络与安装目录均无
TGColumn/TDimTP/TSWall/TUpdSpace 的提示序列, 唯一出路是真机捕获。

Phase A — 提示捕获 (每命令隔离, 不盲试序列):
  建前置实体 → vl-cmdf 启动命令 (不给参数) → 读 LASTPROMPT/CMDACTIVE →
  cancel → UNDO 清理。弹模态框则 dispatch 超时, 由取证 ESC 恢复并记录窗口。

Phase B — TUpdSpace 试驱动 (仅当 Phase A 拿到可判读提示):
  四段闭合 TCH_WALL → 按提示关键词分支 (选择对象 / 点取内部点) →
  实体增量 + 类型校验 (期望 TCH_SPACE)。两轮不成即停。

用法: uv run python scripts/itest_26_prompt_capture.py
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
from t20_mcp.tools.tangent import _load_prelude, generate_lisp

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

CAPTURE = """
(defun c:t20mcp-cap ( / t20mcp:saved *error* t20mcp:p1 t20mcp:a1)
  (setq t20mcp:result "")
  (setq t20mcp:saved (t20mcp:begin "capture"))
  (defun *error* (m) (t20mcp:on-error m t20mcp:saved))
  (vl-catch-all-apply 'vl-cmdf (list "{CMD}"))
  (setq t20mcp:a1 (getvar "CMDACTIVE"))
  (setq t20mcp:p1 (vl-princ-to-string (getvar "LASTPROMPT")))
  (t20mcp:cancel-pending)
  ;; LASTPROMPT 在命令挂起时不更新, 取消后才刷新 (itest_26 第一轮教训),
  ;; 取消前后各读一次对比。
  (setq t20mcp:result
        (strcat "active=" (itoa t20mcp:a1)
                " pre=" t20mcp:p1
                " post=" (vl-princ-to-string (getvar "LASTPROMPT"))))
  (t20mcp:end "capture" t20mcp:saved)
  (princ))
(c:t20mcp-cap)
t20mcp:result
"""

# TUpdSpace 试驱动: 全选墙体 -> 回车 (若提示是选择类); {EXTRA} 留给第二轮变体
UPDSPACE_TRIAL_SELECT = """
(defun c:t20mcp-upds ( / t20mcp:saved *error* t20mcp:prev t20mcp:new t20mcp:ss)
  (setq t20mcp:result "")
  (setq t20mcp:saved (t20mcp:begin "updspace"))
  (defun *error* (m) (t20mcp:on-error m t20mcp:saved))
  (setq t20mcp:prev (entlast))
  (setq t20mcp:ss (ssget "_X" '((0 . "TCH_WALL"))))
  (setq t20mcp:rc (t20mcp:call "TUPDSPACE" (list t20mcp:ss "")))
  (setq t20mcp:new (entlast))
  (setq t20mcp:result
        (strcat "rc=" (if t20mcp:rc "T" "nil")
                " newtype=" (if (and t20mcp:new (not (eq t20mcp:prev t20mcp:new)))
                                (cdr (assoc 0 (entget t20mcp:new)))
                                "none")
                " active=" (itoa (getvar "CMDACTIVE"))))
  (t20mcp:cancel-pending)
  (t20mcp:end "updspace" t20mcp:saved)
  (princ))
(c:t20mcp-upds)
t20mcp:result
"""

UPDSPACE_TRIAL_POINT = """
(defun c:t20mcp-upds2 ( / t20mcp:saved *error* t20mcp:prev t20mcp:new)
  (setq t20mcp:result "")
  (setq t20mcp:saved (t20mcp:begin "updspace2"))
  (defun *error* (m) (t20mcp:on-error m t20mcp:saved))
  (setq t20mcp:prev (entlast))
  (setq t20mcp:rc (t20mcp:call "TUPDSPACE" (list (t20mcp:pt 2000 1500) "")))
  (setq t20mcp:new (entlast))
  (setq t20mcp:result
        (strcat "rc=" (if t20mcp:rc "T" "nil")
                " newtype=" (if (and t20mcp:new (not (eq t20mcp:prev t20mcp:new)))
                                (cdr (assoc 0 (entget t20mcp:new)))
                                "none")
                " active=" (itoa (getvar "CMDACTIVE"))))
  (t20mcp:cancel-pending)
  (t20mcp:end "updspace2" t20mcp:saved)
  (princ))
(c:t20mcp-upds2)
t20mcp:result
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


def forensic_esc(baseline: set[int]) -> list[str]:
    seen = []
    for hwnd in acad_windows() - baseline:
        cls = win32gui.GetClassName(hwnd)
        title = win32gui.GetWindowText(hwnd)
        children: list[str] = []

        def cb(child: int, _: object) -> bool:
            try:
                children.append(
                    f"{win32gui.GetClassName(child)}:{win32gui.GetWindowText(child)!r}"
                )
            except Exception:
                pass
            return True

        try:
            win32gui.EnumChildWindows(hwnd, cb, None)
        except Exception:
            pass
        seen.append(f"{cls} title={title!r} children={children[:12]}")
        win32gui.PostMessage(hwnd, win32con.WM_KEYDOWN, win32con.VK_ESCAPE, 0)
        win32gui.PostMessage(hwnd, win32con.WM_KEYUP, win32con.VK_ESCAPE, 0)
    return seen


async def count(backend: FileIPCBackend) -> int:
    result = await backend.entity_count()
    if not result.ok:
        print(f"[count] blocked/failed: {result.error}")
        return -1
    return result.payload["count"]


async def cleanup_to(backend: FileIPCBackend, baseline: int) -> int:
    rounds = 0
    while (c := await count(backend)) > baseline and c >= 0 and rounds < 12:
        undo = await backend.undo()
        rounds += 1
        if not undo.ok:
            break
    await backend.execute_lisp(RESET_ENV)
    return await count(backend)


async def make_wall(backend: FileIPCBackend, x1, y1, x2, y2) -> bool:
    r = await backend.execute_lisp(
        generate_lisp(
            "wall",
            {"x1": x1, "y1": y1, "x2": x2, "y2": y2,
             "left_width": 120, "right_width": 120, "height": 3000, "wall_type": "砖"},
        )
    )
    return r.ok


async def capture(backend: FileIPCBackend, cmd: str, prereq) -> str:
    baseline_windows = acad_windows()
    baseline = await count(backend)
    if prereq:
        await prereq()
    r = await backend.execute_lisp(_load_prelude() + CAPTURE.replace("{CMD}", cmd))
    if r.ok:
        out = str(r.payload)
    else:
        windows = forensic_esc(baseline_windows)
        out = f"TIMEOUT/blocked windows={windows or '(none)'}"
        await asyncio.sleep(1.0)
        if backend._command_hwnd:
            for _ in range(2):
                win32gui.PostMessage(
                    backend._command_hwnd, win32con.WM_KEYDOWN, win32con.VK_ESCAPE, 0
                )
                win32gui.PostMessage(
                    backend._command_hwnd, win32con.WM_KEYUP, win32con.VK_ESCAPE, 0
                )
        await asyncio.sleep(0.5)
    final = await cleanup_to(backend, baseline)
    print(f"[{cmd}] {out}")
    print(f"    cleanup -> entities={final} (baseline {baseline})")
    return out


async def main() -> int:
    backend = FileIPCBackend()
    init = await backend.initialize()
    if not init.ok:
        print(f"FAIL: initialize: {init.error}")
        return 1
    await backend.execute_lisp(RESET_ENV)

    async def walls_rect():
        await make_wall(backend, 0, 0, 4000, 0)
        await make_wall(backend, 4000, 0, 4000, 3000)
        await make_wall(backend, 4000, 3000, 0, 3000)
        await make_wall(backend, 0, 3000, 0, 0)

    async def one_wall():
        await make_wall(backend, 0, 0, 3000, 0)

    async def one_line():
        await backend.create_line(0, 0, 3000, 0)

    print("=== Phase A: 提示捕获 ===")
    prompts: dict[str, str] = {}
    prompts["TGCOLUMN"] = await capture(backend, "TGCOLUMN", None)
    prompts["TDIMTP"] = await capture(backend, "TDIMTP", one_wall)
    prompts["TSWALL"] = await capture(backend, "TSWALL", one_line)
    prompts["TUPDSPACE"] = await capture(backend, "TUPDSPACE", walls_rect)

    print("=== Phase B: TUpdSpace 试驱动 (两轮预算) ===")
    upd_prompt = prompts.get("TUPDSPACE", "")
    baseline = await count(backend)
    await walls_rect()
    wall_count = await count(backend)
    print(f"[updspace] 闭合墙就绪 entities {baseline}->{wall_count}")

    trial = UPDSPACE_TRIAL_SELECT
    if "点取" in upd_prompt or "内部" in upd_prompt:
        trial = UPDSPACE_TRIAL_POINT
    r1 = await backend.execute_lisp(_load_prelude() + trial)
    after1 = await count(backend)
    print(f"[updspace round1] ok={r1.ok} payload={r1.payload!r} entities={after1}")

    created = after1 > wall_count
    if not created:
        other = (
            UPDSPACE_TRIAL_POINT if trial is UPDSPACE_TRIAL_SELECT else UPDSPACE_TRIAL_SELECT
        )
        r2 = await backend.execute_lisp(_load_prelude() + other)
        after2 = await count(backend)
        print(f"[updspace round2] ok={r2.ok} payload={r2.payload!r} entities={after2}")
        created = after2 > wall_count

    final = await cleanup_to(backend, baseline)
    env = await backend.drawing_get_variables(["CMDACTIVE", "CMDDIA", "FILEDIA", "OSMODE"])
    print(f"[cleanup] entities={final} env={env.payload}")
    print(f"[verdict] updspace_created_entity={created}")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
