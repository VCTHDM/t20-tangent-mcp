# tangent 天正 T20 MCP — 当前态与收尾入口

> 最后校准：2026-07-29（Asia/Shanghai）
>
> 本文件是当前执行入口，不再复述旧分支或旧工作区状态。
> 收尾前后的完整证据保存在 `docs/handoff/38_opening_mode_gate.md`、
> `docs/handoff/39_opening_mode_automation.md`、
> `docs/handoff/40_repository_audit_fresh_e2e.md`、
> `docs/handoff/41_mcp_2026_07_28_protocol.md` 及 Git 历史中。

## 1. 当前基线

- 包版本由 `pyproject.toml` 唯一声明，运行时通过 `t20_mcp.__version__` 读取。
- 当前包版本 `3.2.0`；官方 Python SDK 已迁移到 `mcp>=2.0.0,<3`，现代 stdio
  协议为 `2026-07-28`，并保留 `2025-11-25` legacy 客户端兼容路径。
- MCP 暴露 9 个 consolidated 工具：
  `drawing/entity/layer/block/annotation/pid/view/system/tangent`。
- `tangent` 当前注册 33 个子命令，`EXECUTE_DISABLED_SUBCOMMANDS` 为空。
- 常规子命令走 LISP 模板与参数注入；`column`、`door/window` 是经过真机验证的
  受控 GUI 例外，安全边界见 `PROJECT_RULES.md`。
- 门窗正式链路会自动切换面板模式，创建后仍以 DXF group71（门=0、窗=1）验真；
  错误实体必须删除并返回结构化失败。
- 项目目标是安全封装高价值 T20 命令，不是覆盖官方 454 条命令表。
- 第一批仓库收敛已提交为 `75dbc6c`；未推送远端。
- 第二批真机测试加固与 Handoff 40 当前尚未再次提交。
- 当前离线基线为 `269 passed`；2026-07-26 的 fresh 真机覆盖仍为 33/33 子命令，
  证据强度和保留边界见 Handoff 40。本次协议层迁移未改 File IPC、LISP、T20
  命令序列或 GUI 自动化，因此没有把历史真机结果冒充为 2026-07-29 新复验。

上述数字只代表 2026-07-26 本轮结果；后续修改仍以当次命令输出为准。Handoff 39
中的测试计数只表示 2026-07-24 当次基线。

## 2. 权威文档

| 内容 | 当前来源 |
|---|---|
| 安装、工具名、33 个子命令与常用命令 | `README.md` |
| 子命令映射、行为限制与未交付候选 | `docs/T20_COMMANDS.md` |
| 架构、IPC 与 GUI 例外 | `docs/ARCHITECTURE_NOTES.md` |
| 延后、不交付和重开条件 | `TODO_BACKLOG.md` |
| 历史真机证据 | `docs/handoff/` |

历史 handoff 是不可回写的审计记录。旧测试数、旧文件名、“下一步”和当时的人工
前提按原证据保留；当前行为以上表为准。

## 3. 2026-07-26 已完成

- 全仓代码、配置、文档、测试与打包一致性审查；第一批结果提交为 `75dbc6c`。
- 离线测试从提交前基线 198 项扩至当前 267 项。
- 修复 FileIPC、开洞/爆炸协议、live lock、ezdxf 事务性、wheel 包数据及文档漂移。
- 真机完成 bringup、尺寸 6/6、门窗双向模式门禁、核心 E2E、27-case suite、
  column Gate B 与 explode_read 回滚专项。
- 实机测试脚本统一 UTF-8 输出，收紧会夸大证据的 PASS 判据。
- 旧 `docs/handoff/` 未回写；本轮新证据追加为 Handoff 40。

## 4. 2026-07-29 MCP 协议迁移

- 升级到官方 MCP Python SDK `2.0.0`，服务器从 `FastMCP` 迁移到 `MCPServer`，
  并显式发布 `autocad-mcp` 服务身份和 `3.2.0` 服务版本。
- Python 类型字段切换到 v2 snake_case；SDK 继续在线路上输出规范要求的 camelCase。
- stdio smoke 使用 v2 高层 `Client` 自动探测 `server/discover`，硬断言
  `2026-07-28`、`resultType="complete"`、9 个工具和 tangent dry-run，并以独立
  stdio 子进程验证 legacy `2025-11-25`。
- 离线测试固定覆盖现代 `2026-07-28` 与 legacy `2025-11-25` 两条协议路径。
- 迁移记录追加为 Handoff 41；没有回写 Handoff 40 的历史真机证据。

## 5. 后续变更顺序

1. 审查 `git status` 与逐文件 diff，确认修改归属，不覆盖来源不明的用户改动。
2. 当前行为、工具说明和安全规则有变化时，在同一变更中同步 README、
   `docs/T20_COMMANDS.md`、`TODO_BACKLOG.md` 与必要测试。
3. 执行全部离线门禁。
4. 只有改动触及 File IPC、LISP、T20 命令序列或 GUI 自动化时，才启动真机回归；
   真机脚本必须串行并持有 live lock。
5. 汇总实际验证结果、未验证边界和剩余风险。
6. 未经用户明确同意，不合并到 `main`、不推送远端、不创建发布标签。

本项目不使用、安装或恢复 VibeTrace。

## 6. 离线门禁

```powershell
uv sync --locked
uv run ruff check src tests scripts
uv run ruff format --check src tests scripts
uv run pytest -q
uv run python -m compileall -q src scripts tests
uv run python scripts/itest_19_mcp_stdio_smoke.py
git diff --check
```

验收重点：

- stdio smoke 必须协商到 `2026-07-28`、列出预期 9 个工具，并通过
  `tangent.axis_lines` dry-run；随后必须以 legacy `2025-11-25` 再列出相同工具集。
- 文档/配置变更也必须通过 Ruff、测试、compileall 和 diff check。
- 失败先修复；不得用历史绿灯代替本轮结果。

## 7. 真机门禁

真机前先确认 AutoCAD 2024、T20 V10、dispatcher 和临时图纸处于可恢复状态：

```powershell
uv run python scripts/itest_01_bringup.py
uv run python scripts/itest_19_mcp_stdio_smoke.py
```

触及对应链路时，按风险从窄到宽运行：

```powershell
uv run python scripts/itest_42_opening_panel_mode_auto.py
uv run python scripts/itest_12_e2e.py
uv run python scripts/itest_e2e_suite.py
uv run python scripts/itest_39_column_gate_b_e2e.py
uv run python scripts/itest_25_explode_read_e2e.py
```

真机成功必须同时满足实体类型、关键属性、数量增量、对话框关闭、环境复位和 cleanup；
clean exit、按钮点击成功或 `vl-cmdf` 返回值都不是充分证据。

## 8. 完成标准

- 当前态文档彼此一致，历史 handoff 未被改写。
- 离线门禁全部通过，并记录本轮实际测试数。
- 需要真机复验的变更有新证据；未做真机时明确写“未复验”。
- `git status` 中每个剩余文件都有明确归属，没有临时证据、秘密或未知生成物。
- 延后项和不交付项仍遵守 `TODO_BACKLOG.md` 的重开条件。
