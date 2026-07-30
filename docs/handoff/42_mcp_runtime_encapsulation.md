# Handoff 42 — MCP 运行时与工具注册封装

日期：2026-07-29（Asia/Shanghai）

## 1. 目标

Handoff 41 完成了 MCP Python SDK v2 与 `2026-07-28` 协议迁移，但工具仍直接通过
9 处服务器装饰器注册，业务返回值也主要停留在 JSON 文本。本轮把协议适配从业务
分派中抽离，保持 AutoCAD/T20 执行行为不变。

## 2. 封装边界

- 新增 `src/t20_mcp/mcp_runtime.py`，集中维护兼容服务名、现代/legacy 协议版本
  常量、`ToolSpec`、服务器工厂和批量注册。
- `server.py` 只声明 8 个通用业务处理器及统一 `TOOL_SPECS`；`tangent.py` 暴露
  第 9 个 spec，并保留 `register_tangent_tool()` 兼容入口。
- 注册适配器保留原业务函数输入签名，以 SDK v2 原生
  `Annotated[CallToolResult, ToolEnvelope]` 发布 `outputSchema`。
- 线路转换保留旧 JSON `TextContent` 和可选 `ImageContent`，同时发布
  `structuredContent`。业务 envelope 的 `ok=false` 固定映射为 `isError=true`；
  业务失败仍是 tool execution error，不伪装成 JSON-RPC 协议错误。
- `ToolEnvelope` 固定声明 `ok`，并公开常用 `payload/error/hint` 字段；各操作的
  额外结构继续允许透传，避免机械拆分 33 个已验证 T20 子命令。

## 3. 合同与兼容性

- 9 个工具全部从声明目录注册，服务身份仍为 `autocad-mcp`，包版本仍为 `3.2.0`。
- 现代 `2026-07-28` 路径验证 `server/discover`、9 个 `outputSchema`、成功
  `structuredContent` 和失败 `isError`。
- legacy `2025-11-25` 路径继续通过独立会话/子进程验证工具列表、schema 与结构化
  结果；旧调用方仍可读取原来的文本 content。
- `tests/test_mcp_runtime.py` 单独覆盖 JSON 成功、JSON 失败、文本+截图和既有
  `CallToolResult` 的归一化。

## 4. 验证与边界

本轮离线门禁：

- `uv run pytest -q`：273 passed。
- `uv run ruff check src tests scripts`：PASS。
- `uv run ruff format --check src tests scripts`：PASS。
- `uv lock --check`：PASS。
- `uv run python -m compileall -q src scripts tests`：PASS。
- `uv build`：PASS。
- `uv run python scripts/itest_19_mcp_stdio_smoke.py`：现代
  `2026-07-28` 的工具/schema/成功/失败合同 PASS；独立 legacy `2025-11-25`
  工具/schema/结构化结果 PASS。
- `git diff --check`：PASS。

本轮没有修改 File IPC、LISP 模板、T20 命令序列、实体断言或 GUI 自动化，也没有
启动 AutoCAD/T20。Handoff 40 的 2026-07-26 fresh 33/33 仍是最近真机证据，不能
把本轮离线测试或 stdio smoke 表述为新真机 E2E。
