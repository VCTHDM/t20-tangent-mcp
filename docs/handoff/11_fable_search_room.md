# Handoff 11 — search_room (TUpdSpace) 封装 + 提示捕获尝试

执行人：fable ｜ 日期：2026-06-13 ｜ 环境：T20天正建筑 V10.0 + AutoCAD 2024

## 1. search_room 子命令（新增，E2E 验证）

GPT 两轮调研（docs/research/）无 TUpdSpace 序列线索，真机试驱动一轮即成：

- 序列：`ssget "_X" TCH_WALL` 全选墙体 → 选择集 → 回车；
- 四段闭合墙（4000×3000 矩形）→ 生成 1 个 **TCH_SPACE**，`CMDACTIVE=0`；
- 模板 `search_room.lsp`，无墙时 fail（no-walls-in-drawing），
  未新增 TCH_SPACE 时 fail（保守判据；"更新已有房间"场景的判据待补）；
- itest_27 E2E：建墙→search_room→TCH_SPACE→UNDO 清理→环境干净，全 PASS；
- 离线 90 passed。

## 2. LASTPROMPT 提示捕获法 — 失败，记录在案

设想：`vl-cmdf` 启动命令（不给参数）→ 读 `LASTPROMPT` 取首个提示 → cancel。
实测（itest_26 Phase A）：`CMDACTIVE=1` 确认命令已启动，但 `LASTPROMPT`
返回的是此前 dispatch 的回显文本——**vl-cmdf 启动的命令在挂起等输入时,
其提示不会进入 LASTPROMPT**（可能要命令结束才刷新）。该路线对
TGColumn/TDimTP/TSWall 无效。

候选后续（均未做）：AutoCAD `*command-will-start*` reactor + prompt reactor；
或人工跑一遍命令记录提示。三命令维持「待验证、不开放 execute」。

## 3. 当前 tangent 子命令账面

新增后共 12 个 operation：wall / dimension / wall_thickness_dimension /
opening_dimension / elevation / door / window / axis_lines / axis_grid(dry) /
export_t3(dry) / explode_read / **search_room**。
