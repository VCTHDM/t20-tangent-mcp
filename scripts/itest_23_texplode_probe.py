"""真机联调 Step 23 — 探索: TExplode 实体级副本分解管线 (UNDO 包裹).

itest_22 已证: TCH_WALL 在 DXF 中 proxy graphics 为空 (8 字节头), 非破坏
proxy 解码路线不通。文件副本路线亦不可行 (SAVEAS 挟持会话 / accoreconsole
无天正 ARX / 切文档断 LISP 命名空间)。本脚本验证替代设计:

  UNDO 组内: COPY 复制目标实体到远处暂存区 (+1e6,+1e6) → 仅对副本
  TEXPLODE → entnext 走查分解产物 (类型+数量) → Python 端 UNDO 整组回滚。

用户原实体全程不被修改; 失败路径由 prelude *error* + ESC 兜底恢复。

第一轮教训 (2026-06-13): 原位复制 (位移 0,0) 会触发天正「处理重合的墙体」
模态对话框 (#32770, 删除墙A/墙B) —— 副本必须位移出原位, 远离一切既有实体。

用法: uv run python scripts/itest_23_texplode_probe.py
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

# 副本 + 分解 + 走查。{HANDLE} 为目标实体 handle。
# 返回字符串: "copied=<T/nil> exploded=<T/nil> products=TYPE:N;TYPE:N;..."
PROBE = """
(defun c:t20mcp-texp ( / t20mcp:saved *error* t20mcp:src t20mcp:ss t20mcp:mark
                         t20mcp:e t20mcp:copy t20mcp:rc t20mcp:acc t20mcp:ty)
  (setq t20mcp:saved (t20mcp:begin "texplode-probe"))
  (defun *error* (m) (t20mcp:on-error m t20mcp:saved))
  (setq t20mcp:src (handent "{HANDLE}"))
  (setq t20mcp:mark (entlast))
  ;; 1. 复制到远处暂存区 (原位复制会触发天正重合墙对话框, 见 docstring)
  (setq t20mcp:ss (ssadd t20mcp:src (ssadd)))
  (vl-cmdf "_.COPY" t20mcp:ss "" "_non" "0,0" "_non" "1000000,1000000")
  (setq t20mcp:copy (entlast))
  (if (or (null t20mcp:copy) (eq t20mcp:copy t20mcp:mark))
      (progn (t20mcp:fail "texplode-probe" t20mcp:saved "copy-failed") (princ))
      (progn
        ;; 2. 仅对副本 TEXPLODE
        (setq t20mcp:ss (ssadd t20mcp:copy (ssadd)))
        (setq t20mcp:rc (t20mcp:call "TEXPLODE" (list t20mcp:ss "")))
        ;; 3. 走查 mark 之后的全部实体 (分解产物; 副本自身可能已被删除)
        (setq t20mcp:acc "")
        (setq t20mcp:e (if t20mcp:mark (entnext t20mcp:mark) (entnext)))
        (while t20mcp:e
          (if (entget t20mcp:e)
              (progn
                (setq t20mcp:ty (cdr (assoc 0 (entget t20mcp:e))))
                (setq t20mcp:acc (strcat t20mcp:acc t20mcp:ty ";"))))
          (setq t20mcp:e (entnext t20mcp:e)))
        (t20mcp:end "texplode-probe" t20mcp:saved)
        (setq t20mcp:result
              (strcat "rc=" (if t20mcp:rc "T" "nil") " products=" t20mcp:acc))))
  (princ))
(c:t20mcp-texp)
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


def esc_new_windows(baseline: set[int]) -> list[str]:
    """记录新窗口标题+子控件文本 (取证), 然后只发 ESC。"""
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
        seen.append(f"{cls} title={title!r} children={children}")
        win32gui.PostMessage(hwnd, win32con.WM_KEYDOWN, win32con.VK_ESCAPE, 0)
        win32gui.PostMessage(hwnd, win32con.WM_KEYUP, win32con.VK_ESCAPE, 0)
    return seen


async def count(backend: FileIPCBackend) -> int:
    """实体数; 被对话框阻塞等异常时返回 -1, 不抛断言 (清理路径要能走完)。"""
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
    baseline_windows = acad_windows()

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

    probe = await backend.execute_lisp(
        _load_prelude() + PROBE.replace("{HANDLE}", handle)
    )
    print(f"[texplode] ok={probe.ok} payload={probe.payload!r} error={probe.error!r}")

    if not probe.ok and "Timeout" in (probe.error or ""):
        new = esc_new_windows(baseline_windows)
        print(f"  弹框/挂起, ESC 恢复: new_windows={new or '(none)'}")
        if backend._command_hwnd:
            for _ in range(2):
                win32gui.PostMessage(
                    backend._command_hwnd, win32con.WM_KEYDOWN, win32con.VK_ESCAPE, 0
                )
                win32gui.PostMessage(
                    backend._command_hwnd, win32con.WM_KEYUP, win32con.VK_ESCAPE, 0
                )
        await asyncio.sleep(1.0)

    # 清理: UNDO 到基线
    rounds = 0
    while await count(backend) > before and rounds < 10:
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
