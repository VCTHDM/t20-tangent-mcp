"""T20 Tangent (天正) 专业实体工具包。

本子包在不改动 dispatcher / IPC 协议的前提下，提供面向天正建筑实体的
consolidated MCP 工具。常规子命令走 LISP 模板与参数注入；``column`` 和
``door/window`` 是 PROJECT_RULES.md 明确允许的受控 GUI 例外，只能使用
``dialog_automation.py`` 中的白名单结构指纹、Win32 消息、结果读回与失败回滚。
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
