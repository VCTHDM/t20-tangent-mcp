"""Interactive retry helper for live scripts that create both doors and windows."""

from __future__ import annotations

import asyncio
import sys
from typing import Any

from t20_mcp.backends.base import CommandResult
from t20_mcp.tools.tangent import generate_lisp, parse_opening_status


async def execute_opening_with_retry(
    backend: Any,
    operation: str,
    data: dict[str, Any],
) -> CommandResult:
    """Execute one door/window request and retry after an explicit panel switch."""
    code = generate_lisp(operation, data)
    while True:
        result = await backend.execute_lisp(code)
        if not result.ok:
            return result
        status = parse_opening_status(result.payload)
        if status.get("status") == "OK":
            return result
        if status.get("status") != "MODE-MISMATCH":
            return CommandResult(
                ok=False,
                error=f"{operation} 未返回可识别的 opening 状态: {result.payload!r}",
            )
        if status.get("rollback") != "ok":
            return CommandResult(
                ok=False,
                error=f"{operation} 模式错误实体回滚失败: {result.payload!r}",
            )
        target = "门" if operation == "door" else "窗"
        message = (
            f"{operation} 检测到面板模式不符，错误实体已回滚。"
            f"请把天正门窗面板切换到{target}模式后按 Enter 原参数重试: "
        )
        if not sys.stdin.isatty():
            return CommandResult(
                ok=False,
                payload={
                    "code": "OPENING_MODE_MISMATCH",
                    "retry_operation": operation,
                    "retry_data": data,
                },
                error=message.strip(),
            )
        await asyncio.to_thread(input, message)
        # 点击“插门/插窗”不仅切模式，也会启动一次 TOpening。复用 FileIPC
        # 已验证的超时恢复路径：下一次 dispatch 先发 ESC，再下发原参数重试。
        if hasattr(backend, "_needs_cancel"):
            backend._needs_cancel = True
