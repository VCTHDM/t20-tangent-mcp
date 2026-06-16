# tangent 天正 T20 MCP

T20 天正建筑 V10 MCP Server — 为 AutoCAD/T20 提供 AI 可调用的建筑实体封装。

基于 `autocad-mcp` 上游适配, 通过 **LISP 模板 + 参数注入** 将天正命令封装为 MCP 工具。
所有子命令在 Python 侧完成类型/范围校验, 生成已验证的 AutoLISP 代码, 经文件 IPC 下发。

## 快速上手

```bash
# 安装依赖
uv sync

# 离线测试 (无需 AutoCAD)
uv run pytest -q

# 启动 MCP stdio server
uv run -m t20_mcp

# 真机联调 (需 AutoCAD 2024 + T20 V10 运行中)
uv run python scripts/itest_01_bringup.py          # 引导: 窗口检测 + dispatcher 注入
uv run python scripts/itest_12_e2e.py              # 核心 E2E: wall/dimension/door + COM 回读
uv run python scripts/itest_e2e_suite.py           # 批量 E2E: 24 个子命令全部验证
uv run python scripts/itest_19_mcp_stdio_smoke.py  # MCP stdio 冒烟 (无需 AutoCAD)
```

## MCP 工具

共 9 个: drawing / entity / layer / block / annotation / pid / variable / screenshot / **tangent**。

### tangent 子命令 (28 个)

| 子命令 | 命令 | 实体 | 参数 |
|---|---|---|---|
| `wall` | TgWall | TCH_WALL | x1,y1,x2,y2, left_width?, right_width?, height?, wall_type?, layer? |
| `door` | TOpening | TCH_OPENING | ins_x,ins_y, width?, height?, sill_distance?, layer? |
| `window` | TOpening | TCH_OPENING | ins_x,ins_y, width?, height?, sill_height?, layer? |
| `dimension` | TDimMP | TCH_DIMENSION2 | p1_x,p1_y,p2_x,p2_y, pos_x?, pos_y?, layer? |
| `wall_thickness_dimension` | TDimWall | TCH_DIMENSION2 | p1_x,p1_y,p2_x,p2_y, layer? |
| `opening_dimension` | TDim3 | TCH_DIMENSION2 | p1_x,p1_y,p2_x,p2_y, layer? |
| `two_point_dimension` | TDimTP | TCH_DIMENSION2 | p1_x,p1_y,p2_x,p2_y, pos_x?, pos_y?, layer? |
| `elevation` | TMElev | TCH_ELEVATION | base_x,base_y, label_x?, label_y?, layer? |
| `coordinate` | TCoord | TCH_COORD | point_x,point_y, label_x?, label_y?, layer? |
| `symmetry` | TSymmetry | TCH_SYMMETRY | x1,y1,x2,y2, layer? |
| `line_pattern` | TLinePattern | TCH_PATH_ARRAY | x1,y1,x2,y2, layer? |
| `north_arrow` | TNorthThumb | TCH_NORTHTHUMB | pos_x,pos_y, dir_x?, dir_y?, layer? |
| `break_line` | TSymbCut | TCH_RUPTURE | x1,y1,x2,y2, layer? |
| `section_symbol` | TSection | TCH_SYMB_SECTION | x1,y1,x2,y2, dir_x?, dir_y?, layer? |
| `drawing_name` | TDrawingName | TCH_DRAWINGNAME | ins_x,ins_y, layer? |
| `rectangle` | TRect | TCH_RECT | x1,y1,x2,y2, layer? |
| `balcony` | TBalcony | TCH_BALCONY | points:[[x,y],...], layer? |
| `step` | TStep | TCH_STEP | points:[[x,y],...], layer? |
| `ramp` | TAscent | TCH_ASCENT | x,y, layer? |
| `arrow` | TArrow | TCH_ARROW | x1,y1,x2,y2, layer? |
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

验证状态: 全部 32 个子命令均已 E2E 验证 (T20 V10 / AutoCAD 2024)。
`door`/`window`/`elevation`/`drawing_name`/`arrow` 执行时附 warning 提示。
`window` 调用前需人工切天正门窗面板到窗模式。
详细记录见 [`docs/T20_COMMANDS.md`](docs/T20_COMMANDS.md)。

## 项目结构

```
src/t20_mcp/tools/tangent.py         # 核心: 子命令 generator + MCP 工具注册
src/t20_mcp/lisp_templates/tangent/  # LISP 模板 (30 个 .lsp)
src/t20_mcp/backends/file_ipc.py     # 文件 IPC (编码链/窗口检测/弹框守卫)
tests/test_tangent_lisp_gen.py       # 离线测试 (LISP 生成 + 参数校验)
scripts/                             # 真机联调管线
docs/                                # 命令编目 + handoff 审计记录
```

## Handoff 索引

工程决策审计记录, 按顺序:
`docs/handoff/01..31_*.md`

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
- 29/30 — P2/P3 后续路线图

## 测试

```bash
uv run pytest -q                              # 离线 (29 个测试, <1s)
uv run python scripts/itest_01_bringup.py     # 真机引导 (需 AutoCAD)
uv run python scripts/itest_12_e2e.py         # 真机核心 E2E
uv run python scripts/itest_e2e_suite.py      # 真机批量 E2E (24 case)
```

## 许可

本项目基于上游 `autocad-mcp` 修改适配, 同样遵循其许可证。
