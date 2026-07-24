# Handoff 39 — 门窗模式控件级自动化闭合

## 结论

Handoff 38 的人工“插门/插窗”切换已被控件级 UI 自动化取代。

`tangent.door` / `tangent.window` 当前链路：

1. 经 FileIPC 执行一个只启动 `TOpening` 的 LISP，等待 `CMDACTIVE=1` 和
   「门窗参数」面板出现。
2. 按强结构指纹定位底部标准 `ToolbarWindow32`。
3. 向工具栏客户区的插门或插窗按钮发送后台鼠标 down/up 消息，不移动真实鼠标。
4. 等模式消息落地后向命令行发送空回车，走 `TOpening` 提示中的默认
   `<退出>`，等待面板完全消失。
5. 再执行原有 `opening.lsp` 创建实体、COM 注入属性与图层。
6. 最终读取 DXF group71；`0=门`、`1=窗`。不匹配仍删除错误实体并返回结构化
   失败，因此 UI 点击结果不是成功依据。

## 控件指纹

2026-07-24，T20 天正建筑 V10.0 / AutoCAD 2024：

- 顶层面板：class `#32770`，标题精确为 `门窗参数`。
- 模式工具栏：唯一可见 `ToolbarWindow32`，control id `134`。
- 工具栏按钮数：`24`。
- 工具栏尺寸：`636 x 27` px。
- 布局：14 个 23px 插入方式按钮 + 2 个 8px separator +
  23px 插门 + 23px 插窗。
- 工具栏客户区点击点：
  - door：`(349, 12)`
  - window：`(372, 12)`

上述坐标相对工具栏客户区，不依赖面板屏幕位置。只有标题、class、control id、
按钮数和尺寸全部命中后才允许发送消息；任一不符即安全失败。

## 被证伪和修正的路线

- UI Automation 能读取 `插门` / `插窗` 的名称与 `IsSelected` 状态，但
  `SelectionItemPattern.Select()` 在真机会报 COM “找不到成员”。因此不把
  UIA Select 作为执行路径。
- 工具栏按钮不是独立 HWND，`BM_CLICK` 不适用。标准工具栏自身能消费
  `WM_LBUTTONDOWN` / `WM_LBUTTONUP`，后台消息真机生效。
- `ESC` 不是 `TOpening` 的正常收尾键。切模式后发 ESC 会让放置循环继续或重启，
  面板会重建并阻塞 dispatcher。命令提示明确为 `<退出>`，空回车才会稳定退出；
  这是本次探针中最关键的恢复语义。

## 实现

- `src/t20_mcp/dialog_automation.py`
  - `find_opening_panel`
  - `locate_opening_toolbar`
  - `click_opening_mode`
  - `drive_opening_mode`
- `src/t20_mcp/tools/tangent.py`
  - `_gen_opening_mode_launch`
  - `execute_opening`
  - `door/window` 正式执行路径接入自动模式准备
- `scripts/_opening_retry.py`
  - 保留兼容函数名，但不再等待终端人工输入，统一调用核心自动链
- `scripts/itest_42_opening_panel_mode_auto.py`
  - 一面临时墙上依次自动插窗、插门，逐项核对状态、group71、图层、实体增量、
    面板关闭和最终清理。

## 真机证据

命令：

```powershell
uv run python scripts/itest_42_opening_panel_mode_auto.py
```

结果：

| 顺序 | 请求 | 状态 | 实体证据 | 数量 |
|---|---|---|---|---|
| 1 | window | `T20MCP-OPENING-OK` | `TCH_OPENING`, `layer=WINDOW`, `group71=1` | `1 -> 2` |
| 2 | door | `T20MCP-OPENING-OK` | `TCH_OPENING`, `layer=DOOR_FIRE`, `group71=0` | `2 -> 3` |

两轮 `panel_closed=PASS`；临时墙和两个门窗最终全部 UNDO，实体数 `0 -> 0`。
这同时证明了窗→门的双向切换，不是只在初始面板状态恰好正确时通过。

离线与协议门禁：

- `uv run pytest -q`：`198 passed`
- `uv run python -m compileall -q src scripts tests`：PASS
- `git diff --check`：PASS（仅 Windows LF/CRLF 提示）
- `uv run python scripts/itest_19_mcp_stdio_smoke.py`：9 tools，PASS
- `uv run python scripts/itest_12_e2e.py`：核心 E2E 全 PASS，cleanup 实体数 `0`
- `uv run python scripts/itest_e2e_suite.py`：`25/25 passed`，cleanup PASS

## 安全边界

- 不发送 `WM_CLOSE`。
- `CMDACTIVE=1` 期间不走 IPC。
- 正常退出只发空回车；同一次切换最多重发一次。
- 工具栏指纹不匹配时不点击，正式创建不继续。
- 最终 group71 门禁和错误实体回滚继续保留。
- 非 FileIPC / 无 Win32 HWND 的测试 backend 保留原直接执行路径，便于离线测试。

## 对 backlog 的影响

- B3 `window_placeholder/window_replace` 继续保持 DEFERRED / OPTIONAL，但理由已改变：
  它不再是绕过人工面板切换的必要方案，只剩“离线占位、墙体变更后延迟绑定”
  这类独立工作流价值。
- 原 S-4“门窗模式不可自动化”结论被证伪。准确表述是：
  `COM/DXF 不能直接写模式，但 T20 V10 的面板控件级 UI 自动化可达`。
- A2 WPF 通用守卫和其它 S 级选择/强模态命令不受影响。
