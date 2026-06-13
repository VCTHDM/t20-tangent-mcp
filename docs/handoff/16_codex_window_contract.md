# Handoff 16 — window 子命令人工切窗模式约定

执行者：Codex ｜ 日期：2026-06-13 ｜ 性质：离线补强（未连接 AutoCAD/T20）

## 现场

- 当前分支：`main`，工作区改前干净，`main...origin/main`。
- 已按 README 规则让 ds 做只读对账；ds 建议优先把 `window` 的人工切窗模式约定工具化。
- 本轮未运行真机脚本、未使用 `execute=True`、未触碰 `_prelude.lsp` / IPC / dispatcher。

## 结论

`window` 继续保持部分验证状态：`TOpening` 会沿用天正门窗面板当前模式，COM 属性路线
（`itest_16`）与 COM 方法路线（`itest_29`）均已排除。现阶段不做 WPF 面板自动化，
而是在工具层 warning、模板头注释和文档中明确使用约定：

> 调 `window` 前，用户先手动把天正门窗面板切到窗模式；否则可能生成门对象。

## 改动

- `src/t20_mcp/tools/tangent.py`
  - `window` 生成器 docstring 记录人工切窗模式前提。
  - `LOW_CONFIDENCE_WARNINGS["window"]` 改为明确提示“人工切窗模式”。
  - MCP 工具 docstring 的 `window` 状态同步说明。
- `src/t20_mcp/lisp_templates/tangent/window.lsp`
  - 模板头注释补充人工切窗模式约定。
- `README.md` / `docs/T20_COMMANDS.md` / `docs/handoff/05_fable_field_test.md`
  - 同步 `window` 待办状态，保留 UI 自动化作为后续免人工路线。
- `tests/test_encoding_and_tool.py`
  - dry-run warning 测试新增“人工”“窗模式”断言。

## 验证

```powershell
uv run pytest -q
# 95 passed in 0.67s

uv run python -m compileall -q src scripts tests
# PASS

git diff --check
# PASS（仅工作区 LF/CRLF 提示，无空白错误）
```

## 下一步

1. 若用户能接受人工前置步骤，`window` 可按“部分验证 + 明确前提”使用。
2. 若必须免人工，先写 WPF 门窗面板 UI 自动化方案记录，再碰真机；不得直接猜控件或硬点窗口。
