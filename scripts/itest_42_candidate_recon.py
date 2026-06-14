"""真机联调 Step 42 — 剩余简单候选批量侦察 (recon, 非 E2E).

对每个候选命令做最小点序列试驱动, 只采集:
  - getcname 注册状态
  - 实体增量 delta
  - entlast 类型 (是否 TCH_* 智能实体)
  - 运行后 CMDACTIVE (是否滞留, 暗示选对象步/对话框)

不宣称 E2E 成功; 每条跑完 RESET_ENV(空回车退活动命令) + undo 回滚到基线。
模态对话框候选会触发 10s 调度超时 + 下次 ESC (后端自带), 不会挂死会话。

用法: uv run python -X utf8 scripts/itest_42_candidate_recon.py
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


def esc_recover(main_hwnd: int) -> str:
    """给卡住的天正模态框发 ESC (绝不 WM_CLOSE), 返回处理掉的弹窗标题或 ''。"""
    if not main_hwnd:
        return ""
    glap = ctypes.windll.user32.GetLastActivePopup
    post = ctypes.windll.user32.PostMessageW
    dismissed = ""
    import time
    for _ in range(5):
        if ctypes.windll.user32.IsWindowEnabled(main_hwnd):
            popup = glap(main_hwnd)
            if popup == main_hwnd or not popup:
                break
        popup = glap(main_hwnd)
        if popup and popup != main_hwnd:
            dismissed = win32gui.GetWindowText(popup)
            for _ in range(4):
                post(popup, 0x0100, 0x1B, 0)
                post(popup, 0x0101, 0x1B, 0)
                time.sleep(0.12)
        post(main_hwnd, 0x0100, 0x1B, 0)
        post(main_hwnd, 0x0101, 0x1B, 0)
        time.sleep(0.5)
    return dismissed

LAST_TYPE = '(if (entlast) (cdr (assoc 0 (entget (entlast)))) "none")'

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


def probe_lisp(command: str, pts_src: str) -> str:
    """以最小点序列(末尾补空回车)试驱动 command, 返回 active 状态字符串。"""
    return f"""
(progn
  (setvar "CMDECHO" 0)
  (setq reg (if (getcname "{command}") "yes" "no"))
  (vl-catch-all-apply 'vl-cmdf (cons "{command}" {pts_src}))
  (strcat "reg=" reg " active=" (itoa (getvar "CMDACTIVE"))))
"""


# (子命令标签, 命令, 点序列源, 备注)  —— 点序列已彼此拉开, 末尾补 "" 试退循环
# Round1 结论: TRStair=干净赢(TCH_RECTSTAIR); TDrawXxxStair 族全弹 #32770 面板(拒).
# Round2: 复探 multistair(多给点)/girder/windrose (Round1 因弹框级联超时, 结果无效)。
CANDIDATES = [
    # 确认两胜者的最小序列:
    ("rstair",     "TRStair",     "(list (list 0 0 0.0) \"\")",                           "双跑楼梯"),
    ("multistair", "TMultiStair", "(list (list 12000 0 0.0) (list 12000 6000 0.0) \"\")", "多跑楼梯"),
]


async def count(backend: FileIPCBackend) -> int:
    r = await backend.entity_count()
    return r.payload["count"] if r.ok else -1


async def cleanup_to(backend: FileIPCBackend, target: int) -> None:
    await backend.execute_lisp(RESET_ENV)
    guard = 0
    while guard < 16:
        c = await count(backend)
        if c < 0 or c <= target:
            break
        await backend.undo()
        guard += 1
    await backend.execute_lisp(RESET_ENV)


async def main() -> int:
    backend = FileIPCBackend()
    init = await backend.initialize()
    if not init.ok:
        print(f"init FAIL: {init.error}")
        return 1

    print()
    print("=== Step42 剩余简单候选批量侦察 ===")
    print(f"{'label':12} {'cmd':22} {'note':8} {'reg':4} {'delta':6} {'active':7} entlast")
    print("-" * 88)
    for label, cmd, pts, note in CANDIDATES:
        await backend.execute_lisp(RESET_ENV)
        base = await count(backend)
        r = await backend.execute_lisp(probe_lisp(cmd, pts))
        after = await count(backend)
        ltype = await backend.execute_lisp(LAST_TYPE)
        delta = after - base if (after >= 0 and base >= 0) else None
        status = r.payload if r.ok else f"TIMEOUT/{r.error}"
        # 弹框侦测: 若命令滞留弹模态框, ESC 恢复并记录其标题(=该命令必弹框→拒)
        dlg = await asyncio.to_thread(esc_recover, backend._hwnd)
        dlg_note = f"  DIALOG={dlg!r}" if dlg else ""
        print(
            f"{label:12} {cmd:22} {note:8} "
            f"{'':4} {str(delta):6} {'':7} type={ltype.payload!r}  raw={status!r}{dlg_note}"
        )
        await cleanup_to(backend, base)

    final = await count(backend)
    print("-" * 88)
    print(f"final_count={final}")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
