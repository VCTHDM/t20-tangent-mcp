# Handoff 10 — explode_read: 天正实体几何读回管线

执行人：fable ｜ 日期：2026-06-13 ｜ 环境：T20天正建筑 V10.0 + AutoCAD 2024（Drawing1.dwg）

## 1. 目标与选型过程（探索全记录，含被否决路线）

目标：把 `TCH_*` 自定义实体读回为普通几何（MCP 客户端可消费），不破坏用户图纸。

| 候选路线 | 探测 | 结论 |
|---|---|---|
| DXF 导出 + ezdxf proxy graphics 解码 | itest_22 | **否决**：`PROXYGRAPHICS=1` 下 TCH_WALL 的 proxy 块仅 8 字节（空头部）。副产物：`DXFOUT` 实测不改 `DWGNAME`（会话安全，区别于 `SAVEAS DXF`） |
| 文件副本 + 第二实例/accoreconsole | 纸面分析 | **否决**：accoreconsole 加载不了天正 ARX；同会话切文档断 per-document LISP 命名空间 |
| 实体副本 + `TEXPLODE` | itest_23/24 | 可行但必弹「分解对象」框 (#32770)，需对话框按钮自动化（已验证，见 §3） |
| 实体副本 + 原生 `_.EXPLODE` | itest_25 | **采用**：对 TCH 实体有效且不弹框 |
| COM `Explode` 方法 | 一次性探测 | 否决：TCH_WALL 未暴露（"未知名称: EXPLODE"） |

最终管线（`lisp_templates/tangent/explode_read.lsp`，UNDO 组包裹）：
COPY 目标实体到暂存区（默认 +1e6,+1e6）→ `_.EXPLODE` 仅分解副本 →
`t20mcp:geo1`（prelude 新增）序列化产物 → 模板内 `_.U` 整组回滚 →
Python `parse_explode_payload` 平移坐标回原位。**用户原实体全程不被修改。**

## 2. 真机教训（新增三条，都会复现，勿再踩）

1. **原位复制墙体 → 天正弹「处理重合的墙体」模态框**（删除墙A/墙B）。
   副本必须位移到远离一切实体的暂存区（参数层强制 ≥1e5）。
2. **COPY 默认多重复制**（2006+）：位移点后不补 `""`，命令保持活动，
   后续输入全被灌进 COPY 提示。模板已补结尾回车。
3. **预选会被命令启动清空**：`sssetfirst`（含 `PICKFIRST=1`）对 `vl-cmdf`
   启动的命令无效；选择集必须走 vl-cmdf 参数队列。

## 3. 对话框按钮自动化（新基础设施，本轮验证但未投产）

`src/t20_mcp/dialog_automation.py`：白名单（标题+按钮文本精确匹配）+
`BM_CLICK`，黑名单按钮（「分解本图所有天正对象」等）硬拒绝，**严禁 WM_CLOSE**。
itest_24 真机验证：与阻塞中的 LISP dispatch 并发点击「分解对象」框的
「分解当前选中的天正对象」+「确定」，命令恢复执行且选择集参数被正常消费。

虽然 explode_read 最终改用不弹框的原生 EXPLODE，该模块为
**axis_grid (TRectAxis) / 导出类弹框命令**的后续驱动提供了已验证的原语。
新增白名单条目必须 fable review。

## 4. 已知 T20 缺陷（重要）

**墙体 explode 产物的起点侧顶点归零**：`(10 0.0 0.0 0.0)`，终点侧正确。
- `TEXPLODE` 与原生 `_.EXPLODE` 同样表现（同源实现）；
- 与 COPY 无关（直接分解基线 (5000,4000)→(8000,4000) 的原墙同样复现）；
- `vla-Update`/`REGEN` 无效；
- **墙体本身数据健康**：`vlax-curve-getStartPoint/EndPoint` 返回正确基线，
  COM `LeftWidth/RightWidth/Height` 正确 → 墙体精确几何应走曲线协议+宽度计算，
  explode_read 适用于其他实体类型的读回。
- execute 成功 payload 附 warning 说明此缺陷。

## 5. 验收

- itest_25（生产路径 E2E）：4 LINE 产物、终点侧坐标平移正确、缺陷签名容忍、
  `clean=T` 模板内回滚、最终图纸回空、环境干净 —— 全 PASS。
- 离线：`uv run pytest -q` 89 passed（新增 explode_read 渲染/校验/解析 +
  dialog_automation 白名单测试）；`compileall` 通过。

## 6. 后续可做

1. 墙体专用读回：`vlax-curve` + 宽度的解析式 outline（不经 explode）。
2. 用 explode_read 验证 TCH_OPENING / TCH_DIMENSION2 的产物质量。
3. dialog_automation 扩展到 TRectAxis 参数框（需先真机枚举控件再定白名单）。
