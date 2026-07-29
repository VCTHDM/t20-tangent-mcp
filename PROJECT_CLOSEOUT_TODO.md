# tangent 天正 T20 MCP — 当前态与收尾入口

> 最后校准：2026-07-26（Asia/Shanghai）
>
> 本文件是当前执行入口，不再保存旧分支、旧工作区和旧测试数字。2026-07-24
> 收尾前后的完整证据保存在 `docs/handoff/38_opening_mode_gate.md`、
> `docs/handoff/39_opening_mode_automation.md` 及 Git 历史中。

## 1. 当前基线

- 包版本由 `pyproject.toml` 唯一声明，运行时通过 `t20_mcp.__version__` 读取。
- MCP 暴露 9 个 consolidated 工具：
  `drawing/entity/layer/block/annotation/pid/view/system/tangent`。
- `tangent` 当前注册 33 个子命令，`EXECUTE_DISABLED_SUBCOMMANDS` 为空。
- 常规子命令走 LISP 模板与参数注入；`column`、`door/window` 是经过真机验证的
  受控 GUI 例外，安全边界见 `PROJECT_RULES.md`。
- 门窗正式链路会自动切换面板模式，创建后仍以 DXF group71（门=0、窗=1）验真；
  错误实体必须删除并返回结构化失败。
- 项目目标是安全封装高价值 T20 命令，不是覆盖官方 454 条命令表。

当前测试数量不写死在本文。以本轮 `uv run pytest -q` 输出为准；Handoff 39
中的测试计数只表示 2026-07-24 当次离线基线。

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

## 3. 本轮收尾顺序

1. 审查 `git status` 与逐文件 diff，确认修改归属，不覆盖来源不明的用户改动。
2. 当前行为、工具说明和安全规则有变化时，在同一变更中同步 README、
   `docs/T20_COMMANDS.md`、`TODO_BACKLOG.md` 与必要测试。
3. 执行全部离线门禁。
4. 只有改动触及 File IPC、LISP、T20 命令序列或 GUI 自动化时，才启动真机回归；
   真机脚本必须串行并持有 live lock。
5. 汇总实际验证结果、未验证边界和剩余风险。
6. 未经用户明确同意，不合并到 `main`、不推送远端、不创建发布标签。

本项目不使用、安装或恢复 VibeTrace。

## 4. 离线门禁

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

- stdio smoke 必须列出预期 9 个工具，并通过 `tangent.axis_lines` dry-run。
- 文档/配置变更也必须通过 Ruff、测试、compileall 和 diff check。
- 失败先修复；不得用历史绿灯代替本轮结果。

## 5. 真机门禁

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
```

真机成功必须同时满足实体类型、关键属性、数量增量、对话框关闭、环境复位和 cleanup；
clean exit、按钮点击成功或 `vl-cmdf` 返回值都不是充分证据。

## 6. 完成标准

- 当前态文档彼此一致，历史 handoff 未被改写。
- 离线门禁全部通过，并记录本轮实际测试数。
- 需要真机复验的变更有新证据；未做真机时明确写“未复验”。
- `git status` 中每个剩余文件都有明确归属，没有临时证据、秘密或未知生成物。
- 延后项和不交付项仍遵守 `TODO_BACKLOG.md` 的重开条件。
