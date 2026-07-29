# tangent 天正 T20 MCP — 当前交付裁定

> 最后校准：2026-07-26
>
> 本文件只记录仍有效的交付决定和重开条件。已完成过程与旧测试基线见
> `docs/handoff/`；不要把历史 handoff 的“下一步”重新加入当前计划。

## 状态约定

| 状态 | 含义 |
|---|---|
| DELIVERED | 已进入当前 33 子命令或当前基础设施，并有相应证据 |
| DEFERRED | 当前没有触发场景；满足明确条件后才重新设计 |
| BLOCKED | 目标仍有价值，但当前安全执行链受外部机制阻塞 |
| WON'T-SHIP | 已裁定不进入当前产品；不是“再试一轮”的待办 |

当前没有默认开启的命令扩展项。新工作必须先写明用户场景、相对现有能力的净增益、
安全回滚路径和验收证据。

## 1. 已交付基线

- 9 个 MCP 工具、33 个 `tangent` 子命令；当前名称见 `README.md` 和
  `src/t20_mcp/tools/tangent.py::SUBCOMMANDS`。
- `column` 面板自动化与五参数读回：Handoff 36。
- `drawing_name/arrow/elevation` 文本 COM 注入：Handoff 35。
- `TRectAxis` Gate B 机制与价值裁定：Handoff 37。
- 门窗 group71 回滚门禁：Handoff 38。
- 门窗面板自动切换与双向真机闭合：Handoff 39。

这些结论说明对应路线曾在记录环境通过，不等于本轮已经重新执行真机 E2E。

## 2. DEFERRED

### B3：window 占位与延迟替换

当前 `tangent.window` 已能自动切换窗模式并以 group71 验真，因此占位/替换不是
常规插窗链路的依赖。

仅在用户明确需要以下任一能力时重开：

- 不启动 T20 面板，先离线规划大量窗位；
- 墙体 MOVE/STRETCH 后仍通过持久 wall handle 延迟绑定；
- 最终阶段批量把可审计占位对象替换为真实 `TCH_OPENING`。

重开后必须重新设计 xdata schema、单条失败保留占位、整批 undo 和 cleanup；
不得直接恢复旧草案或先增加 `window_placeholder/window_replace` 名称再补行为。

### A2：通用 WPF 寄宿守卫

Handoff 34 已证明当前 TSaveAs「图形导出」是经典 Win32 `#32770`，不是 WPF
寄宿控件。现有场景没有实现通用 WPF 守卫的必要性。

只有捕获到真实 WPF 寄宿模态、现有 IsWindowEnabled/`#32770` 守卫无法安全诊断时
才重开；届时必须提供最小复现、窗口树证据和专项真机验收。

## 3. BLOCKED / WON'T-SHIP

| 对象 | 当前裁定 | 原因与替代 |
|---|---|---|
| `TRectAxis` / `rect_axis` | WON'T-SHIP | Gate B 可驱动，但产物只是普通 `LINE@DOTE`，无 xdata、TCH_AXIS 或轴号；使用 `axis_lines` + `layer="DOTE"` |
| `TPartSaveAs` | BLOCKED | selection-first 后强制弹「图形导出」Win32 模态框，`FILEDIA=0` 无法绕开；当前不提供静默 wrapper |
| `TSaveAs` / `TGetXML` / `export_t3` | WON'T-SHIP | 强模态导出链不符合无残留、可回滚的 MCP 执行边界 |
| `TSingleAxisDim` | WON'T-SHIP | `entsel` 风格不接受坐标注入；使用现有 `axis_lines` 或已交付尺寸工具 |
| `TLeader`、`TPointIndex`、`TSectIndex`、`TDimRad/Dia/Ang/Arc` | WON'T-SHIP | 依赖对象选择或内联编辑，现有安全输入链无法证明确定性完成 |
| 原生 `WIPEOUT` | WON'T-SHIP（范围裁定） | 真机已证明可生成，但它不是 T20 `TCH_*` 智能实体；不是“机制不可自动化” |
| `TBlkMask1` | WON'T-SHIP | 已测点序列 clean exit 但 0 实体，没有可验收产物 |
| `TGirDer`、`TSlab`、`TElevator`、复杂整体楼梯族 | WON'T-SHIP | 依赖既有对象、选择步骤或强面板，当前相对已交付替代能力没有足够净增益 |

`WON'T-SHIP` 表示当前产品决定，不是对未来所有自动化可能性的理论断言。只有出现
新的用户需求、不同产物类型或新的确定性输入机制，才可带新证据重新评审。

## 4. 新项目进入 backlog 的门槛

新候选至少要先回答：

1. 是否生成比现有工具更有价值的 T20 智能实体或稳定数据？
2. 输入是坐标、属性注入、白名单控件，还是不可控的对象选择/模态交互？
3. 成功如何通过实体类型、属性和数量增量证明？
4. 失败如何退出、回滚并恢复 `CMDACTIVE/CMDDIA/FILEDIA/OSMODE`？
5. 是否能先写窄探针，而不改 dispatcher、IPC 或广泛 UI 自动化？

连续两轮得到 0 实体、无法解释的实体增长、残留对话框或无法恢复的活动命令时停止，
记录 handoff，不继续猜输入序列。

## 5. 每次改动的验证门禁

```powershell
uv sync --locked
uv run ruff check src tests scripts
uv run ruff format --check src tests scripts
uv run pytest -q
uv run python -m compileall -q src scripts tests
uv run python scripts/itest_19_mcp_stdio_smoke.py
git diff --check
```

涉及 AutoCAD/T20 的变更再按 `PROJECT_CLOSEOUT_TODO.md` 执行窄到宽真机回归。
历史 `passed` 数字不在 backlog 固化；当前结果以本轮命令输出为准。

## 6. 历史证据路由

- Handoff 33：TPartSaveAs、TSingleAxisDim、opening COM 与 column inventory。
- Handoff 34：window DoorSill 与 TSaveAs 纯 Win32 模态证据。
- Handoff 35：文字 COM 注入。
- Handoff 36：column 控件级自动化。
- Handoff 37：TRectAxis 价值裁定。
- Handoff 38：opening group71 门禁与回滚。
- Handoff 39：opening 模式自动化闭合。

历史正文保持不变；当前状态发生变化时只更新本文件和当前态文档。
