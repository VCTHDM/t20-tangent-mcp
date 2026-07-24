"""Compatibility helper for live scripts that create both doors and windows.

Handoff 39 起由核心 execute_opening 自动切换门窗面板模式；保留旧函数名，
避免户型/教堂/图层探针重复实现调用与状态校验。
"""

from __future__ import annotations

from typing import Any

from t20_mcp.backends.base import CommandResult
from t20_mcp.tools.tangent import execute_opening, parse_opening_status


async def execute_opening_with_retry(
    backend: Any,
    operation: str,
    data: dict[str, Any],
) -> CommandResult:
    """Execute one door/window request with automatic panel mode selection."""
    result = await execute_opening(backend, operation, data)
    if not result.ok:
        return result
    status = parse_opening_status(result.payload)
    if status.get("status") == "OK":
        return result
    return CommandResult(
        ok=False,
        error=f"{operation} 未返回成功的 opening 状态: {result.payload!r}",
    )
