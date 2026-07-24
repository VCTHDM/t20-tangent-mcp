# Handoff 31 - current package status and next-run checklist

> 历史状态：其中 window 人工模式前置条件已被 Handoff 39 的控件级自动化取代；
> 当前门窗链路以 Handoff 39、README 和 `docs/T20_COMMANDS.md` 为准。

Executor: Codex
Date: 2026-06-16
Scope: current uncommitted package audit after Handoffs 28-30.

This is a status handoff, not a new probe result. No real-machine AutoCAD/T20 script was run in this pass.

## Current package

Tracked files with edits:

- `README.md`
- `docs/T20_COMMANDS.md`
- `src/t20_mcp/tools/tangent.py`
- `tests/test_tangent_lisp_gen.py`

New files in the package:

- `docs/handoff/28_codex_remaining_tail.md`
- `docs/handoff/29_codex_p2_p3_attack_plan.md`
- `docs/handoff/30_codex_p3_ui_selection_design.md`
- `docs/handoff/31_codex_current_package_status.md`
- `scripts/itest_44_tpartsaveas_args_probe.py`
- `scripts/itest_45_tsingleaxisdim_prompt_probe.py`
- `scripts/itest_46_column_gate_a_inventory.py`
- `src/t20_mcp/lisp_templates/tangent/line_pattern.lsp`
- `src/t20_mcp/lisp_templates/tangent/wheelchair_diameter.lsp`

The worktree remains unstaged and uncommitted. The branch is still `main...origin/main [ahead 1]` in the latest local check.

## Current live preflight

2026-06-16 follow-up check:

```powershell
Get-Process -Name acad -ErrorAction SilentlyContinue | Select-Object Id,ProcessName,MainWindowHandle,MainWindowTitle,Path
# no output
```

No visible/running `acad.exe` process was available, so Step 44/45/46 were not run in this pass.

## Closed in this package

P0/P1:

- `line_pattern` and `wheelchair_diameter` are integrated into generator registration, tests, README, T20 command docs, and LISP templates.
- Handoff 28 records the real-machine E2E evidence:
  - `line_pattern`: `TLinePattern`, start point -> end point -> Enter -> Enter, `TCH_PATH_ARRAY`.
  - `wheelchair_diameter`: `TWheelchairDaim`, center point -> edge point -> Enter, `TCH_RADIUSDIM`.
- `TBlkMask1` stays rejected because the tested two-corner sequence exited cleanly with 0 entities.
- Native `WIPEOUT` stays out of `tangent` because it is not a T20 `TCH_*` smart entity.
- Offline and MCP protocol gates have stayed green after every follow-up.

P2/P3 preparation:

- Step 44 `TPARTSAVEAS` argument-shape probe is drafted with ESC-only recovery and environment checks.
- Step 45 `TSingleAxisDim` prompt-flow probe is drafted with LOGFILEMODE capture and cleanup.
- Handoff 29 records that Step 44 was attempted but stopped before dispatch because no visible AutoCAD/T20 window was available.
- Handoff 30 defines P3 Gate A-D boundaries for `#32770`, WPF, and selection-injection routes.
- Step 46 `TGColumn` Gate A inventory probe is drafted and kept inventory-only.

## Not established yet

Do not claim any of these until live evidence exists:

- `TPARTSAVEAS` can create a T3/Tangent output file.
- `TSingleAxisDim` has a safe wrapper sequence.
- `window` can be promoted beyond the current manual window-mode precondition.
- `column`, `axis_grid`, or `export_t3` can be execute-enabled.
- Any UI automation route is approved for broad clicking, text filling, or infrastructure changes.

## Next live run order

Only after AutoCAD/T20 is visible with a disposable `.dwg` and dispatcher health is confirmed:

1. `uv run python scripts/itest_01_bringup.py`
2. `uv run python scripts/itest_19_mcp_stdio_smoke.py`
3. `uv run python scripts/itest_44_tpartsaveas_args_probe.py`
4. `uv run python -X utf8 scripts/itest_45_tsingleaxisdim_prompt_probe.py`
5. Manual: switch the T20 door/window panel to window mode.
6. Run a narrow manual-window-mode E2E for `window` `SillHeight` readback.
7. Only if P2 remains blocked and the session is clean, run `uv run python scripts/itest_46_column_gate_a_inventory.py`.

Stop immediately if:

- bringup or stdio smoke fails;
- `mcp_dispatch.lsp` is not loaded;
- a probe leaves `CMDACTIVE > 0` after ESC/reset;
- a dialog remains after ESC-only recovery;
- entity count changes without a known cleanup path;
- any route produces 0 entities and no output file twice.

## Never in this package

- No `WM_CLOSE` to T20/ARX/WPF dialogs.
- No broad UI clicking.
- No `execute=True` through OpenCode/ds.
- No edits to `_prelude.lsp`, `file_ipc.py`, `mcp_dispatch.lsp`, `dialog_automation.py`, encoding, or IPC infrastructure.
- No promotion from `vl-cmdf` return value, clean exit, selection consumption, or 0-entity behavior.

## Offline verification commands

Current expected gates:

```powershell
uv run python -m py_compile scripts/itest_44_tpartsaveas_args_probe.py scripts/itest_45_tsingleaxisdim_prompt_probe.py scripts/itest_46_column_gate_a_inventory.py
uv run pytest -q
uv run python -m compileall -q src scripts tests
git diff --check
uv run python scripts/itest_19_mcp_stdio_smoke.py
```

Latest local result before this handoff:

- `py_compile`: pass
- `pytest`: `167 passed`
- `compileall`: pass
- `git diff --check`: pass with CRLF warnings only
- stdio smoke: 9 tools visible, `tangent.axis_lines` dry-run PASS
