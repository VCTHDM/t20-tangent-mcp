"""真机联调 Step 1 — 引导链路 (P0-3 / P1-1 / P0-1 验收).

流程:
  1. find_autocad_window: 进程名主判据识别 T20 主窗 (P1-1)
  2. initialize(): ping 失败则自动引导 —— 把 mcp_dispatch.lsp 拷到 ASCII 路径
     (IPC 目录), 先经命令行注入 (load ...), 失败再用 COM SendCommand fallback
     后重试 ping (P0-3)
  3. drawing-get-variables: 读 ACADVER/DWGNAME 确认环境
  4. 中文编码往返: layer-create "T20MCP测试图层" → layer-list 验证无损 (P0-1/P2-1)

用法: uv run python scripts/itest_01_bringup.py
"""

from __future__ import annotations

import asyncio
import ctypes
import shutil
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))  # for _live_lock
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from _live_lock import live_lock_or_exit  # noqa: E402
from t20_mcp.backends.file_ipc import FileIPCBackend, find_autocad_window  # noqa: E402
from t20_mcp.config import IPC_DIR, LISP_DIR

WM_CHAR = 0x0102
TEST_LAYER = "T20MCP测试图层"


def type_line(hwnd: int, text: str) -> None:
    """向 AutoCAD 命令行 (MDIClient) 注入一行文本 + 回车 (与 backend 同机制)。"""
    post = ctypes.windll.user32.PostMessageW
    for ch in text:
        post(hwnd, WM_CHAR, ord(ch), 0)
    post(hwnd, WM_CHAR, 0x0D, 0)
    time.sleep(0.2)


def send_load_via_com(load_path: str) -> bool:
    """Fallback loader: AutoCAD COM SendCommand is more reliable than keyboard
    injection when focus or a modeless T20 palette eats typed characters."""
    try:
        import win32com.client
    except Exception as exc:
        print(f"  COM fallback 不可用: {exc!r}")
        return False

    try:
        acad = win32com.client.GetActiveObject("AutoCAD.Application")
        doc = acad.ActiveDocument
        for line in (
            '(setvar "SECURELOAD" 0)',
            f'(load "{load_path}")',
            '(setvar "SECURELOAD" 1)',
        ):
            print(f"  COM SendCommand: {line}")
            doc.SendCommand(line + "\n")
            time.sleep(1.0)
        return True
    except Exception as exc:
        print(f"  COM fallback 失败: {exc!r}")
        return False


async def bootstrap_dispatcher(backend: FileIPCBackend) -> bool:
    """拷贝 dispatcher 到 ASCII 路径并经命令行 (load), 绕开中文项目路径与
    SECURELOAD 弹框 (load 前临时置 0, 完成后恢复 1)。命令行注入失败时改用
    COM SendCommand fallback。"""
    Path(IPC_DIR).mkdir(parents=True, exist_ok=True)
    dst = Path(IPC_DIR) / "mcp_dispatch.lsp"
    shutil.copy(LISP_DIR / "mcp_dispatch.lsp", dst)
    load_path = str(dst).replace("\\", "/")

    target = backend._command_hwnd or backend._hwnd
    if target:
        print(f"  引导加载(PostMessage): (load \"{load_path}\")")
        type_line(target, '(setvar "SECURELOAD" 0)')
        type_line(target, f'(load "{load_path}")')
        time.sleep(1.0)
        type_line(target, '(setvar "SECURELOAD" 1)')
        result = await backend._dispatch("ping", {})
        print(f"  PostMessage 引导后 ping: ok={result.ok} payload={result.payload!r} error={result.error!r}")
        if result.ok:
            return True
    else:
        print("  !! 无命令行句柄, 跳过 PostMessage 引导")

    print("  PostMessage 引导未通过, 尝试 COM SendCommand fallback")
    if not send_load_via_com(load_path):
        return False
    time.sleep(1.0)
    result = await backend._dispatch("ping", {})
    print(f"  COM fallback 后 ping: ok={result.ok} payload={result.payload!r} error={result.error!r}")
    return result.ok


async def main() -> int:
    # --- Step 1: 窗口识别 (P1-1) ---
    hwnd = find_autocad_window()
    print(f"[1] find_autocad_window -> {hwnd}")
    if not hwnd:
        print("FAIL: 未找到 acad.exe 窗口")
        return 1

    backend = FileIPCBackend()
    init = await backend.initialize()
    print(f"[2] initialize -> ok={init.ok} payload={init.payload!r}")
    if not init.ok:
        print(f"    error: {init.error}")
        if (
            "not loaded" in (init.error or "")
            or "mcp_dispatch" in (init.error or "")
            or "dispatcher ping failed" in (init.error or "")
            or "command-line input" in (init.error or "")
        ):
            if not await bootstrap_dispatcher(backend):
                print("FAIL: dispatcher 引导失败")
                return 1
        else:
            return 1

    # --- Step 3: 环境变量 ---
    vars_result = await backend.drawing_get_variables(["ACADVER", "DWGNAME", "CLAYER", "CMDDIA", "FILEDIA", "OSMODE"])
    print(f"[3] drawing-get-variables -> ok={vars_result.ok} payload={vars_result.payload!r}")
    if not vars_result.ok:
        print(f"FAIL: {vars_result.error}")
        return 1

    # --- Step 4: 中文编码往返 (P0-1/P2-1) ---
    create = await backend.layer_create(TEST_LAYER, "yellow")
    print(f"[4a] layer-create {TEST_LAYER!r} -> ok={create.ok} payload={create.payload!r} error={create.error!r}")
    layers = await backend.layer_list()
    names = [item.get("name") for item in (layers.payload or {}).get("layers", [])] if layers.ok else []
    roundtrip = TEST_LAYER in names
    print(f"[4b] layer-list 含 {TEST_LAYER!r}: {roundtrip}  (layers={names})")

    ok = init.ok or roundtrip
    print()
    print("=== Step1 结果 ===")
    print(f"窗口识别(P1-1): PASS (hwnd={hwnd})")
    print(f"ping 往返(P0-3): {'PASS' if ok else 'FAIL'}")
    print(f"中文编码往返(P0-1/P2-1): {'PASS' if roundtrip else 'FAIL'}")
    return 0 if (ok and roundtrip) else 1


if __name__ == "__main__":
    _lock = live_lock_or_exit(__file__)
    raise SystemExit(asyncio.run(main()))
