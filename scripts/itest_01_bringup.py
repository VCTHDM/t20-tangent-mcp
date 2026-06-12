"""真机联调 Step 1 — 引导链路 (P0-3 / P1-1 / P0-1 验收).

流程:
  1. find_autocad_window: 进程名主判据识别 T20 主窗 (P1-1)
  2. initialize(): ping 失败则自动引导 —— 把 mcp_dispatch.lsp 拷到 ASCII 路径
     (IPC 目录), 经命令行注入 (load ...) 后重试 ping (P0-3)
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

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from t20_mcp.backends.file_ipc import FileIPCBackend, find_autocad_window
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


async def bootstrap_dispatcher(backend: FileIPCBackend) -> bool:
    """拷贝 dispatcher 到 ASCII 路径并经命令行 (load), 绕开中文项目路径与
    SECURELOAD 弹框 (load 前临时置 0, 完成后恢复 1)。"""
    target = backend._command_hwnd or backend._hwnd
    if not target:
        print("  !! 无命令行句柄, 无法引导")
        return False
    Path(IPC_DIR).mkdir(parents=True, exist_ok=True)
    dst = Path(IPC_DIR) / "mcp_dispatch.lsp"
    shutil.copy(LISP_DIR / "mcp_dispatch.lsp", dst)
    load_path = str(dst).replace("\\", "/")
    print(f"  引导加载: (load \"{load_path}\")")
    type_line(target, '(setvar "SECURELOAD" 0)')
    type_line(target, f'(load "{load_path}")')
    time.sleep(1.0)
    type_line(target, '(setvar "SECURELOAD" 1)')
    result = await backend._dispatch("ping", {})
    print(f"  引导后 ping: ok={result.ok} payload={result.payload!r} error={result.error!r}")
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
        if "not loaded" in (init.error or "") or "mcp_dispatch" in (init.error or ""):
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
    raise SystemExit(asyncio.run(main()))
