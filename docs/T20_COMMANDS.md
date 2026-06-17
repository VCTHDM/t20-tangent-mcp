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
> 验证记录见 `docs/handoff/05_field_test.md`。

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
| 两点标注 | `TDimTP` | 穿越线起点→穿越线终点→标注位置→回车；三墙场景 E2E 生成尺寸，穿过对象不足会报"对象数目太少" | `TCH_DIMENSION2` | **高** (E2E) |
| 标高标注 | `TMElev` | 标高基准点→标注放置点→回车；单点序列会挂起等待输入，严禁改成单点序列 | `TCH_ELEVATION` | **高** (E2E) |
| 坐标标注 | `TCoord` | 标注点→坐标标注方向点→回车 | `TCH_COORD` | **高** (E2E) |
| 画对称轴 | `TSymmetry` | 起点→终点；两点即收尾 (active=0) | `TCH_SYMMETRY` | **高** (E2E) |
| 线图案 | `TLinePattern` | 起点→终点→回车→回车（补第二个空回车退出循环）；样式走面板记忆值 | `TCH_PATH_ARRAY` | **高** (E2E) |
| 画指北针 | `TNorthThumb` | 指北针位置点→方向点；两点即收尾 (active=0) | `TCH_NORTHTHUMB` | **高** (E2E) |
| 加折断线 | `TSymbCut` | 起点→终点→回车 (接受 `<不切割>` 默认)；两点后命令仍 active, 必须补空回车 | `TCH_RUPTURE` | **高** (E2E) |
| 剖切符号 | `TSection` | 第一剖切点→第二剖切点→剖视方向→回车退出循环；编号文字走面板记忆值 | `TCH_SYMB_SECTION` | **高** (E2E) |
| 图名标注 | `TDrawingName` | 插入位置→回车退出循环；图名文字/比例走面板记忆值 (不可参数化, 附 warning) | `TCH_DRAWINGNAME` | **高** (E2E) |
| 矩形 | `TRect` | 第一角点→第二角点→回车退出循环 | `TCH_RECT` | **高** (E2E) |
| 阳台 | `TBalcony` | 各轮廓点→回车；类型/挑出宽走面板记忆值；点数≥2 | `TCH_BALCONY` | **高** (E2E) |
| 台阶 | `TStep` | 各轮廓点→回车；踏步数/宽走面板记忆值；点数≥2 | `TCH_STEP` | **高** (E2E) |
| 坡道 | `TAscent` | 点取位置→回车退出循环；宽度/坡长走面板记忆值 | `TCH_ASCENT` | **高** (E2E) |
| 箭头引注 | `TArrow` | 起点→终点→回车→回车（先结束引线循环再退外层循环）；引注文字走面板记忆值 (附 warning) | `TCH_ARROW` | **高** (E2E) |
| 矩形屋顶 | `TRectRoof` | 左下角点→右下角点→右上角点→回车退出循环；坡角/出檐走面板记忆值 | `TCH_MOUNTROOF` | **高** (E2E) |
| 攒尖屋顶 | `TCuspRoof` | 屋顶中心位置→第二点(定半径/朝向)；两点即收尾 (active=0)；边数/屋顶高走面板记忆值 | `TCH_CUSPROOF` | **高** (E2E) |
| 内视符号 | `TInsight` | 标注位置点→回车退出循环 (每点一个)；朝向/编号走面板记忆值 | `TCH_TDBINSIGHT` | **高** (E2E) |
| 任意布树 | `TSingleTree` | 插入点→回车退出循环 (每点一棵)；树种/尺寸走面板记忆值；实体为通用 INSERT 图块 | `INSERT` | **高** (E2E) |
| 直线梯段 | `TLStair` | 点取位置→回车退出循环；梯段宽/踏步数/踏步高走面板记忆值 | `TCH_LINESTAIR` | **高** (E2E) |
| 圆弧梯段 | `TAStair` | 点取位置→回车退出循环；内外半径/踏步数/圆心角走面板记忆值 | `TCH_ARCSTAIR` | **高** (E2E) |
| 双跑楼梯 | `TRStair` | 插入点→回车退出循环；梯段宽/踏步数/楼梯高/井宽走面板记忆值 | `TCH_RECTSTAIR` | **高** (E2E) |
| 多跑楼梯 | `TMultiStair` | 起点→下一点→回车（在"起点<退出>"处空回车收尾）；跑数/梯段宽/楼梯高走面板记忆值 | `TCH_MULTISTAIR` | **高** (E2E) |
| 轮椅直径 | `TWheelchairDaim` | 中心点→半径/方向点→回车；edge 缺省为中心正右 1500mm；官方命令拼写为 `Daim` | `TCH_RADIUSDIM` | **高** (E2E) |
| 门窗 | `TOpening` | 墙上插入点→回车（非模态面板不阻塞）；`Width/Height/DoorSill` 可 COM 注入；`window` 调用前需人工把门窗面板切到窗模式 | `TCH_OPENING` | **中**：插入类型随面板当前模式（默认门） |
| 普通线轴网 | 原生 `LINE` | `axis_lines` 替代路径：按开间/进深生成普通线网格，可旋转；不生成天正智能轴网 | `LINE` | **中** (替代路径) |
| 几何读回 | 原生 `EXPLODE` | `explode_read`：COPY 副本到暂存区→分解副本→序列化产物→UNDO 回滚，非破坏。已知 T20 缺陷：墙体产物起点侧顶点归零 | `LINE` 等 | **高** (E2E) |
| 搜索房间 | `TUpdSpace` | `search_room`：全图选择 `TCH_WALL` → 选择集 → 回车；闭合墙体围合区域生成房间对象 | `TCH_SPACE` | **高** (E2E) |

### 1.2 已验证存在、待封装评估

| 中文命令名 | 命令名 | 备注 |
|---|---|---|
| 分解对象 | `TExplode` | **已被 `explode_read` 取代**（实体副本 + 原生 `EXPLODE`，不弹框）。TExplode 必弹「分解对象」#32770 框（itest_23），白名单按钮驱动已验证可行（itest_24）但不再需要 |
| 两点标注 | `TDimTP` | **已封装为 `two_point_dimension`**。Handoff 13 改用三墙穿越线场景后 E2E 验证通过 |
| 墙厚标注 | `TDimWall` / 门窗标注 `TDim3` | 已封装为 `wall_thickness_dimension` / `opening_dimension` |
| 标高标注 | `TMElev` | 已封装为 `elevation`；双点序列 E2E 验证，单点序列禁用 |
| 坐标标注 | `TCoord` | **已封装为 `coordinate`**（Handoff 17，E2E 验证） |
| 平行标注 | `TParallelDim` | 已探测：提示为起点→终点；无足够平行对象时报“与第一个对象平行的对象太少”；三墙穿越线场景未生成新实体，暂不封装（Handoff 18） |
| 箭头引注 | `TArrow` | 已探测：起点→下一点可生成 `TCH_ARROW`，但回车后命令仍 active，完成/退出语义未确认，暂不封装（Handoff 18） |
| 画对称轴 | `TSymmetry` | **已封装为 `symmetry`**（Handoff 19，E2E 生成 `TCH_SYMMETRY`） |
| 画指北针 | `TNorthThumb` | **已封装为 `north_arrow`**（Handoff 19，E2E 生成 `TCH_NORTHTHUMB`） |
| 加折断线 | `TSymbCut` | **已封装为 `break_line`**（Handoff 19，E2E 生成 `TCH_RUPTURE`） |
| 剖切符号 | `TSection` | **已封装为 `section_symbol`**（Handoff 20，E2E 生成 `TCH_SYMB_SECTION`） |
| 图名标注 | `TDrawingName` | **已封装为 `drawing_name`**（Handoff 20，E2E 生成 `TCH_DRAWINGNAME`；图名文字取面板记忆值） |
| 矩形 | `TRect` | **已封装为 `rectangle`**（Handoff 21，E2E 生成 `TCH_RECT`） |
| 阳台 | `TBalcony` | **已封装为 `balcony`**（Handoff 21，E2E 生成 `TCH_BALCONY`；轮廓点列驱动） |
| 台阶 | `TStep` | **已封装为 `step`**（Handoff 21，E2E 生成 `TCH_STEP`；轮廓点列驱动） |
| 坡道 | `TAscent` | **已封装为 `ramp`**（Handoff 22，E2E 生成 `TCH_ASCENT`；点取位置→回车，宽度/坡长取面板记忆值） |
| 箭头引注 | `TArrow` | **已封装为 `arrow`**（Handoff 22，E2E 生成 `TCH_ARROW`；起点→终点→回车→回车，引注文字取面板记忆值）。补完 Handoff 18 未确认的退出语义：两点引线后需补**两个**空回车（先结束本引线"直段下一点<结束>"循环，再退"箭头起点<退出>"外层循环） |
| 平板 | `TSlab` | 已探测：提示"选择一封闭的多段线或圆"；选对象步不吃脚本点(ssget"_L"/ename/拾取点均不消费，命令滞留或默认退出，0 平板)，同标注族选择步坑，暂不封装（Handoff 22） |
| 地下坡道 | `TUndergroundRamp` | 已探测：坡道起点→下一点→回车可生成几何，但产物是裸 `LWPOLYLINE`(非干净 TCH_ 实体，一次出 3 个杂实体)，难以断言，暂不封装（Handoff 22） |
| 矩形屋顶 | `TRectRoof` | **已封装为 `rect_roof`**（Handoff 23，E2E 生成 `TCH_MOUNTROOF`；左下→右下→右上→回车） |
| 攒尖屋顶 | `TCuspRoof` | **已封装为 `cusp_roof`**（Handoff 23，E2E 生成 `TCH_CUSPROOF`；中心→半径点两点收尾） |
| 单轴绘制 | `TSingleAxis` | 已探测：起点→终点→回车可成，但产物是裸 `LINE`(非天正智能轴线)，不比 `axis_lines` 强，暂不封装（Handoff 23） |
| 引出标注 | `TLeader` | 已探测：第一点→引线位置→文字基线位置；文字基线给空回车则放弃(0 实体)，正常完成需内联文字编辑(挂死风险)，暂不封装（Handoff 23） |
| 墙体造型 | `TAddPatch` | 已探测：外凸/内凹→轮廓点列→结束；无依附墙体时 0 实体(造型需附墙)，前置重，暂不封装（Handoff 23） |
| 内视符号 | `TInsight` | **已封装为 `insight`**（Handoff 24，E2E 生成 `TCH_TDBINSIGHT`；单点循环补回车退出） |
| 任意布树 | `TSingleTree` | **已封装为 `tree`**（Handoff 24，E2E 插入 INSERT 树木图块 `tree1`；单点循环补回车退出） |
| 指向索引/剖切索引 | `TPointIndex`/`TSectIndex` | 已探测：索引节点位置→参考点；需编号文字，空回车则 0 实体，暂不封装（Handoff 24） |
| 直线梯段 | `TLStair` | **已封装为 `line_stair`**（Handoff 25，E2E 生成 `TCH_LINESTAIR`；单点循环补回车退出） |
| 圆弧梯段 | `TAStair` | **已封装为 `arc_stair`**（Handoff 25，E2E 生成 `TCH_ARCSTAIR`；单点循环补回车退出） |
| 双跑楼梯 | `TRStair` | **已封装为 `double_stair`**（Handoff 27，E2E 生成 `TCH_RECTSTAIR`；插入点→回车，单点循环补回车退出） |
| 多跑楼梯 | `TMultiStair` | **已封装为 `multi_stair`**（Handoff 27，E2E 生成 `TCH_MULTISTAIR`；起点→下一点→回车，在"起点<退出>"处空回车收尾） |
| 线图案 | `TLinePattern` | **已封装为 `line_pattern`**（Handoff 28，E2E 生成 `TCH_PATH_ARRAY`；起点→终点→回车→回车） |
| 轮椅直径 | `TWheelchairDaim` | **已封装为 `wheelchair_diameter`**（Handoff 28，E2E 生成 `TCH_RADIUSDIM`；中心点→半径/方向点→回车） |
| 矩形屏蔽 | `TBlkMask1` | 已探测：两角点序列 clean exit 但 0 实体，暂不封装（Handoff 28） |
| 任意屏蔽 | `WIPEOUT` | 已探测：四点+C 可生成原生 `WIPEOUT`，但不是天正 `TCH_*` 智能实体，暂不纳入 `tangent` 智能实体封装（Handoff 28） |
| 双分/转角/三跑/交叉/剪刀/三角楼梯·自动扶梯 | `TDrawParallelStair`/`TDrawCornerStair`/`TDrawDoubleMulStair`/`TDrawScissorsStair`/`TDrawCrossStair`/`TDrawTriangleStair`/`tdrawautostair` | 已探测：均**先弹 #32770 模态参数面板**（如"双分平行楼梯"框）再取点，命令行点序列到不了放置处理器，同 column/axis_grid 墙2 死路，暂不封装（Handoff 27） |
| 绘制梁 | `TGirDer` | 已探测：两点序列命令行无弹框但 0 实体（梁需依附墙/柱/轴线，前置重），暂不封装（Handoff 27） |
| 风玫瑰 | `TWINDROSE` | 已探测：**弹"风玫瑰"模态框**（地区/参数面板），墙2 死路，暂不封装（Handoff 27） |
| 电梯 | `TElevator` | 已探测：电梯间角点→对角点→**点取开电梯门的墙线**(选墙线步，需前置墙，空回车则 0 实体)，暂不封装（Handoff 25） |
| 半径/直径/角度/弧弦标注 | `TDimRad`/`TDimDia`/`TDimAng`/`TDimArc` | 已探测：均命令行无弹框，但**选择待标注对象的拾取步不吃脚本点/ename**（报"点无效"，命令滞留 active），vl-cmdf 点序列打不通，暂不封装（Handoff 21） |
| 局部导出 | `TPartSaveAs` | **Handoff 33 已 BLOCKED**: LOGFILEMODE 抓取确认提示流为 selection-first (`请选择要导出的对象<退出>:`); 选择集到位后必弹 `#32770` "图形导出" 模态框, 即使 `FILEDIA=0` 也跳不过去, 不可静默封装。证据: `scripts/itest_33_tpartsaveas_args_probe.py` 三阶段 + LOGFILEMODE 抓取。|
| BIM导出 | `TGetXML` | 空输入弹 `#32770` “天正模型导出到TGL”，不可静默封装 |
| 单线变墙 | `TSWall` | 已复核：选择 LINE 后回车直接结束，0 实体；未观察到弹框；额外 `240` 被当未知命令。暂不封装（Handoff 15） |
| 搜索房间 | `TUpdSpace` | **已封装为 `search_room`**（Handoff 11，E2E 验证） |

> 其余 ~440 条见 `docs/T20_OFFICIAL_COMMANDS.md`（含真机注册标记）。
> 未注册的 9 条集中在渲染/动画模块（延迟加载 ARX）与官方表笔误。

## 2. 未封装/暂拒命令

已从命令集移除不可行项 (column/axis_grid/export_t3经证实为#32770模态对话框阻塞)。
当前仅保留已验证可命令行驱动的子命令。完整选型历史见`docs/handoff/`系列。

| 命令 | 状态 | 备注 |
|---|---|---|
| 标准柱 TGColumn | 已移除 | #32770 面板阻塞, 命令行点序列不可达 |
| 绘制轴网 TRectAxis | 已移除 | 模态对话框, 不可命令行驱动 |
| 导出天正3 TSaveAs | 已移除 | WPF 框无视 FILEDIA=0 |
| 窗模式切换 | 窗台高走 DoorSill | Handoff 33 真机证实: TCH_OPENING 不暴露独立 SillHeight 属性, 门/窗共用 DoorSill, 模式由面板 + DXF group 71 决定; window 子命令已 sweep 验证 sill_height 参数生效。COM 方法切换路线已排除 (itest_29); window 调用前需人工切面板 |
| 轴网对话框自动化 | 待评估 | TRectAxis控件已侦察, 性价比低, 暂用 axis_lines 替代 |
| TPartSaveAs | Handoff 33 BLOCKED | selection-first 后弹「图形导出」`#32770`, 即便 FILEDIA=0 也无法绕开 (itest_33) |
| TSingleAxisDim | Handoff 33 STOPPED | 提示 `点取待标注的轴线或[手工绘制(D)]<退出>:` 是 entsel 风格, 命令行坐标输入会被命令吞掉后报「未知命令」, 不接受坐标注入; selection-injection 族, 不包装 (itest_32 LOGFILEMODE 抓取) |

## 3. 模板与测试

子命令 → 模板 → 命令 已在 `tangent.py` 的 `_GENERATORS` 字典与 docstring
中维护 (单一事实来源)。离线测试: `uv run pytest -q`。
真机管线: `scripts/itest_01_bringup.py` (引导) → `scripts/itest_12_e2e.py` (核心)
→ `scripts/itest_e2e_suite.py` (批量)。
