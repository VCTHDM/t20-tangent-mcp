# Handoff 07 — GPT 接管开发分支

执行人：GPT ｜ 日期：2026-06-13 ｜ 分支：开发分支

## 1. 接管原则

用户已明确本分支不再等待 fable 额度。本分支由 GPT 继续推进，但仍保留真机安全门禁：

- 不把未 E2E 验证的命令开放 `execute=True`；事故相关命令开放前必须有专门 E2E 记录。
- 不再对任何天正窗口发送 `WM_CLOSE`。
- 试驱动脚本若 ESC 无法恢复，只记录现场并改走 `itest_11_force_recover.py` 的按钮点击恢复路线。
- 所有新增封装仍走 LISP 模板 + 参数注入，不写硬编码键击序列。

## 2. 当前落地

1. 新增 `elevation` / `TMElev` 模板：
   - 双点序列：标高基准点 → 标注放置点 → 回车。
   - `scripts/itest_15_elevation.py` 已真机 E2E 验证生成 `TCH_ELEVATION` 并成功 UNDO 清理。
   - `execute=True` 已开放，但工具返回 warning，提醒不得改成单点序列。
2. 修正恢复脚本安全边界：
   - `scripts/itest_08_dialog_recover.py`
   - `scripts/itest_09_opening_axis.py`
   - `scripts/itest_10_opening_props.py`
   这些脚本不再发 `WM_CLOSE`。
3. 文档更新：
   - README 子命令状态、文档索引、待办状态。
   - `docs/T20_COMMANDS.md` 的 `TMElev` 状态与执行门禁。
   - `docs/handoff/06_gpt_tmelev_crash_stop.md` 保留事故现场原始记录。

## 3. 验证

```text
uv run pytest -q
67 passed
```

```text
uv run python scripts/itest_15_elevation.py
elevation: PASS
清理还原: PASS
```

```text
uv run python scripts/itest_16_opening_props_safe.py
TCH_OPENING 属性探测完成, 清理还原: PASS
```

`rg -n "win32con\\.WM_CLOSE|WM_CLOSE" scripts src lisp-code docs README.md` 只剩文档警告和事故记录，没有脚本调用 `win32con.WM_CLOSE`。

## 4. 后续建议

1. 继续离线补强工具层与测试。
2. 真机重新验证前，先确认 AutoCAD/T20 崩溃恢复、自动保存和空白 scratch 图纸。
3. 其它新命令开放 execute 前，需先新增对应 `itest_*.py` 并在 scratch 图纸 E2E 通过。
