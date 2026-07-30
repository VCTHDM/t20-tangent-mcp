# T20 MCP 当前架构说明

本文只描述当前实现。按时间追加的探索过程、失败路线与真机原始证据保存在
[`docs/handoff/`](handoff/)；历史文件中的旧路径、旧测试数和旧判断不构成当前接口。

## 1. 运行边界

项目面向 Windows、完整版 AutoCAD 与 T20 天正建筑。MCP 层注册 9 个 consolidated
工具；通用 AutoCAD 操作由 drawing/entity/layer/block/annotation/pid/view/system
分派，天正专业实体由 tangent 分派。

后端有两条路径：

- `file_ipc`：连接正在运行的 AutoCAD/T20，通过文件 IPC 与
  [`mcp_dispatch.lsp`](../lisp-code/mcp_dispatch.lsp) 往返。
- `ezdxf`：不依赖 AutoCAD 的离线 DXF 路径，只提供其 capabilities 声明支持的操作。

后端选择、路径和超时配置集中在
[`src/t20_mcp/config.py`](../src/t20_mcp/config.py)，不要在文档或调用方复制默认值。
源码树中的 `lisp-code/mcp_dispatch.lsp` 会在构建 wheel 时映射到
`t20_mcp/lisp_code/`；配置层优先使用已安装包数据，editable/source 运行才回退到
仓库根文件，避免“源码可用、安装包缺 dispatcher”。

## 2. MCP 协议层

项目使用官方 Python SDK `mcp>=2.0.0,<3` 与 `MCPServer`，服务身份继续保持
`autocad-mcp`，服务版本来自 `t20_mcp.__version__`。默认协议是稳定版
`2026-07-28`，SDK 同时服务 `2025-11-25` 及更早客户端。

协议边界由 [`mcp_runtime.py`](../src/t20_mcp/mcp_runtime.py) 统一维护：

- `create_server()` 负责服务身份和服务器构造，协议版本字符串集中为常量。
- `ToolSpec` 是工具目录的声明单元；业务处理器、标题、工具名和只读提示不再散落在
  9 组服务器装饰器中。
- `wire_handler()` 保留业务处理器的输入签名，在返回类型上使用 SDK v2 原生
  `Annotated[CallToolResult, ToolEnvelope]`，因此工具列表自动发布 `outputSchema`。
- `to_call_tool_result()` 保留旧 JSON 文本和截图 content，同时把 JSON envelope
  映射到 `structuredContent`；`ok=false` 统一映射为 `isError=true`，但不升级为
  JSON-RPC 协议错误。

业务处理器只负责 operation 分派与后端调用，不应自行构造 SDK 会话对象、复制协议
版本或重复实现线路结果转换。`client.py` 中的 `_failure()` 和 `CommandResult`
仍是业务/后端 envelope；只有 `mcp_runtime.py` 负责把它们变成线路对象。

现代协议请求由 SDK 处理 `server/discover`、每请求协议/能力 `_meta`、必需的
`resultType` 和完整 JSON Schema 2020-12。项目没有 MCP Roots、Sampling、Logging、
Tasks、资源订阅或 Streamable HTTP 会话状态，因此本轮无需应用层迁移这些特性。
`backend.initialize()`、`FileIPCBackend._dispatch("ping", ...)` 只属于 AutoCAD
后端生命周期，不应与已经删除的 MCP `initialize` 握手和 MCP `ping` 方法混淆。

真实 stdio 协议门禁是 `scripts/itest_19_mcp_stdio_smoke.py`：客户端使用自动协商，
必须得到 `2026-07-28`，随后列出 9 个带 `outputSchema` 的工具，完成
`tangent.axis_lines` 结构化 dry-run，并验证未知子命令设置 `isError`。同一 smoke
再启动独立子进程，以 legacy 模式固定验证 `2025-11-25`、工具列表与结构化结果；
离线单元测试也覆盖这两条路径。

## 3. File IPC 调度链路

[`FileIPCBackend`](../src/t20_mcp/backends/file_ipc.py) 的一次正常请求按以下顺序执行：

1. 初始化阶段按进程映像名发现 AutoCAD 主窗口，再寻找其 `MDIClient` 子窗口作为
   不抢焦点的命令输入目标。
2. 每个请求在后端异步锁内串行执行。发送前若检测到阻塞主窗口的模态对话框，
   请求直接安全失败，不把 dispatcher 触发串送进对话框消息循环。
3. Python 生成 `request_id`，去掉参数中的 `None`，把命令原子写入
   `IPC_DIR/t20_mcp_cmd_<request_id>.json`：先写 `.tmp`，再在同目录 rename。
4. IPC 目录优先取 `AUTOCAD_MCP_IPC_DIR`；未设置时使用
   `%TEMP%/t20_mcp`。Python 与 LISP dispatcher 使用同一解析规则。
5. 命令 JSON 在 IPC 边界编码为 GBK，以适配中文 Windows 上 AutoLISP 的 ANSI
   读取行为；Python 源码、文档和普通配置仍统一使用 UTF-8。
6. Python 仅向 `MDIClient` 发送固定的 `(c:mcp-dispatch)` 和回车。正常请求不会先发
   ESC；只有上一请求超时、可能留下活动命令时，下一次首次触发才补两次 ESC。
7. dispatcher 读取命令、调用 `mcp-cmd-*` 路由，并写出
   `IPC_DIR/t20_mcp_result_<request_id>.json`。
8. Python 按配置的超时轮询结果，解码后校验 `request_id`，构造统一
   `CommandResult`。终态成功/失败会清理本次命令、结果和临时 LISP；超时属于
   “dispatcher 可能已读取命令但尚未加载代码”的不确定状态，因此临时 LISP 保留到
   stale cleanup。stale 阈值按全局最大允许超时再加缓冲计算，避免不同超时配置的
   两个进程互删仍活跃的请求文件。

结果文件由 AutoLISP 按系统 ANSI 代码页写出。解码顺序和兼容回退集中在
`_decode_result_bytes()`，调用方不应自行猜测编码。

## 4. 窗口发现与健康检查

`find_autocad_window()` 以进程映像名为主判据，默认是 `acad.exe`，可用
`AUTOCAD_MCP_ACAD_PROCESS` 覆盖。窗口标题中的 `autocad`、`天正`、`tarch`
只作回退或多实例消歧；若多个候选同时存在，优先标题含 `.dwg` 的窗口并记录告警。

初始化成功还要求 dispatcher ping 往返通过。仅发现窗口不代表 IPC 可用；
`mcp_dispatch.lsp not loaded`、ping timeout 或无法恢复的 `CMDACTIVE > 0` 都是停止条件。

## 5. tangent 执行模型

常规 tangent 子命令采用 LISP 模板与参数注入：

1. Python 完成类型、范围、文本和图层校验。
2. generator 渲染 `src/t20_mcp/lisp_templates/tangent/` 下的模板。
3. dry-run 只返回代码；`execute=True` 才进入后端。
4. 成功必须由实体增量、实体类型和关键属性读回证明，不能依赖 `vl-cmdf`
   返回值或“命令已退出”。

目前有两个经项目规则批准的 GUI 例外：

- `column`：LISP 只启动 `TGColumn`；Python 通过 TGColumn 面板的结构指纹定位控件，
  用受控 Win32 消息填参、向命令行输入插入点，并在结束后读回柱属性。
- `door/window`：LISP 只启动 `TOpening`；Python 以「门窗参数」标题和
  `ToolbarWindow32` 强结构指纹切换插门/插窗，再退出面板并执行正式 opening 模板。
  创建后的 DXF group71（门=0、窗=1）仍是最终门禁。

GUI 指纹不匹配时必须停止并回滚；严禁 `WM_CLOSE`，严禁无边界的键鼠自动化，
`CMDACTIVE > 0` 的面板阶段不得并发发起 File IPC。

## 6. 文档与证据边界

- 当前工具、子命令和参数语义：[`README.md`](../README.md) 与
  [`docs/T20_COMMANDS.md`](T20_COMMANDS.md)。
- 当前交付/延后裁定：[`TODO_BACKLOG.md`](../TODO_BACKLOG.md)。
- 当前收尾入口与验证命令：[`PROJECT_CLOSEOUT_TODO.md`](../PROJECT_CLOSEOUT_TODO.md)。
- 真机历史证据：`docs/handoff/`，其中 Handoff 40 是最近一次完整真机回归；
  Handoff 41 记录 MCP 协议层迁移，Handoff 42 记录其后的 MCP 运行时封装。

历史 E2E 可以说明某条路线曾在指定 AutoCAD/T20 环境通过，但不能代替本轮真机复验。
离线测试、compileall、Ruff 与 MCP stdio smoke 也不能被表述为新的 AutoCAD/T20 E2E。

## 7. 维护入口

| 关注点 | 权威实现 |
|---|---|
| MCP 协议边界、服务器工厂与线路结果 | `src/t20_mcp/mcp_runtime.py` |
| 9 个工具的业务目录与通用分派 | `src/t20_mcp/server.py` |
| 包版本 | `pyproject.toml` → `t20_mcp.__version__` |
| 后端选择与环境变量 | `src/t20_mcp/config.py` |
| File IPC、窗口发现和模态守卫 | `src/t20_mcp/backends/file_ipc.py` |
| LISP dispatcher | `lisp-code/mcp_dispatch.lsp` |
| tangent 子命令注册与生成 | `src/t20_mcp/tools/tangent.py` |
| 白名单 GUI 例外 | `src/t20_mcp/dialog_automation.py` |

修改上述契约时，应在同一变更中同步当前态文档和离线回归；历史 handoff 正文保持不变。
