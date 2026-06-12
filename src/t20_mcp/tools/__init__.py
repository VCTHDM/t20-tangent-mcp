"""T20 Tangent (天正) 专业实体工具包。

本子包在不改动 dispatcher / IPC 层的前提下, 新增面向天正建筑实体的
consolidated MCP 工具。所有命令封装严格遵循 CLAUDE.md 铁律:
仅走 LISP 模板 + 参数注入, 不硬编码键击序列。
"""

from t20_mcp.tools.tangent import (
    ParamError,
    generate_lisp,
    is_paren_balanced,
    register_tangent_tool,
)

__all__ = [
    "ParamError",
    "generate_lisp",
    "is_paren_balanced",
    "register_tangent_tool",
]
