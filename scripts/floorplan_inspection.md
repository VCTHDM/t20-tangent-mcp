# 平面图视觉检查报告（历史快照，问题已闭合）

> 本报告的 32 实体快照早于 `56875cb`、`b0a23b2` 与 Handoff 38，保留用于说明
> 问题如何被发现，不代表当前行为。2026-07-24 复验为 35 实体：门 5 个位于
> `DOOR_FIRE`、窗 5 个位于 `WINDOW`，全部断言通过。

## 实体清单 (32 个)
- 16 TCH_WALL (WALL 图层) — 脚本画 11 面, 天正交叉处自动分割成 16 段
- 10 TCH_OPENING (当时全部在 WINDOW 图层) — 5 门 + 5 窗
- 6 TCH_DIMENSION2 (PUB_DIM 图层) — 2 dimension + 4 wall_thickness_dimension
- 1 TCH_NORTHTHUMB (DIM_SYMB, Text=北)
- 1 TCH_DRAWINGNAME (DIM_SYMB)

## 当时发现的问题与当前裁定

### BUG-1: 门和窗全部在 WINDOW 图层 — 已修复
- 5 个门 (DoorSill=0.0) 应在 DOOR/DOOR_FIRE 图层, 但实际在 WINDOW 图层
- Handles: 37F, 380, + 另外 3 个 DoorSill=0 的
- 修复: `b0a23b2` 将 door 强制写入 `DOOR_FIRE`、window 写入 `WINDOW`；
  Handoff 38 又以 DXF group71 (0=门, 1=窗) 增加权威模式校验与错误实体回滚；
  Handoff 39 已进一步自动切换插门/插窗模式

### WARN-1: 墙体端点几何不可读 — 已找到读回路径
- TCH_WALL 不暴露 COM `StartPoint/EndPoint` 属性，但可通过
  `vlax-curve-getStartPoint/EndPoint` 读回；`itest_dim_precision_verify.py` 已真机验证端点重合

### WARN-2: 天正逐点标注值不可读 — 语义已隔离
- TCH_DIMENSION2 的 Measurement/Text 属性不可读
- 建筑总宽/总高已改用原生 DIMLINEAR，可读且确定；TCH_DIMENSION2 仅保留
  逐点吸附、墙厚等天正语义，并用类型/数量与穿越场景验收

### WARN-3: drawing_name 文本不可验证 — 已闭合
- Handoff 35 已通过 `NameText/ScaleText` COM 写入与读回精确匹配验证

### INFO-1: 墙体数量 16 > 11 (正常)
- 天正在墙交叉处自动分割, 11 命令 → 16 实体, 非 bug

### INFO-2: 门窗权威区分
- DoorSill 只承载距墙垛/窗台高；门窗类型以 DXF group71 为准：0=门，1=窗
