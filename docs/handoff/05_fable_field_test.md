# Handoff 05 — Fable 真机联调记录

执行人：Fable ｜ 日期：2026-06-12 ｜ 环境：T20天正建筑 V10.0 + AutoCAD 2024 (中文 Win11)
前置：Handoff 03 审查的 P0/P1/P2 整改（Handoff 04）已逐项核对属实，60 测试全绿后开始联调。
联调脚本：`scripts/itest_01..13_*.py`（可重复执行的管线，新命令验证直接复用）。

## 1. 审查项真机验收结果

| 项 | 结果 |
|---|---|
| P0-3 引导链路 | **PASS**：冷启动 initialize 报未加载 → 自动 `(load)`（拷至 ASCII 路径绕中文路径+SECURELOAD）→ ping pong |
| P0-1/P2-1 编码往返 | **PASS**：中文图层 GBK 字节级往返无损（见 §3 的解码链修正） |
| P0-4 错误路径 | **PASS**：未知命令走 fail 分支（USERS1 回传验证），CMDDIA/FILEDIA/OSMODE/ATTDIA/ATTREQ/EXPERT/DIMZIN 七值前后一致，0 垃圾实体 |
| P1-1 窗口识别 | **PASS**：进程名主判据命中 `T20天正建筑…` 标题主窗；多实例告警真机触发且选择正确（.dwg 标题优先） |
| P1-2 模态防护 | **部分**：`#32770`（AutoCAD 原生/轴网框）可探测；**天正 WPF 框（HwndWrapper）探测不到**——已知盲区，文档化 |
| P1-4 命令编目 | **完成且超额**：见 §2 |

## 2. 命令名问题的根治（回应"为什么尬猜"）

推测命令名的做法已废弃。命令名权威来源 = 本机安装目录官方命令表
`C:\Tangent\TArchT20V10\SYS\tchcmd.txt`（454 条中文名→命令名映射）：

- UTF-8 原始副本：`docs/t20_official_commands.txt`
- 全表 + 真机 getcname 注册标记（442/451 命中）：`docs/T20_OFFICIAL_COMMANDS.md`
- 封装相关精编：`docs/T20_COMMANDS.md`（已重写）

未注册的 9 条 = 渲染/动画延迟加载模块 + 官方表笔误（`TOuterDimTOuterDim`）。
**后续新增封装一律先查官方表，不允许再猜**；需要外部资料（如交互序列文章）时
明示需求，由便宜模型执行检索。

## 3. 真机发现与修复

1. **解码链字节碰撞（P0-1 修正）**：`砖` 的 GBK 字节 `D7A9` 恰为合法 UTF-8
   （U+05E9 ש），原 utf-8 优先链把 GBK 结果解成 mojibake。已改为 **ANSI 优先**
   （结果文件按契约必然 ANSI 写出；ASCII 在 ANSI 下解码相同，无回归），
   utf-8 降为回退。回归测试：`test_gbk_utf8_collision_char_not_mojibaked`。
2. **vl-cmdf 假成功**：无效关键字被命令吞掉后正常返回（非 nil）、0 实体。
   `wall` 模板原推测的 `L/R/H/T` 序列即如此。对策：所有模板改为
   **实体增量 + TCH_* 类型校验** 作为成功判据。
3. **可行驱动模式确立**：命令行给点（面板记忆参数）→ 生成 TCH_* 实体 →
   **ActiveX 属性事后注参**。已验证属性：
   - `TCH_WALL`: LeftWidth/RightWidth/Height/Style(材料,默认"砖")/Usage/Elevation/InsuThick
   - `TCH_OPENING`: Width/Height/DoorSill（SillHeight 在门模式不存在）
4. **天正对话框两例证实**（编目坑 1）：`TSaveAs` WPF 导出框无视 FILEDIA=0；
   `TRectAxis` 模态 #32770。**对天正 ARX 对话框发 WM_CLOSE 会触发 AutoCAD
   致命错误**（真机崩溃一次，已重启恢复，scratch 图纸无损失）——恢复手段只允许
   ESC 键或点"取消"按钮（`itest_11_force_recover.py`）。
5. **CMDDIA/FILEDIA 残留**：对话框阻塞会使 prelude 恢复分支无法执行，静默态
   （CMDDIA=0 等）泄漏且**随注册表跨重启持久**。联调脚本现含复位逻辑；
   后续可考虑在 initialize 时检测并提示。

## 4. 端到端验收（生产路径 generate_lisp → execute_lisp）

| 子命令 | 结果 |
|---|---|
| wall | **PASS**：TCH_WALL，COM 回读 LeftWidth=240/RightWidth=120/Height=3300/Style=砖 |
| dimension | **PASS**：TCH_DIMENSION2（顺序=位置点→点1→点2→回车） |
| door | **PASS**：TCH_OPENING，回读 Width=1000/Height=2000/DoorSill=0 |
| 清理 | UNDO 全还原至 0 实体，环境复位 CMDDIA=1/FILEDIA=1 |

离线测试：**64 passed**。

## 5. 代码改动汇总

- `wall.lsp`/`dimension.lsp`/`door.lsp`/`window.lsp`：验证序列 + 实体增量校验 + COM 注参
- `axis_grid.lsp`(TRectAxis)/`export_t3.lsp`(TSaveAs)：官方名 + 不可驱动注记
- `tangent.py`：`EXECUTE_DISABLED_SUBCOMMANDS`（axis_grid/export_t3 拒绝 execute，
  dry-run 附 `execute_disabled`）；LOW_CONFIDENCE 收窄为 {door,window}；
  wall_type 默认 "砖墙"→"砖"（Style 为材料名）；docstring 标注验证状态
- `file_ipc.py`：`_decode_result_bytes` ANSI 优先（见 §3.1）
- 测试：64 个（新增碰撞回归、execute 禁用、TDIMMP 顺序等）

## 6. 遗留（按优先级）

1. window 子命令：窗模式下的类型切换与 SillHeight 属性（需面板处于窗模式或找到 COM 类型切换属性）
2. 轴网替代路径：逐根轴线 + `TSingleAxisDim`，或 UI 自动化
3. 导出替代路径：`TPartSaveAs` / `TGetXML`（BIM 导出）调研
4. `TExplode` + ezdxf 临时副本读取管线
5. ~~P1-2 防护对 WPF 框的探测~~ **已完成**（2026-06-13，Handoff 09：
   改用「主窗口 IsWindowEnabled」信号，与类名/线程无关；itest_21 真机验收通过）
