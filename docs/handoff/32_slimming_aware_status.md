# Handoff 32 — slimming-aware current package status

日期: 2026-06-17
分支: main (HEAD = 76a2a3b 之后, 含本次 P0 文档/测试漂移清理)

本文件**不**改写历史 handoff 28/29/30/31 的事实记录, 只在 slimming 提交
`441e890` (remove 42 one-off scripts, 3 disabled subcommands, vendor/) 之后
为后续接手者补一份"当前可调用资产清单 + 命名漂移修复说明", 防止盲跑已删脚本。

---

## 1. 当前 tangent 子命令 (32 个, 与 src/t20_mcp/tools/tangent.py SUBCOMMANDS 一致)

```
axis_lines, wall, door, window, dimension, wall_thickness_dimension,
opening_dimension, two_point_dimension, elevation, coordinate, symmetry,
line_pattern, north_arrow, break_line, section_symbol, drawing_name,
rectangle, balcony, step, ramp, arrow, rect_roof, cusp_roof, insight,
tree, line_stair, arc_stair, double_stair, multi_stair,
wheelchair_diameter, explode_read, search_room
```

### 当前 LOW_CONFIDENCE_SUBCOMMANDS
`arrow, door, drawing_name, elevation, window`

### 当前 EXECUTE_DISABLED_SUBCOMMANDS
空字典 `{}` — 没有任何子命令在 dispatcher 层被禁用执行。

### 已从主代码中移除的子命令 (历史 handoff 仍可能提到)
- `axis_grid` — 替代路径 `axis_lines` (普通 LINE 轴网, 非天正智能轴网)。
- `column` — TGColumn `#32770` 标准柱面板阻塞 (Handoff 13)。
- `export_t3` — TSaveAs 走 WPF 导出框, 不可静默封装 (Handoff 18 等)。

> 这些子命令再次被调用时, `generate_lisp(...)` 抛出 `ParamError("未知 tangent 子命令: ...")`,
> 由 `tests/test_tangent_lisp_gen.py::TestParamRejection::test_removed_axis_grid_subcommand_rejected` 守住回归。

---

## 2. 当前 scripts/ 实际存在的 itest_*.py (slimming 之后)

```
itest_01_bringup.py
itest_02_errorpath.py
itest_08_dialog_recover.py
itest_12_e2e.py
itest_19_mcp_stdio_smoke.py
itest_21_wpf_dialog_guard.py
itest_25_explode_read_e2e.py
itest_30_column_dialog_block.py
itest_32_prompt_capture_log.py
itest_e2e_suite.py
```

**已在 441e890 中删除、不再可用**, 但历史 handoff 29/30/31 仍引用:
- `scripts/itest_44_tpartsaveas_args_probe.py` (P2 TPartSaveAs 参数形态探针草案)
- `scripts/itest_45_tsingleaxisdim_prompt_probe.py` (P2 TSingleAxisDim 提示捕获草案)
- `scripts/itest_46_column_gate_a_inventory.py` (P3 column Gate A inventory 草案)

如需继续 P1/P2 路线, **不要尝试运行这三个文件名**。
正确做法是从 `git show d4b015d:scripts/itest_44_tpartsaveas_args_probe.py` 之类
取出历史版本作参考, 然后**重新写更窄的探针**, 入库前先离线 compileall 通过,
真机运行前先确认 `itest_01_bringup.py` + `itest_19_mcp_stdio_smoke.py` 全绿。

---

## 3. P0 已完成的命名漂移修复 (本次)

### tests/test_tangent_lisp_gen.py
- `test_axis_grid_injects_spacings_and_base` →
  `test_axis_lines_injects_spacings_and_base`
  (函数体本来就只调用 `axis_lines`, 仅历史命名残留。)
- `test_axis_grid_empty_spacings_rejected` 拆为两个:
  - `test_axis_lines_empty_spacings_rejected`: 走 axis_lines 参数校验层。
  - `test_removed_axis_grid_subcommand_rejected`: 显式覆盖
    `axis_grid / column / export_t3` 三个被移除子命令均抛 unknown-subcommand
    `ParamError`, 防止意外回归。

修复范围**仅限测试函数名 + 注释 + 一条新增回归**, 不触碰 _prelude.lsp /
file_ipc.py / mcp_dispatch.lsp / dialog_automation.py / 编码与 IPC 基础设施。

---

## 4. 离线验证基线 (本次, 修复前后)

修复前:
- `uv run pytest -q` → 149 passed
- `uv run python -m compileall -q src scripts tests` → pass
- `git diff --check` → pass
- `uv run python scripts/itest_19_mcp_stdio_smoke.py` → 9 tools, axis_lines dry-run PASS

修复后:
- `uv run pytest -q` → 150 passed (+1, 来自上面拆分)
- 其它三项与修复前一致 (修复后再次执行确认)。

---

## 5. 真机状态 (本次会话)

- `Get-Process -Name acad` 在 cmd.exe / powershell 下均无输出。
- 没有可见 AutoCAD/T20 进程, 因此本次会话**没有**做任何真机探针。
- P1 (TPartSaveAs / TSingleAxisDim / window 窗模式人工验证)、P2 (column / TRectAxis /
  TSaveAs / selection injection inventory)、P3 (低置信子命令收敛) 的真机进展为零,
  仍以 Handoff 28/29/30/31 的最后一次真机记录为准。

---

## 6. 下一接手者建议

1. 从 `itest_01_bringup.py` 开始, 确认 AutoCAD/T20 真机可见。
2. 然后 `itest_19_mcp_stdio_smoke.py` 确认 MCP stdio + dispatcher 全绿。
3. 再按本仓库 README "P1 路线" 节奏, 重写 (而非恢复) TPartSaveAs / TSingleAxisDim
   两个窄探针; 入库时仅作为 probe, 不要直接接入 `tangent.py` SUBCOMMANDS。
4. 每个真机探针完成后写一份 `docs/handoff/33_*.md`, 模板与 Handoff 28 对齐:
   命令 / 输入序列 / 窗口状态 / entity delta / last entity type / 清理结果 / 是否停止。
5. 严禁向任何 #32770 / WPF 模态框发 WM_CLOSE; 恢复只用 ESC + 命令取消 + 已验证白名单按钮。
6. 不要把 vl-cmdf 返回值 / clean exit / selection consumed / 0 entity 当成功;
   成功判据始终是 entity count delta + 预期 TCH_* 类型 (导出类则要求真实输出文件 + 环境干净)。

---

## 7. 不在本次 P0 范围内 (留给后续 handoff)

- 是否给低置信子命令 `door` / `window` / `elevation` / `arrow` / `drawing_name`
  收敛 warning 文案。
- 是否新增 P1 探针。
- README / docs/T20_COMMANDS.md 已与代码事实一致, 本次不动。
