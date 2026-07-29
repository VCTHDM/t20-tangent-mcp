# tangent 天正 T20 MCP

![CI](https://github.com/VCTHDM/t20-tangent-mcp/actions/workflows/ci.yml/badge.svg)
![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)

T20 天正建筑 V10 MCP Server — 为 AutoCAD/T20 提供 AI 可调用的建筑实体封装。

基于 `autocad-mcp` 上游适配。常规子命令通过 **LISP 模板 + 参数注入** 封装，
所有参数先在 Python 侧校验；`column` 与 `door/window` 使用强结构指纹约束的
受控 Win32 编排，最终仍以实体读回结果验真。

## MCP 协议兼容性

当前包版本为 `3.2.0`，依赖官方 Python SDK `mcp>=2.0.0,<3`。服务器默认支持稳定版
MCP `2026-07-28`：协议层不再使用 `initialize/notifications/initialized` 会话握手，
由 `server/discover` 和每请求 `_meta` 完成版本与能力协商；同时保留对
`2025-11-25` 旧客户端的兼容服务。

`scripts/itest_19_mcp_stdio_smoke.py` 会通过真实 stdio 子进程自动协商，并硬断言
协议版本为 `2026-07-28`、普通结果含 `resultType="complete"`、9 个工具均可列出；
随后用独立 stdio 子进程固定验证 legacy `2025-11-25`。
项目代码中的 `backend.initialize()` 与 dispatcher `ping` 是 AutoCAD/File IPC
健康检查，不是本次规范删除的 MCP 握手或 MCP `ping` 方法。

迁移依据：

- [MCP 2026-07-28 官方变更清单](https://modelcontextprotocol.io/specification/2026-07-28/changelog)
- [MCP Python SDK v2.0.0 发布说明](https://github.com/modelcontextprotocol/python-sdk/releases/tag/v2.0.0)
- [MCP Python SDK v2 迁移指南](https://py.sdk.modelcontextprotocol.io/migration/)

## 快速上手

```bash
# 安装依赖
uv sync --locked

# 离线测试 (无需 AutoCAD)
uv run pytest -q

# 启动 MCP stdio server
uv run -m t20_mcp

# 真机联调 (需 AutoCAD 2024 + T20 V10 运行中)
uv run python scripts/itest_01_bringup.py          # 引导: 窗口检测 + dispatcher 注入
uv run python scripts/itest_dim_precision_verify.py # 尺寸/坐标精度专项
uv run python scripts/itest_42_opening_panel_mode_auto.py # 门/窗双向模式门禁
uv run python scripts/itest_12_e2e.py              # 核心 E2E: wall/dimension/door + COM 回读
uv run python scripts/itest_e2e_suite.py           # 批量 E2E: 27 case
uv run python scripts/itest_39_column_gate_b_e2e.py # column 五参数专项
uv run python scripts/itest_25_explode_read_e2e.py  # explode_read 回滚专项
uv run python scripts/itest_19_mcp_stdio_smoke.py  # MCP stdio 冒烟 (无需 AutoCAD)
```

## MCP 工具

共 9 个: drawing / entity / layer / block / annotation / pid / view / system / **tangent**。

### tangent 子命令 (33 个)

| 子命令 | 命令 | 实体 | 参数 |
|---|---|---|---|
| `wall` | TgWall | TCH_WALL | x1,y1,x2,y2, left_width?, right_width?, height?, wall_type?, layer? |
| `door` | TOpening | TCH_OPENING | ins_x,ins_y, width?, height?, sill_distance?, layer? |
| `window` | TOpening | TCH_OPENING | ins_x,ins_y, width?, height?, sill_height?, layer? |
| `dimension` | TDimMP | TCH_DIMENSION2 | p1_x,p1_y,p2_x,p2_y, pos_x?, pos_y?, layer?；逐点吸附，不用于总宽/总高（总尺寸用 `annotation.create_dimension_linear`） |
| `wall_thickness_dimension` | TDimWall | TCH_DIMENSION2 | p1_x,p1_y,p2_x,p2_y, layer? |
| `opening_dimension` | TDim3 | TCH_DIMENSION2 | p1_x,p1_y,p2_x,p2_y, layer? |
| `two_point_dimension` | TDimTP | TCH_DIMENSION2 | p1_x,p1_y,p2_x,p2_y, pos_x?, pos_y?, layer? |
| `elevation` | TMElev | TCH_ELEVATION | base_x,base_y, label_x?, label_y?, text?, layer? |
| `coordinate` | TCoord | TCH_COORD | point_x,point_y, label_x?, label_y?, layer? |
| `symmetry` | TSymmetry | TCH_SYMMETRY | x1,y1,x2,y2, layer? |
| `line_pattern` | TLinePattern | TCH_PATH_ARRAY | x1,y1,x2,y2, layer? |
| `north_arrow` | TNorthThumb | TCH_NORTHTHUMB | pos_x,pos_y, dir_x?, dir_y?, layer? |
| `break_line` | TSymbCut | TCH_RUPTURE | x1,y1,x2,y2, layer? |
| `section_symbol` | TSection | TCH_SYMB_SECTION | x1,y1,x2,y2, dir_x?, dir_y?, layer? |
| `drawing_name` | TDrawingName | TCH_DRAWINGNAME | ins_x,ins_y, name_text?, scale_text?, layer? |
| `rectangle` | TRect | TCH_RECT | x1,y1,x2,y2, layer? |
| `balcony` | TBalcony | TCH_BALCONY | points:[[x,y],...], layer? |
| `step` | TStep | TCH_STEP | points:[[x,y],...], layer? |
| `ramp` | TAscent | TCH_ASCENT | x,y, layer? |
| `arrow` | TArrow | TCH_ARROW | x1,y1,x2,y2, text?, text2?, layer? |
| `column` | TGColumn | TCH_COLUMN | x,y, height?, material?, rotation?, sec_w?, sec_h? (面板 UI 自动化, 图层强制 COLUMN) |
| `rect_roof` | TRectRoof | TCH_MOUNTROOF | x1,y1,x2,y2,x3,y3, layer? |
| `cusp_roof` | TCuspRoof | TCH_CUSPROOF | center_x,center_y, base_x?, base_y?, layer? |
| `insight` | TInsight | TCH_TDBINSIGHT | x,y, layer? |
| `tree` | TSingleTree | INSERT | x,y, layer? |
| `line_stair` | TLStair | TCH_LINESTAIR | x,y, layer? |
| `arc_stair` | TAStair | TCH_ARCSTAIR | x,y, layer? |
| `double_stair` | TRStair | TCH_RECTSTAIR | x,y, layer? |
| `multi_stair` | TMultiStair | TCH_MULTISTAIR | x1,y1,x2,y2, layer? |
| `wheelchair_diameter` | TWheelchairDaim | TCH_RADIUSDIM | center_x,center_y, edge_x?, edge_y?, layer? |
| `axis_lines` | LINE | LINE | base_x?,base_y?, hspacings:[..], vspacings:[..], angle?, layer? |
| `explode_read` | EXPLODE | — | handle, offset_x?, offset_y?, max_entities? |
| `search_room` | TUpdSpace | TCH_SPACE | layer? |

历史验证状态：全部 33 个子命令均有 T20 V10 / AutoCAD 2024 E2E 证据。
2026-07-26 的仓库收敛补丁又完成了一轮 fresh 33/33 真机覆盖；具体脚本映射、断言
强度和恢复记录见 [Handoff 40](docs/handoff/40_repository_audit_fresh_e2e.md)。
这表示每个子命令至少通过当前生产路径与对应门禁，不表示穷举所有可选参数组合。
`dimension`/`door`/`window`/`elevation`/`drawing_name`/`arrow`/`column` 执行时附 warning 提示。
`door`/`window` 会先自动驱动「门窗参数」面板切换插门/插窗模式，再创建并校验
DXF group71 (0=门, 1=窗)。group71 仍是最终门禁；模式不符时错误实体自动删除，
不会把错误类型伪装成成功。
详细记录见 [`docs/T20_COMMANDS.md`](docs/T20_COMMANDS.md)。

## 项目结构

```
src/t20_mcp/tools/tangent.py         # 核心: 子命令 generator + MCP 工具注册
src/t20_mcp/lisp_templates/tangent/  # LISP 模板 (31 个 .lsp + _prelude)
lisp-code/mcp_dispatch.lsp           # File IPC dispatcher (构建时作为包数据纳入 wheel)
src/t20_mcp/backends/file_ipc.py     # 文件 IPC (编码链/窗口检测/弹框守卫)
tests/test_tangent_lisp_gen.py       # 离线测试 (LISP 生成 + 参数校验)
scripts/                             # 真机联调管线
docs/                                # 命令编目 + handoff 审计记录
```

## Handoff 索引

当前入口是 [`PROJECT_CLOSEOUT_TODO.md`](PROJECT_CLOSEOUT_TODO.md) 与
[`TODO_BACKLOG.md`](TODO_BACKLOG.md)。`docs/handoff/` 保存按时间追加的真机证据，
编号目前到 41；编号 14 的空缺以及 34/36/37 的同号多文件都按历史原样保留，
不要把编号范围简写当成可执行的文件模式，也不要把旧 handoff 当成当前行为说明。

关键节点:

- 03 — 架构评审 (P0-P2)
- 05 — 首次真机验证
- 09 — 弹框守卫 (WPF 盲区修复)
- 10 — explode_read 管线
- 13 — TGColumn #32770 定论
- 17 — TCoord 封装
- 25 — 楼梯梯段封装
- 27 — 双跑/多跑楼梯 + 简单候选耗尽
- 28 — line_pattern / wheelchair_diameter 收尾
- 29/30 — P2/P3 后续路线图 (脚本引用已被 32 修订, 见下)
- 32 — slimming 后当前可用资产清单 + 已删脚本提示 (取代 29/30/31 中已失效的 itest_44/45/46 脚本路径)
- 33 — P1/P2/P3 真机推进: TPartSaveAs BLOCKED (selection-first 后弹「图形导出」#32770) / TSingleAxisDim STOP (entsel/实体拾取, 不接受坐标注入) / door COM 读回 PASS / window 模式下 sill_height 已通过 DoorSill 写入验证 (TCH_OPENING 不暴露独立 SillHeight；当时要求预切窗模式，先被 Handoff 38 的 mismatch 回滚保护、再由 Handoff 39 自动切换取代) / column Gate A inventory (556 子控件)
- 34 — D1 闭合: window 模式 SillHeight 真机 sweep (DS=600/1200/300) 与 group71=1 精确匹配; tangent.window 参数语义闭合, sill_height 走 DoorSill 字段语义经第二轮真机确认
- 35 — B2 闭合: drawing_name/arrow/elevation 文本 COM 注入证实可行 (NameText/ScaleText, Text/Text2, Text 真机写入+读回精确匹配), 三子命令文本参数上线; S-4 收窄为仅门/窗模式切换
- 36 — B1 闭合: TGColumn 面板 UI 自动化突破 (项目首例), `column` 子命令上线; WM_SETTEXT+通知补发 填参 + 命令行 WM_CHAR 打插入点, 五参数 COM 读回精确匹配; "面板命令不可脚本驱动"结论修正为"点序列不可达, 控件级可达"
- 37 — A1 裁定: TRectAxis Gate B 机制打通 (WM_COMMAND IDOK 关框 + 打点, COUNT*SPACING 语法) 但**不封装** — 产物纯 LINE@DOTE 无 xdata/TCH_AXIS/轴号, 与 axis_lines 同类零增益; 沉淀"封装前先验产物实体类型"方法论 (机制可行 ≠ 值得封装)
- [38](docs/handoff/38_opening_mode_gate.md) — 门窗两阶段模式门禁与错误实体回滚（历史人工切换阶段）
- [39](docs/handoff/39_opening_mode_automation.md) — 当前门窗自动切换链路；group71 最终门禁继续保留
- [40](docs/handoff/40_repository_audit_fresh_e2e.md) — 仓库收敛、测试门禁加固与 fresh 33/33 真机回归
- [41](docs/handoff/41_mcp_2026_07_28_protocol.md) — MCP 2026-07-28 / Python SDK v2 协议迁移与双版本兼容验证

## 测试

```bash
uv run ruff check src tests scripts
uv run ruff format --check src tests scripts
uv run pytest -q                              # 完整离线测试
uv run python scripts/itest_01_bringup.py     # 真机引导 (需 AutoCAD)
uv run python scripts/itest_42_opening_panel_mode_auto.py  # 门窗自动切换双向门禁
uv run python scripts/itest_12_e2e.py         # 真机核心 E2E
uv run python scripts/itest_e2e_suite.py      # 真机批量 E2E (27 case)
uv run python scripts/itest_39_column_gate_b_e2e.py  # column 参数读回
uv run python scripts/itest_25_explode_read_e2e.py   # explode_read 回滚
```

## 许可

MIT License — 见 [`LICENSE`](LICENSE)。

本项目基于上游 [`puran-water/autocad-mcp`](https://github.com/puran-water/autocad-mcp)
(MIT, Copyright 2024 AutoCAD MCP Server Contributors) 修改适配, 保留其版权声明并
以同一 MIT 许可证发布。
