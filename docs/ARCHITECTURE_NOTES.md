# T20 架构适配笔记与原理解析

## 1. File IPC 调度链路时序
目前的进程间通信机制完全通过临时文件和消息键盘注入来完成。
完整时序如下：
1. **Python 端发送请求**：生成唯一的 `request_id`，将指令及参数（去掉空值）打包成 JSON，原子写入 `C:/temp/autocad_mcp_cmd_{request_id}.json`（先写入 `.tmp` 后 rename）。
2. **命令触发**：Python 使用 `win32gui` 获取 AutoCAD 的 MDIClient 窗口句柄（Command Line），通过 `PostMessageW` 连续发送 2 次 ESC 取消当前命令，然后发送 `(c:mcp-dispatch)` 和回车。
3. **LISP 端处理**：`mcp_dispatch.lsp` 截获命令调用，按模式查找最新的临时 JSON 文件，使用简易 LISP 解析器解析 JSON，随后将请求路由到 `mcp-cmd-*` 对应函数。
4. **结果回传**：LISP 函数执行完后，将结果拼接成 JSON 字符串，原子写入 `C:/temp/autocad_mcp_result_{request_id}.json`（同样先 `.tmp` 后 rename）。
5. **Python 端接收**：Python 端在发出命令后，每隔 100ms 轮询一次结果文件，直到文件存在或达到 10s 超时时间。读取后核对 `request_id`。

## 2. 窗口查找逻辑
在 `src/t20_mcp/backends/file_ipc.py` 的 `find_autocad_window()` 中（行号：34-54），通过 `win32gui.EnumWindows` 遍历所有可见顶层窗口。判断逻辑为：
- `win32gui.IsWindowVisible(hwnd)` 为 True。
- 获取窗口标题转换为小写，匹配 `autocad` 且同时包含 `drawing` 或 `.dwg`。

在找到主句柄后，还需要遍历子窗口寻找类名为 `MDIClient` 的句柄（行号：196-214），这是命令行发送目标，可实现不抢占焦点（Focus-free）执行。

## 3. 所有与 "AutoCAD LT" 耦合的代码位置清单
目前上游代码中主要通过硬编码注释、异常提示语以及固定的类名与 AutoCAD LT 发生耦合。清单如下：

- **src/t20_mcp/backends/file_ipc.py**:
  - `Line 1`: `"""File-based IPC backend for AutoCAD LT.` (文件注释)
  - `Line 57`: `"""File-based IPC with AutoCAD LT via mcp_dispatch.lsp."""` (类注释)
  - `Line 86`: `"""Find AutoCAD window and verify dispatcher is loaded."""` (注释)
  - `Line 89`: `error="AutoCAD LT window not found"` (异常信息硬编码)
  - `Line 116`: `"AutoCAD LT detected but mcp_dispatch.lsp not loaded.\n"` (异常信息硬编码)
- **lisp-code/mcp_dispatch.lsp**:
  - `Line 10`: `;;; Compatible with AutoCAD LT 2024+.` (注释声明)

*(注：其他有关 DXF 提取等未对 LT 设硬限制，但在完整版与天正环境下有更丰富的命令可供替代。)*
