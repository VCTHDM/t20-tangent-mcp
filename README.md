# T20 天正建筑 MCP Server

适配 **T20 天正建筑 V10 + 完整版 AutoCAD（中文 Windows）** 的 MCP Server。
基于上游 [autocad-mcp](vendor/autocad-mcp/)（面向 AutoCAD LT）改造：重做 IPC 编码链、
窗口识别与对话框防护，并新增天正建筑专业实体（墙/门窗/标注等 `TCH_*` 自定义对象）的
LISP 模板封装。

> 本 README 面向接手者（人或 AI）。读完本页 + 「文档索引」即可继续开发。

> 当前主分支由 claude 接管推进（fable 额度用尽退出）；codex 作为辅助执行。
> 但真机安全门禁仍保留：未 E2E 或事故相关命令只允许 dry-run，不开放 execute。

## 当前完成度：约 75%

| 领域 | 完成度 | 说明 |
|---|---|---|
| IPC 基础设施（编码链/窗口识别/模态防护/引导加载） | 100% | 全部真机验收通过；WPF 对话框探测盲区已补（Handoff 09，itest_21） |
| 命令编目 | 100% | 官方表 454 条全部收录并真机探测注册状态（442/451） |
| 天正实体封装 | ~50% | wall/dimension/wall_thickness_dimension/opening_dimension/elevation/explode_read/search_room/column 已 E2E 验证，axis_lines 普通线轴网替代可执行，door 部分验证；导出受对话框阻碍；楼梯/屋顶等未动工 |
| MCP server 集成 | ~95% | 9 工具已注册（含 `tangent`）；MCP stdio dry-run 冒烟已通过 |
| 测试与联调管线 | ~88% | 离线测试全绿；`scripts/itest_*.py` 可重复真机管线，E2E 收尾环境已校验 |

## 快速开始

```powershell
uv sync                                  # 安装依赖 (Python 3.10+)
uv run pytest -q                         # 离线测试 (不需要 AutoCAD)

# 真机联调 (需 T20 + AutoCAD 已启动并打开 .dwg):
uv run python scripts/itest_01_bringup.py   # 窗口识别 + 自动加载 dispatcher + ping
uv run python scripts/itest_12_e2e.py       # wall/dimension/door 端到端验收

# 作为 MCP server (stdio):
uv run python -m t20_mcp                 # 或在 MCP 客户端配置 command 指向它
```

MCP 工具共 9 个：上游 8 个（drawing/entity/layer/block/annotation/pid/view/system）
+ 本项目新增 **`tangent`**（天正实体，**默认 dry-run**，传 `execute=True` 才下发）。

## `tangent` 子命令状态（真机：T20 V10 / AutoCAD 2024, 2026-06-13）

| 子命令 | 天正命令 | 状态 |
|---|---|---|
| `wall` 墙体 | `TgWall` | ✅ E2E 验证（实体 + COM 属性回读） |
| `dimension` 逐点标注 | `TDimMP` | ✅ E2E 验证 |
| `wall_thickness_dimension` 墙厚标注 | `TDimWall` | ✅ E2E 验证 |
| `opening_dimension` 门窗标注 | `TDim3` | ✅ E2E 验证 |
| `elevation` 标高标注 | `TMElev` | ✅ 双点序列 E2E 验证（实体 `TCH_ELEVATION`）；execute 附 warning，严禁改成单点序列 |
| `column` 标准柱 | `TGColumn` | ✅ E2E 验证（插入点生成 `TCH_COLUMN`；截面尺寸来自面板记忆值） |
| `door` 门 | `TOpening` | 🟡 部分验证（execute 附 warning） |
| `window` 窗 | `TOpening` | 🟡 类型随面板模式、窗台高未保证 |
| `axis_lines` 普通线轴网 | 原生 `LINE` | 🟡 可执行替代路径，生成普通线，不是天正智能轴网 |
| `explode_read` 几何读回 | 原生 `EXPLODE` | ✅ E2E 验证（副本分解+回滚，非破坏；墙体起点侧有已知 T20 缺陷，见 Handoff 10） |
| `search_room` 搜索房间 | `TUpdSpace` | ✅ E2E 验证（全选墙体+回车，生成 `TCH_SPACE`） |
| `axis_grid` 轴网 | `TRectAxis` | ⛔ 模态对话框，execute 已禁用（仅 dry-run） |
| `export_t3` 导出T3 | `TSaveAs` | ⛔ WPF 导出框无视 FILEDIA=0，execute 已禁用 |

## 已验证的封装方法论（新增命令照此办理）

1. **查官方命令表取名**（`docs/T20_OFFICIAL_COMMANDS.md`，严禁猜命令名）；
2. `getcname` 真机预检注册（`scripts/itest_03_probe.py` 模式）；
3. **最小点序列**试驱动（命令行给点，参数走天正面板记忆值）；
4. **实体增量 + `TCH_*` 类型校验**判成败（`vl-cmdf` 返回值会"假成功"，不可信）；
5. 几何/尺寸参数经 **ActiveX 属性事后注入**（`vlax-put-property`，
   如 `TCH_WALL.LeftWidth/Height/Style`、`TCH_OPENING.Width/DoorSill`）。

模板骨架与防御机制（环境保存/恢复、局部 `*error*`、UNDO 组、命令预检）见
`src/t20_mcp/lisp_templates/tangent/_prelude.lsp`。

## 铁律与教训（违反会乱码/崩溃/污染用户环境）

- **编码契约**：仓库内 .lsp 模板 UTF-8；写给 AutoCAD `(load)` 前整体转 **GBK 无 BOM**；
  结果文件按**系统 ANSI 优先**解码（GBK 字节可能恰为合法 UTF-8，如 `砖`=D7A9=ש，
  utf-8 优先会静默 mojibake）。详见 `_prelude.lsp` 头部契约。
- **严禁对天正 ARX 对话框发 `WM_CLOSE`**——真机曾因此 AutoCAD 致命错误崩溃。
  恢复只允许 ESC 键或点"取消"按钮（`scripts/itest_11_force_recover.py`）。
- `CMDDIA`/`FILEDIA` 等静默态若因对话框阻塞未被 prelude 恢复，会**经注册表跨重启
  泄漏**，恢复后须复位（`scripts/itest_14_cleanup.py`）。
- 所有天正封装走 **LISP 模板 + 参数注入**，不允许硬编码键击序列（PROJECT_RULES.md）。
- `tangent` 工具**默认 dry-run**；纯对话框命令禁止 execute。

## 文档索引

| 文档 | 内容 |
|---|---|
| `docs/T20_COMMANDS.md` | 封装相关命令精编 + 驱动方式 + **待办 §3** |
| `docs/T20_OFFICIAL_COMMANDS.md` | 官方 454 条命令全表 + 真机注册标记 |
| `docs/t20_official_commands.txt` | 官方表原始副本（源：`C:\Tangent\TArchT20V10\SYS\tchcmd.txt`） |
| `docs/handoff/03_fable_review.md` | 架构审查（P0/P1/P2 整改清单，已全部完成） |
| `docs/handoff/04_gpt_fixes.md` | 整改记录 |
| `docs/handoff/05_fable_field_test.md` | **真机联调全记录**（发现/修复/崩溃教训/遗留 §6） |
| `docs/handoff/06_gpt_tmelev_crash_stop.md` | `TMElev` 试驱动后闪退停手记录 |
| `docs/handoff/07_gpt_branch_takeover.md` | GPT 接管本分支后的安全门禁与当前状态 |
| `docs/handoff/08_gpt_field_test.md` | GPT 本轮真机联调结果（bringup/E2E/elevation/opening props） |
| `docs/handoff/09_fable_wpf_guard.md` | P1-2 补盲：模态对话框探测（IsWindowEnabled 信号，itest_21 验收） |
| `docs/handoff/10_fable_explode_read.md` | explode_read 几何读回管线（选型/教训/T20 缺陷/对话框自动化） |
| `docs/handoff/11_fable_search_room.md` | search_room 封装（TUpdSpace 一轮通过）+ LASTPROMPT 捕获法失败记录 |
| `docs/research/2026-06-13_*.md` | GPT 调研：网搜与安装目录提示词检索（结论：需真机提示捕获） |
| `scripts/itest_01..27_*.py` | 可重复的联调管线（引导/探测/试驱动/E2E/MCP stdio/恢复/清理） |

## 分工规则（二人制：claude = 执行人/审查者，codex = 辅助执行）

执行者读到这里先认领身份，按下面两条规则干活。commit 前缀：claude 用 `[claude]`，
其他执行者（含 codex）一律 `[assist]`。

**规则 1 —— 以下情况必须 claude，codex 不得动手：**
- 改**基础设施**：`_prelude.lsp`、`file_ipc.py`、`mcp_dispatch.lsp`、编码契约相关的任何一行；
- **疑难现场**：AutoCAD 崩溃/挂死、乱码、环境变量污染、IPC 超时反复出现；
- **探索性决策**（没有现成管线可抄的）：轴网/导出替代路径选型、TExplode 管线设计；
- 每批封装**合入前的 review** 与最终验收（MCP 协议冒烟）。

**规则 2 —— 体力活给 GPT，但触发即停：**
照「封装方法论」五步管线（见上文）可完成的活都归 GPT：批量封装、属性探测、
文档回填、测试补全。**一旦遇到以下任一情况立即停手**，把现场（脚本输出、
AutoCAD 命令行回显、最后一次 diff）写进 `docs/handoff/` 新文档后移交 claude，
禁止自行硬试：
- 命中规则 1 的任何条目（尤其：想改 prelude / 想强关对话框 / 想猜命令名）；
- 同一命令试驱动 **2 轮**仍是假成功或 0 实体；
- 出现弹框阻塞、ping 不通、或任何"教训"清单（见铁律一节）里的现象。

## 待办（按优先级，标了执行人）

**GPT（体力活，照管线抄作业）：**
1. **window 完善**：COM 属性（itest_16）与 COM 方法（itest_29：
   GetKind/SetKind/GetSubKind/SetSubKind 等全部未暴露）两条路线均已排除；
   剩余路线为门窗面板 UI 自动化（WPF，待 claude 决策）或文档化"用户先手动
   切窗模式"的使用约定。
2. **批量封装 6 命令**——进度：墙厚标注 `TDimWall`、标高标注 `TMElev`、
   搜索房间 `TUpdSpace`（→`search_room`，Handoff 11）与标准柱 `TGColumn`
   （→`column`，Handoff 12）均已完成 E2E；两点标注 `TDimTP`、单线变墙
   `TSWall` 已抓到命令行提示但最小成功序列仍待验证。
3. **导出替代探测**：`TPartSaveAs`/`TGetXML` 注册预检 + 最小试驱动；**弹框即记录停手**，
   只产出调研结论，不做绕过尝试。
4. 文档/测试补全、截图存档。

**claude（审查与硬骨头）：**
1. GPT 每批封装的 review + 合入（参照 `docs/handoff/03` 的审查模式）。
2. **轴网替代路径**选型与实现（逐根轴线+`TSingleAxisDim` 组合 vs UI 自动化）。
3. ~~TExplode + ezdxf 管线~~ 已完成（Handoff 10：实体副本 + 原生 EXPLODE 路线，
   `explode_read` 子命令 E2E 验收；ezdxf proxy 路线被真机否决）。
4. ~~P1-2 防护补盲~~ 已完成（Handoff 09：主窗口 IsWindowEnabled 信号，itest_21 真机验收）。
5. **MCP 协议端到端冒烟**（最终验收，完成后更新完成度表）。

> 待办的权威位置：本节 + `docs/T20_COMMANDS.md` §3 + `docs/handoff/05_fable_field_test.md` §6。
> 完成一项请同步更新这三处与上方完成度表。
