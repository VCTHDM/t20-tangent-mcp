# 平面图视觉检查报告

## 实体清单 (32 个)
- 16 TCH_WALL (WALL 图层) — 脚本画 11 面, 天正交叉处自动分割成 16 段
- 10 TCH_OPENING (全部在 WINDOW 图层) — 5 门 + 5 窗
- 6 TCH_DIMENSION2 (PUB_DIM 图层) — 2 dimension + 4 wall_thickness_dimension
- 1 TCH_NORTHTHUMB (DIM_SYMB, Text=北)
- 1 TCH_DRAWINGNAME (DIM_SYMB)

## 发现的问题

### BUG-1: 门和窗全部在 WINDOW 图层 (严重)
- 5 个门 (DoorSill=0.0) 应在 DOOR/DOOR_FIRE 图层, 但实际在 WINDOW 图层
- Handles: 37F, 380, + 另外 3 个 DoorSill=0 的
- 原因待溯源: opening.lsp 的 {{SET_LAYER}} 对 door/window 子命令的处理

### WARN-1: 墙体端点几何不可读
- TCH_WALL 有 LeftWidth/RightWidth/Height 但无 StartPoint/EndPoint
- 无法程序化验证墙体连接 (端点重合)

### WARN-2: 标注值不可读
- TCH_DIMENSION2 的 Measurement/Text 属性不可读
- 无法程序化验证标注值 (如 12000mm)

### WARN-3: drawing_name 文本不可验证
- TCH_DRAWINGNAME 无可读属性, name_text/scale_text 写入无法验证

### INFO-1: 墙体数量 16 > 11 (正常)
- 天正在墙交叉处自动分割, 11 命令 → 16 实体, 非 bug

### INFO-2: 门窗区分仅靠 DoorSill
- Kind/OpType/Type 属性不可读, DoorSill=0→门, DoorSill>0→窗
