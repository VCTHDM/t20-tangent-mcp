# T20 天正建筑 MCP Server

适配 **T20 天正建筑 V10 + 完整版 AutoCAD（中文 Windows）** 的 MCP Server。
基于上游 [autocad-mcp](vendor/autocad-mcp/)（面向 AutoCAD LT）改造：重做 IPC 编码链、
窗口识别与对话框防护，并新增天正建筑专业实体（墙/门窗/标注等 `TCH_*` 自定义对象）的
LISP 模板封装。

> 本 README 面向接手者（人或 AI）。读完本页 + 「文档索引」即可继续开发。

## 当前完成度：约 60%

| 领域 | 完成度 | 说明 |
|---|---|---|
| IPC 基础设施（编码链/窗口识别/模态防护/引导加载） | ~95% | 全部真机验收通过；遗留：天正 WPF 对话框探测盲区 |
| 命令编目 | 100% | 官方表 454 条全部收录并真机探测注册状态（442/451） |
| 天正实体封装 | ~25% | wall/dimension 已 E2E 验证，door 部分验证；轴网/导出受对话框阻碍；柱/楼梯/房间/屋顶等未动工 |
| MCP server 集成 | ~90% | 9 工具已注册（含 `tangent`）；经 MCP 协议的端到端冒烟未做 |
| 测试与联调管线 | ~85% | 离线 64 测试全绿；`scripts/itest_*.py` 可重复真机管线 |

## 快速开始

```powershell
uv sync                                  # 安装依赖 (Python 3.10+)
uv run pytest -q                         # 离线测试 (不需要 AutoCAD)

# 真机联调 (需 T20 + AutoCAD 已启动并打开 .dwg):
uv run python scripts/itest_01_bringup.py   # 窗口识别 + 自动加载 dispatcher + ping
uv run python scripts/itest_12_e2e.py       # wall/dimension/door 端到端验收

# 作为 MCP server (stdio):
uv run python -m t20_mcp.server          # 或在 MCP 客户端配置 command 指向它
```

MCP 工具共 9 个：上游 8 个（drawing/entity/layer/block/annotation/pid/view/system）
+ 本项目新增 **`tangent`**（天正实体，**默认 dry-run**，传 `execute=True` 才下发）。

## `tangent` 子命令状态（真机：T20 V10 / AutoCAD 2024, 2026-06-12）

| 子命令 | 天正命令 | 状态 |
|---|---|---|
| `wall` 墙体 | `TgWall` | ✅ E2E 验证（实体 + COM 属性回读） |
| `dimension` 逐点标注 | `TDimMP` | ✅ E2E 验证 |
| `door` 门 | `TOpening` | 🟡 部分验证（execute 附 warning） |
| `window` 窗 | `TOpening` | 🟡 类型随面板模式、窗台高未保证 |
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
- 所有天正封装走 **LISP 模板 + 参数注入**，不允许硬编码键击序列（CLAUDE.md）。
- `tangent` 工具**默认 dry-run**；纯对话框命令禁止 execute。

## 文档索引

| 文档 | 内容 |
|---|---|
| `docs/T20_COMMANDS.md` | 封装相关命令精编 + 驱动方式 + **待办 §3** |
| `docs/T20_OFFICIAL_COMMANDS.md` | 官方 454 条命令全表 + 真机注册标记 |
| `docs/t20_official_commands.txt` | 官方表原始副本（源：`C:\Tangent\TArchT20V10\SYS\tchcmd.txt`） |
| `docs/handoff/03_fable_review.md` | 架构审查（P0/P1/P2 整改清单，已全部完成） |
| `docs/handoff/04_gemini_fixes.md` | 整改记录 |
| `docs/handoff/05_fable_field_test.md` | **真机联调全记录**（发现/修复/崩溃教训/遗留 §6） |
| `scripts/itest_01..14_*.py` | 可重复的真机联调管线（引导/探测/试驱动/E2E/恢复/清理） |

## 路线图（按优先级）

1. **window 完善**：找 TOpening 门/窗类型的 COM 切换属性与窗模式 `SillHeight`
   （管线：`itest_10_opening_props.py` 改属性候选名重跑）。
2. **更多实体封装**（照上面方法论）：标准柱 `TGColumn`、两点标注 `TDimTP`、
   墙厚标注 `TDimWall`、标高标注 `TMElev`、单线变墙 `TSWall`、搜索房间 `TUpdSpace`。
3. **轴网替代路径**：逐根轴线 + `TSingleAxisDim` 组合，或 UI 自动化填 `TRectAxis` 框。
4. **导出替代路径**：调研 `TPartSaveAs`（局部导出）、`TGetXML`（BIM 导出）是否可静默。
5. **TExplode + ezdxf 读取管线**：仅在临时副本上分解（破坏性！禁止动用户当前图纸）。
6. **MCP 协议端到端冒烟**：以真实 MCP 客户端连 server 跑一遍 `tangent`。
7. P1-2 防护补盲：探测天正 WPF（HwndWrapper）对话框。

> 待办的权威位置：本节（路线图）+ `docs/T20_COMMANDS.md` §3 + `docs/handoff/05_fable_field_test.md` §6。
> 完成一项请同步更新这三处与上方完成度表。
