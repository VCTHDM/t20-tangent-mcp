# T20 天正建筑命令编目

本文描述当前 `tangent` 接口、关键行为限制和未交付裁定。命令探索过程与旧结论保存在
[`docs/handoff/`](handoff/)；本文不重复按时间展开同一命令的多轮状态。

## 1. 命令来源与事实边界

T20 命令名来自本机官方命令表
`C:\Tangent\TArchT20V10\SYS\tchcmd.txt`。仓库保留了
[`t20_official_commands.txt`](t20_official_commands.txt) 的 454 行 UTF-8 副本，以及
[`T20_OFFICIAL_COMMANDS.md`](T20_OFFICIAL_COMMANDS.md) 的注册状态表。历史批量
`getcname` 结果为 442/451 个大小写无关命令名命中；未注册项可能来自延迟加载模块或
官方表拼写，不等于命令永久不存在。

不同层次的权威来源如下：

- 可执行子命令名：`src/t20_mcp/tools/tangent.py::SUBCOMMANDS`。
- 参数校验与实际生成/执行行为：`src/t20_mcp/tools/tangent.py` 与 LISP 模板。
- 面向使用者的快速参数表：[`README.md`](../README.md)。
- 当前交付与重开条件：[`TODO_BACKLOG.md`](../TODO_BACKLOG.md)。
- 真机证据：`docs/handoff/`，只证明记录当时的环境和代码。

`_GENERATORS` 是可执行子命令注册来源，但不是所有文档文字的“单一事实源”；修改接口时
必须同步 README、本文、工具 docstring 和一致性测试。

## 2. 当前安全前提

1. `CMDDIA=0`/`FILEDIA=0` 不能屏蔽天正自有对话框。TSaveAs「图形导出」经
   Handoff 34 复核为经典 Win32 `#32770` 真模态框，37 个子控件，WPF 子控件数为 0。
2. 严禁向天正 ARX 对话框发送 `WM_CLOSE`。安全退出只使用已验证的 ESC、空回车或
   白名单按钮路径。
3. `vl-cmdf` clean exit 可能是 0 实体假成功。验收必须检查实体增量、类型和关键属性。
4. 常规子命令走 LISP 模板与参数注入。`column`、`door/window` 是受控 GUI 例外：
   只允许强结构指纹、白名单 Win32 消息、读回验真和失败回滚。
5. 坐标单位默认毫米，角度单位默认度。`execute=False` 是 dry-run；只有
   `execute=True` 才进入 AutoCAD/T20 执行链路。

## 3. 当前 33 个 tangent 子命令

| 子命令 | 底层命令 | 主要产物 | 当前行为要点 |
|---|---|---|---|
| `axis_lines` | 原生 `LINE` | `LINE` | 普通线轴网，可旋转；不生成天正智能轴网 |
| `wall` | `TgWall` | `TCH_WALL` | 两点建墙，宽度、高度、材料经属性注入 |
| `door` | `TOpening` | `TCH_OPENING` | 自动切门模式；创建后硬校验 group71=0 |
| `window` | `TOpening` | `TCH_OPENING` | 自动切窗模式；窗台高写 `DoorSill`；硬校验 group71=1 |
| `dimension` | `TDimMP` | `TCH_DIMENSION2` | 逐点吸附标注，不用于严格总宽/总高 |
| `wall_thickness_dimension` | `TDimWall` | `TCH_DIMENSION2` | 穿墙线段生成墙厚标注 |
| `opening_dimension` | `TDim3` | `TCH_DIMENSION2` | 穿过墙/门窗的线段生成门窗标注 |
| `two_point_dimension` | `TDimTP` | `TCH_DIMENSION2` | 穿越多个独立对象后放置尺寸线 |
| `elevation` | `TMElev` | `TCH_ELEVATION` | 必须使用已验证双点序列；可经 COM 写 `Text` |
| `coordinate` | `TCoord` | `TCH_COORD` | 标注点与方向点 |
| `symmetry` | `TSymmetry` | `TCH_SYMMETRY` | 两点生成对称轴 |
| `line_pattern` | `TLinePattern` | `TCH_PATH_ARRAY` | 两点路径，样式取面板记忆值 |
| `north_arrow` | `TNorthThumb` | `TCH_NORTHTHUMB` | 位置点与方向点 |
| `break_line` | `TSymbCut` | `TCH_RUPTURE` | 两点后补默认回车收尾 |
| `section_symbol` | `TSection` | `TCH_SYMB_SECTION` | 两个剖切点与方向点 |
| `drawing_name` | `TDrawingName` | `TCH_DRAWINGNAME` | 可经 COM 写 `NameText/ScaleText` |
| `rectangle` | `TRect` | `TCH_RECT` | 两角点矩形 |
| `balcony` | `TBalcony` | `TCH_BALCONY` | 点列轮廓；类型和挑出宽取面板记忆值 |
| `step` | `TStep` | `TCH_STEP` | 点列轮廓；踏步参数取面板记忆值 |
| `ramp` | `TAscent` | `TCH_ASCENT` | 单点放置；宽度/坡长取面板记忆值 |
| `arrow` | `TArrow` | `TCH_ARROW` | 两点引线；可经 COM 写 `Text/Text2` |
| `column` | `TGColumn` | `TCH_COLUMN` | 受控面板自动化；五参数读回；图层由 T20 强制为 COLUMN |
| `rect_roof` | `TRectRoof` | `TCH_MOUNTROOF` | 三点矩形屋顶 |
| `cusp_roof` | `TCuspRoof` | `TCH_CUSPROOF` | 中心与半径/方向点 |
| `insight` | `TInsight` | `TCH_TDBINSIGHT` | 单点循环后退出 |
| `tree` | `TSingleTree` | `INSERT` | 插入普通树木图块，不是 `TCH_*` |
| `line_stair` | `TLStair` | `TCH_LINESTAIR` | 单点放置直线梯段 |
| `arc_stair` | `TAStair` | `TCH_ARCSTAIR` | 单点放置圆弧梯段 |
| `double_stair` | `TRStair` | `TCH_RECTSTAIR` | 单点放置双跑楼梯 |
| `multi_stair` | `TMultiStair` | `TCH_MULTISTAIR` | 起点与下一点，空回车收尾 |
| `wheelchair_diameter` | `TWheelchairDaim` | `TCH_RADIUSDIM` | 官方拼写为 `Daim`；缺省半径点在右侧 1500 mm |
| `explode_read` | 原生 `EXPLODE` | `LINE` 等 | COPY 副本、分解、序列化、UNDO；不修改原实体 |
| `search_room` | `TUpdSpace` | `TCH_SPACE` | 全图墙体围合生成房间对象 |

完整参数名与可选字段见 README 的 33 项表和 tangent 工具 docstring。执行时附带的 warning
表示调用限制或环境依赖，不等于“尚未验证”。

## 4. 门窗与柱的受控 GUI 例外

### door / window

当前链路先用独立 LISP 启动 `TOpening`，按「门窗参数」标题、唯一可见
`ToolbarWindow32`、control id、按钮数和尺寸定位模式工具栏，再发送后台鼠标消息选择
插门或插窗。空回车退出面板后，正式 opening 模板创建实体并注入属性。

按钮消息不是成功依据。创建后的 DXF group71 是最终权威；不匹配时删除错误实体并返回
`OPENING_MODE_MISMATCH`。当前闭合证据见
[`Handoff 39`](handoff/39_opening_mode_automation.md)，前一阶段回滚协议见
[`Handoff 38`](handoff/38_opening_mode_gate.md)。

### column

`column` 没有独立 `column.lsp` 模板。generator 只生成启动 `TGColumn` 的 LISP 片段，
正式执行由 Python 在 `CMDACTIVE=1` 期间驱动强结构指纹面板，填入高度、旋转、截面和
材料，向命令行输入插入点，退出后再通过 IPC 读回 `TCH_COLUMN` 属性。证据见
[`Handoff 36`](handoff/36_tgcolumn_gate_b_close.md)。

因此 33 个子命令当前对应 31 个命令模板加 `_prelude.lsp`：door/window 共用
`opening.lsp`，column 使用受控编排而非独立模板。

## 5. 未交付或不再交付

| 命令/方向 | 当前裁定 | 原因或替代 |
|---|---|---|
| `TRectAxis` | WON'T-SHIP | 可驱动但只产普通 `LINE@DOTE`，没有 TCH_AXIS/xdata/轴号；改用 `axis_lines` |
| `TPartSaveAs` | BLOCKED | selection-first 后强制弹经典 Win32「图形导出」模态框 |
| `TSaveAs` / `TGetXML` | WON'T-SHIP | 强模态导出链不满足静默、可回滚的 MCP 边界；不是 WPF 判定 |
| `TSingleAxisDim` | WON'T-SHIP | `entsel` 风格不接受坐标注入 |
| `TLeader`、`TPointIndex`、`TSectIndex` | WON'T-SHIP | 依赖选择或内联文字编辑 |
| `TDimRad/Dia/Ang/Arc` | WON'T-SHIP | 选择待标对象的步骤不能由现有安全坐标链确定驱动 |
| 原生 `WIPEOUT` | 范围外 | 真机可生成，但不是 T20 智能实体；不是“不可自动化” |
| `TExplode` | 已被替代 | `explode_read` 使用副本 + 原生 EXPLODE，不需要其模态框 |
| window 占位/延迟替换 | DEFERRED | 常规门窗自动切换已交付；仅在离线规划或跨墙变换场景重开 |
| 通用 WPF 寄宿守卫 | DEFERRED | 当前没有真实 WPF 模态触发场景 |

其它探测过但未交付的命令不属于隐含待办。重新评审条件和停止规则见
[`TODO_BACKLOG.md`](../TODO_BACKLOG.md)。

## 6. 验证与证据

离线接口一致性：

```powershell
uv run pytest -q
uv run python -m compileall -q src scripts tests
uv run python scripts/itest_19_mcp_stdio_smoke.py
```

真机管线：

```powershell
uv run python scripts/itest_01_bringup.py
uv run python scripts/itest_42_opening_panel_mode_auto.py
uv run python scripts/itest_12_e2e.py
uv run python scripts/itest_e2e_suite.py
```

离线门禁不能替代 AutoCAD/T20 真机证据；历史真机 PASS 也不能冒充本轮复验。
