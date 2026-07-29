# Handoff 41 — MCP 2026-07-28 协议迁移

日期：2026-07-29（Asia/Shanghai）

## 1. 官方基线

本轮以 2026-07-28 稳定规范与官方 Python SDK v2.0.0 为基线：

- <https://modelcontextprotocol.io/specification/2026-07-28/changelog>
- <https://github.com/modelcontextprotocol/modelcontextprotocol/releases/tag/2026-07-28>
- <https://github.com/modelcontextprotocol/python-sdk/releases/tag/v2.0.0>
- <https://py.sdk.modelcontextprotocol.io/migration/>

与本项目直接相关的破坏性变化是：协议层改为无状态请求；删除
`initialize/notifications/initialized` 握手；新增 `server/discover`；每个普通结果
必须带 `resultType`；Python SDK 公共字段改为 snake_case。完整 JSON Schema
2020-12、扩展框架、MRTR、Tasks 和订阅属于 SDK/规范能力，本项目当前没有自定义
实现这些协议面。

## 2. 仓库变更

- `mcp[cli]` 从 v1 升级并约束为 `>=2.0.0,<3`，锁文件解析到 `mcp==2.0.0` 与
  `mcp-types==2.0.0`。
- 包版本从 `3.1.0` 提升到 `3.2.0`。
- 服务类从 `FastMCP` 迁移到 `MCPServer`，继续使用兼容服务名 `autocad-mcp`，
  并显式发布当前包版本。
- Python 侧 `read_only_hint`、`mime_type`、`result_type`、`is_error` 等字段按
  SDK v2 命名；线路 JSON 仍由 SDK 输出规范规定的 camelCase。
- stdio smoke 的现代路径改用 v2 `Client(..., mode="auto")`，不得再手工调用
  legacy `ClientSession.initialize()`；独立子进程再以 `mode="legacy"` 固定验证
  `2025-11-25`。
- 单元测试覆盖现代 `2026-07-28` 服务身份/工具列表和 legacy `2025-11-25`
  工具列表，防止升级只顾新客户端。

项目里的 `backend.initialize()` 与 dispatcher `ping` 是 AutoCAD/File IPC 健康检查，
不是 MCP 协议握手或 MCP `ping`，因此继续保留。

## 3. 验证与边界

本轮离线门禁：

- `uv run pytest -q`：269 passed。
- `uv run ruff check src tests scripts`：PASS。
- `uv run ruff format --check src tests scripts`：PASS。
- `uv lock --check`：PASS。
- `uv run python -m compileall -q src scripts tests`：PASS。
- `uv build`：PASS。
- `uv run python scripts/itest_19_mcp_stdio_smoke.py`：协商
  `2026-07-28`，列出 9 个工具，`tangent.axis_lines` dry-run PASS；独立 legacy
  stdio 子进程协商 `2025-11-25` 并列出相同工具集。
- `git diff --check`：PASS。

协议迁移没有修改 File IPC、LISP 模板、T20 命令序列、实体断言或 GUI 自动化。
因此 2026-07-26 Handoff 40 的 fresh 33/33 仍是最近真机证据；本轮没有重新运行
AutoCAD/T20，也不把离线 MCP smoke 表述为新真机 E2E。
