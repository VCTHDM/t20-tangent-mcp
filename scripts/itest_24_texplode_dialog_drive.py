"""真机联调 Step 24 — 探索: TEXPLODE 对话框按钮驱动 (BM_CLICK, 白名单).

itest_23 证实: TEXPLODE 必弹「分解对象」模态框 (#32770), 子按钮:
  分解当前选中的天正对象 / 分解本图所有天正对象 / 分解块参照内天正对象 /
  确定 / 取消
纯命令行驱动不可行。本脚本验证 Python 侧对话框按钮自动化:

  LISP (阻塞于框): 复制目标到暂存区 (+1e6) → sssetfirst 预选副本 →
    TEXPLODE → (框被 Python 点掉后恢复执行) → 走查分解产物 → 返回类型清单
  Python 并发: 轮询「分解对象」框 → BM_CLICK「分解当前选中的天正对象」→
    BM_CLICK「确定」

安全边界: 只点白名单标题/按钮文本的对话框; 绝不点「分解本图所有天正对象」
(会破坏用户实体); 失败路径 ESC + UNDO 回滚; 严禁 WM_CLOSE。

用法: uv run python scripts/itest_24_texplode_dialog_drive.py
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

BM_CLICK = 0x00F5

DIALOG_TITLE = "分解对象"
RADIO_TEXT = "分解当前选中的天正对象"
OK_TEXT = "确定"

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

PROBE = """
(defun c:t20mcp-texp ( / t20mcp:saved *error* t20mcp:src t20mcp:ss t20mcp:mark
                         t20mcp:e t20mcp:copy t20mcp:rc t20mcp:acc t20mcp:ty t20mcp:pf)
  (setq t20mcp:saved (t20mcp:begin "texplode-drive"))
  (defun *error* (m) (t20mcp:on-error m t20mcp:saved))
  (setq t20mcp:src (handent "{HANDLE}"))
  (setq t20mcp:mark (entlast))
  (setq t20mcp:ss (ssadd t20mcp:src (ssadd)))
  (vl-cmdf "_.COPY" t20mcp:ss "" "_non" "0,0" "_non" "1000000,1000000")
  (setq t20mcp:copy (entlast))
  (if (or (null t20mcp:copy) (eq t20mcp:copy t20mcp:mark))
      (progn (t20mcp:fail "texplode-drive" t20mcp:saved "copy-failed") (princ))
      (progn
        ;; 方案 B: 选择集经 vl-cmdf 参数队列, 在对话框「确定」后喂给
        ;; 「选择对象」提示 (预选/sssetfirst 两轮均被命令启动清空, 无效)。
        (setq t20mcp:ss (ssadd t20mcp:copy (ssadd)))
        (setq t20mcp:rc (t20mcp:call "TEXPLODE" (list t20mcp:ss "")))
        (setq t20mcp:acc "")
        (setq t20mcp:e (if t20mcp:mark (entnext t20mcp:mark) (entnext)))
        (while t20mcp:e
          (if (entget t20mcp:e)
              (progn
                (setq t20mcp:ty (cdr (assoc 0 (entget t20mcp:e))))
                (setq t20mcp:acc (strcat t20mcp:acc t20mcp:ty ";"))))
          (setq t20mcp:e (entnext t20mcp:e)))
        (t20mcp:end "texplode-drive" t20mcp:saved)
        (setq t20mcp:result
              (strcat "rc=" (if t20mcp:rc "T" "nil") " products=" t20mcp:acc))))
  (princ))
(c:t20mcp-texp)
t20mcp:result
"""


def find_explode_dialog() -> int | None:
    found: list[int] = []

    def cb(hwnd: int, _: object) -> bool:
        try:
            if not win32gui.IsWindowVisible(hwnd):
                return True
            if win32gui.GetClassName(hwnd) != "#32770":
                return True
            if win32gui.GetWindowText(hwnd) != DIALOG_TITLE:
                return True
            _, pid = win32process.GetWindowThreadProcessId(hwnd)
            if _process_image_name(pid) == "acad.exe":
                found.append(hwnd)
        except Exception:
            pass
        return True

    win32gui.EnumWindows(cb, None)
    return found[0] if found else None


def find_button(dialog: int, text: str) -> int | None:
    found: list[int] = []

    def cb(child: int, _: object) -> bool:
        try:
            if (
                win32gui.GetClassName(child) == "Button"
                and win32gui.GetWindowText(child) == text
            ):
                found.append(child)
        except Exception:
            pass
        return True

    try:
        win32gui.EnumChildWindows(dialog, cb, None)
    except Exception:
        pass
    return found[0] if found else None


async def drive_dialog(timeout: float = 8.0) -> str:
    """等「分解对象」框出现, 点白名单按钮。返回结果描述。"""
    deadline = asyncio.get_event_loop().time() + timeout
    while asyncio.get_event_loop().time() < deadline:
        dialog = find_explode_dialog()
        if dialog:
            radio = find_button(dialog, RADIO_TEXT)
            ok = find_button(dialog, OK_TEXT)
            if not radio or not ok:
                return f"dialog-found-but-buttons-missing radio={radio} ok={ok}"
            win32gui.PostMessage(radio, BM_CLICK, 0, 0)
            await asyncio.sleep(0.3)
            win32gui.PostMessage(ok, BM_CLICK, 0, 0)
            await asyncio.sleep(0.5)
            if find_explode_dialog() is None:
                return "clicked-ok-dialog-closed"
            # 再试一次确定
            win32gui.PostMessage(ok, BM_CLICK, 0, 0)
            await asyncio.sleep(0.7)
            return (
                "clicked-ok-dialog-closed"
                if find_explode_dialog() is None
                else "dialog-still-open"
            )
        await asyncio.sleep(0.25)
    return "dialog-never-appeared"


async def count(backend: FileIPCBackend) -> int:
    result = await backend.entity_count()
    if not result.ok:
        print(f"[count] blocked/failed: {result.error}")
        return -1
    return result.payload["count"]


async def main() -> int:
    backend = FileIPCBackend()
    init = await backend.initialize()
    if not init.ok:
        print(f"FAIL: initialize: {init.error}")
        return 1

    await backend.execute_lisp(RESET_ENV)
    before = await count(backend)

    wall = await backend.execute_lisp(
        generate_lisp(
            "wall",
            {
                "x1": 0, "y1": 0, "x2": 3000, "y2": 0,
                "left_width": 120, "right_width": 120, "height": 3000,
                "wall_type": "砖",
            },
        )
    )
    handle_r = await backend.execute_lisp(
        '(if (entlast) (cdr (assoc 5 (entget (entlast)))) "none")'
    )
    handle = (handle_r.payload or "").strip('"') if handle_r.ok else "none"
    print(f"[wall] ok={wall.ok} handle={handle} entities {before}->{await count(backend)}")
    if not wall.ok or handle in ("none", ""):
        print("FAIL: 墙体创建失败")
        return 1

    lisp_task = asyncio.create_task(
        backend.execute_lisp(_load_prelude() + PROBE.replace("{HANDLE}", handle))
    )
    click_result = await drive_dialog()
    print(f"[dialog] {click_result}")
    probe = await lisp_task
    print(f"[texplode] ok={probe.ok} payload={probe.payload!r} error={probe.error!r}")

    if backend._command_hwnd and not probe.ok:
        for _ in range(2):
            win32gui.PostMessage(
                backend._command_hwnd, win32con.WM_KEYDOWN, win32con.VK_ESCAPE, 0
            )
            win32gui.PostMessage(
                backend._command_hwnd, win32con.WM_KEYUP, win32con.VK_ESCAPE, 0
            )
        await asyncio.sleep(1.0)

    rounds = 0
    while (c := await count(backend)) > before and rounds < 10:
        undo = await backend.undo()
        rounds += 1
        if not undo.ok:
            print(f"[cleanup] undo failed: {undo.error}")
            break
    reset = await backend.execute_lisp(RESET_ENV)
    env = await backend.drawing_get_variables(["CMDACTIVE", "CMDDIA", "FILEDIA", "OSMODE"])
    final = await count(backend)
    print(f"[cleanup] entities={final} (baseline {before}) reset={reset.ok} env={env.payload}")

    ok = probe.ok and "products=" in (probe.payload or "") and final == before
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
