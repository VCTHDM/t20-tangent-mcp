# T20 天正建筑常用命令编目

> 目的：为 `tangent` 工具的封装提供命令级清单与可驱动性评估。
>
> **命令名来源（2026-06-12 升级）**
> 命令名不再是推测：全部取自本机安装目录**官方命令表**
> `C:\Tangent\TArchT20V10\SYS\tchcmd.txt`（454 条「中文名 → 命令名」映射，
> UTF-8 副本见 `docs/t20_official_commands.txt`），并已在真机
> （T20 V10 / AutoCAD 2024）经 `getcname` 批量验证注册状态（442/451 命中），
> 全表见 **`docs/T20_OFFICIAL_COMMANDS.md`**。
> 本文档只保留「封装相关命令」的精编条目；**交互序列**仍需逐条真机验证，
> 验证记录见 `docs/handoff/05_fable_field_test.md`。

## 0. 关键前提与坑（真机证实）

1. **天正对话框 ≠ AutoCAD 原生对话框。** `CMDDIA=0`/`FILEDIA=0` 只对 AutoCAD
   原生命令生效，对天正自有对话框**无效**——已真机证实两例：
   - `TSaveAs`（图形导出）弹天正自绘导出框，无视 `FILEDIA=0`。
     2026-06-13 勘误（Handoff 09）：其顶层窗口类名实测为 `#32770`（WPF 内容
     寄宿其中），原探测盲因更可能是对话框不在主 UI 线程；现已新增
     「主窗口 IsWindowEnabled」信号（与类名/线程无关），itest_21 验收通过；
   - `TRectAxis`（绘制轴网）弹模态参数框（`#32770`）。
   **严禁对天正 ARX 对话框发送 `WM_CLOSE` 强关**——真机曾因此导致 AutoCAD
   致命错误崩溃。安全做法：向对话框发 ESC 键，或点击其"取消"按钮（BM_CLICK）。
2. **`vl-cmdf` 对无效输入是"假成功"**：命令吞掉无效关键字后正常返回（非 nil），
   不抛错也不建实体。因此模板一律以**实体增量 + 实体类型**为成功判据
   （见 wall/dimension/door/window 模板），不能信任 `vl-cmdf` 返回值。
3. **可驱动的天正命令模式（真机证实）**：命令行给点 → 用参数面板记忆值生成
   实体 → 实体为 `TCH_*` 自定义对象，**几何/尺寸参数可经 ActiveX 属性
   (`vlax-put-property`) 事后注入**。这是 wall/door 的落地路线，优先推广。
4. 本项目铁律：所有封装走 **LISP 模板 + 参数注入**，不硬编码键击序列。
5. 坐标单位默认 **毫米 (mm)**；角度单位默认 **度**。

## 1. 封装相关命令精编

列含义：
- **命令名**：官方命令表名称（已全部真机验证注册，不再推测）。
- **驱动方式**：真机验证出的可行驱动路径。
- **置信度**：高=真机端到端验证；中=部分验证；低=未行为验证；禁=对话框命令不可驱动。

### 1.1 已封装（tangent 子命令）

| 中文命令名 | 命令名 | 驱动方式（真机验证） | 生成实体 | 置信度 |
|---|---|---|---|---|
| 绘制墙体 | `TgWall` | 起点→终点→回车（面板记忆值）；左/右宽、高、材料经 COM 注入 `LeftWidth/RightWidth/Height/Style` | `TCH_WALL` | **高** (E2E) |
| 逐点标注 | `TDimMP` | 尺寸线位置点→点1→点2→回车（顺序错则 0 实体假成功） | `TCH_DIMENSION2` | **高** (E2E) |
| 墙厚标注 | `TDimWall` | 直线第一点→直线第二点；两点连线穿过墙体 | `TCH_DIMENSION2` | **高** (E2E) |
| 门窗标注 | `TDim3` | 线选起点→线选终点→回车；线选段穿过墙体/门窗 | `TCH_DIMENSION2` | **高** (E2E) |
| 标高标注 | `TMElev` | 标高基准点→标注放置点→回车；单点序列会挂起等待输入，严禁改成单点序列 | `TCH_ELEVATION` | **高** (E2E) |
| 门窗 | `TOpening` | 墙上插入点→回车（非模态面板不阻塞）；`Width/Height/DoorSill` 可 COM 注入 | `TCH_OPENING` | **中**：插入类型随面板当前模式（默认门）；窗模式/`SillHeight` 待验证 |
| 普通线轴网 | 原生 `LINE` | `axis_lines` 替代路径：按开间/进深生成普通线网格，可旋转；不生成天正智能轴网 | `LINE` | **中** (替代路径) |
| 绘制轴网(直线) | `TRectAxis` | **不可命令行驱动**：模态对话框 (#32770)。工具层已禁止 execute | — | **禁** (仅 dry-run) |
| 图形导出(T3) | `TSaveAs` | **不可静默**：天正自绘导出框 (WPF)，无视 FILEDIA=0。工具层已禁止 execute | — | **禁** (仅 dry-run) |

### 1.2 已验证存在、待封装评估

| 中文命令名 | 命令名 | 备注 |
|---|---|---|
| 分解对象 | `TExplode` | 注册已验证。**破坏性**：仅可在临时副本上执行（先 SAVEAS 副本→副本上分解→ezdxf 读取），禁止分解用户当前图纸 |
| 两点标注 | `TDimTP` | 两轮最小点序列均 0 实体（见 Handoff 06），暂不封装 |
| 墙厚标注 | `TDimWall` / 门窗标注 `TDim3` | 已封装为 `wall_thickness_dimension` / `opening_dimension` |
| 标高标注 | `TMElev` | 已封装为 `elevation`；双点序列 E2E 验证，单点序列禁用 |
| 局部导出 | `TPartSaveAs` | 空输入无弹框、无实体、无输出（no-op），仍未找到静默导出参数 |
| BIM导出 | `TGetXML` | 空输入弹 `#32770` “天正模型导出到TGL”，不可静默封装 |
| 标准柱 | `TGColumn` | 两轮点序列均 0 实体，暂不封装 |
| 单线变墙 | `TSWall` | 两轮选择 LINE 序列均未转换，仅保留原 LINE，暂不封装 |
| 搜索房间 | `TUpdSpace`(见全表) | 待验证 |

> 其余 ~440 条见 `docs/T20_OFFICIAL_COMMANDS.md`（含真机注册标记）。
> 未注册的 9 条集中在渲染/动画模块（延迟加载 ARX）与官方表笔误
> （如 `TOuterDimTOuterDim` 应为 `TOuterDim`）。

## 2. 当前 `tangent` 工具子命令状态

| 子命令 | 模板 | 命令 | 状态 |
|---|---|---|---|
| `wall` | `wall.lsp` | TgWall | **已验证** (E2E: 实体+COM 回读) |
| `dimension` | `dimension.lsp` | TDimMP | **已验证** (E2E) |
| `wall_thickness_dimension` | `wall_thickness_dimension.lsp` | TDimWall | **已验证** (E2E) |
| `opening_dimension` | `opening_dimension.lsp` | TDim3 | **已验证** (E2E) |
| `elevation` | `elevation.lsp` | TMElev | **已验证** (双点序列生成 TCH_ELEVATION；execute 附 warning) |
| `door` | `door.lsp` | TOpening | **部分验证** (execute 附 warning) |
| `window` | `window.lsp` | TOpening | **部分验证** (类型/窗台高未保证, execute 附 warning) |
| `axis_lines` | `axis_lines.lsp` | 原生 LINE | **替代路径** (普通线网格，可 execute) |
| `axis_grid` | `axis_grid.lsp` | TRectAxis | **仅 dry-run** (execute 已禁用) |
| `export_t3` | `export_t3.lsp` | TSaveAs | **仅 dry-run** (execute 已禁用) |

未覆盖（待后续迭代）：柱子、楼梯、房间、屋顶、符号/文字标注、门窗表等。

## 3. 后续待办

1. **窗模式驱动**：当前门模式下已验证 `Width/Height/DoorSill` 可写；
   `SillHeight/WindowSillHeight/OpType/Kind/Type/WinType` 均不可读/不可写
   （见 `scripts/itest_16_opening_props_safe.py`）。下一步需先把 TOpening 面板切到窗模式，
   再重跑属性探测。
2. **轴网/导出替代路径**：
   - 轴网：评估逐根画轴线（原生 LINE + 轴号 `TSingleAxisDim`）或 UI 自动化填对话框；
   - 导出：评估 `TPartSaveAs`、`TGetXML`，或 UI 自动化。
3. **TExplode + ezdxf 读取管线**（临时副本上，见 §1.2 批注）。
4. 新封装命令一律走已验证模式：官方表取名 → getcname 预检 → 最小点序列
   试驱动 → 实体增量校验 → COM 属性注参（`scripts/itest_*.py` 为现成管线）。
