# Handoff 29 - P2/P3 attack plan

> 历史规划：其中 door/window 需要人工预切模式的判断已被 Handoff 39 真机证伪；
> 当前门窗链路以 Handoff 39、README 和 `docs/T20_COMMANDS.md` 为准。

Executor: Codex
Date: 2026-06-16
Scope: P2 material consolidation and P3/P4 risk routing after Handoff 28.

No real-machine AutoCAD/T20 execution was performed in this pass. OpenCode/ds was used only for read-only material gathering; every action item below is based on repository evidence and still needs the main executor to judge any real-machine probe.

## Current baseline

- P0/P1 for Handoff 28 is closed out in `docs/handoff/28_codex_remaining_tail.md`: full pytest, compileall, diff check, and MCP stdio dry-run smoke passed on 2026-06-16.
- `line_pattern` and `wheelchair_diameter` are the last promoted simple tail commands from the current batch.
- `TBlkMask1` and native `WIPEOUT` remain rejected: zero TCH smart-entity evidence.

## P2 route map

### 1. export_t3 alternatives

Authoritative evidence:

- `TSaveAs` / `export_t3` is execute-disabled because it opens a T20 export dialog and ignores `FILEDIA=0`: `docs/T20_COMMANDS.md:16-19`, `docs/T20_COMMANDS.md:77`, `src/t20_mcp/tools/tangent.py:1210-1221`, `src/t20_mcp/lisp_templates/tangent/export_t3.lsp:3-6`.
- `TPartSaveAs` and `TGetXML` already have a minimal probe script: `scripts/itest_17_export_alternatives.py:3`, `scripts/itest_17_export_alternatives.py:103`.
- Current recorded conclusions: `TPartSaveAs` empty input is a no-op with no output; `TGetXML` empty input opens a `#32770` "TGL" export dialog: `docs/T20_COMMANDS.md:124-125`, `docs/handoff/08_gpt_field_test.md:132-136`.
- WPF/modal detection was hardened later: `docs/handoff/09_fable_wpf_guard.md:28-32`, `docs/handoff/09_fable_wpf_guard.md:38-41`, `scripts/itest_21_wpf_dialog_guard.py:6-9`.

Recommended next probe:

1. Use `getcname`/registration confirmation for `TPARTSAVEAS` and `TGETXML` before any command run.
2. Extend `itest_17_export_alternatives.py` or write a sibling probe that tries only `TPARTSAVEAS` argument shapes, one at a time, with ESC-only recovery:
   - output path only;
   - output path plus version-like token;
   - selection set plus output path only if the command prompt proves it wants objects.
3. Do not promote anything unless there is an output file, no modal residue, clean `CMDACTIVE=0`, and no hidden environment leak.

Stop conditions:

- Any modal dialog appears: record window class/title and stop that route.
- Two `TPARTSAVEAS` argument shapes still produce no file/no entity/no prompt clarity: stop; do not guess.
- `TGETXML` remains an export-to-TGL dialog route, not a T3 DWG route, unless new prompt evidence proves otherwise.

### 2. TSingleAxisDim and axis route

Authoritative evidence:

- `axis_lines` is the current safe executable fallback and creates ordinary `LINE`, not smart T20 axis objects: `docs/T20_COMMANDS.md:73`, `docs/T20_COMMANDS.md:167`, `src/t20_mcp/lisp_templates/tangent/axis_lines.lsp:2-4`.
- `TRectAxis` / `axis_grid` is execute-disabled because it opens a `#32770` parameter dialog: `docs/T20_COMMANDS.md:76`, `src/t20_mcp/lisp_templates/tangent/axis_grid.lsp:3-10`.
- The `TRectAxis` dialog was already inspected and has low-value unlabeled controls: `docs/T20_COMMANDS.md:186-191`, `docs/research/2026-06-13_rectaxis_dialog_controls.txt:2-12`, `docs/research/2026-06-13_rectaxis_dialog_controls.txt:26-31`.
- `TSingleAxisDim` has no implementation. It is only a known unknown: `README.md:220`, `docs/T20_COMMANDS.md:191`, `docs/research/2026-06-14_remaining_simple_candidates.md:16`.

Recommended next probe:

1. Probe `TSingleAxisDim` prompt flow first, using the existing prompt-capture style scripts rather than a wrapper.
2. If its first prompt is coordinate-only and it can generate a TCH axis-label entity with an entity delta, then draft a wrapper.
3. If it asks for existing axis objects, try only one controlled selection-injection experiment after building a scene with `axis_lines`; do not conflate a consumed selection with success.

Stop conditions:

- Any `#32770`/WPF dialog.
- Object-pick prompt rejects coordinates/selection twice.
- Result is plain text/LINE only and does not materially improve over `axis_lines`.

### 3. door/window follow-up

Authoritative evidence:

- `door` is partially verified: `TCH_OPENING` plus `Width/Height/DoorSill` readback: `docs/handoff/05_fable_field_test.md:58`, `docs/T20_COMMANDS.md:72`.
- `window` depends on manually switching the T20 door/window panel to window mode: `docs/handoff/16_codex_window_contract.md:13-17`, `src/t20_mcp/tools/tangent.py:425-429`, `src/t20_mcp/lisp_templates/tangent/window.lsp:5-8`.
- COM property/method switching was ruled out: `scripts/itest_16_opening_props_safe.py:24-27`, `scripts/itest_16_opening_props_safe.py:115-130`, `scripts/itest_29_opening_kind_probe.py:7-9`, `scripts/itest_29_opening_kind_probe.py:42-46`.
- `SillHeight` is still window-mode real-machine debt: `src/t20_mcp/lisp_templates/tangent/window.lsp:30-31`, `src/t20_mcp/tools/tangent.py:1187-1189`.

Recommended next probe:

1. Keep the current manual precondition. Do not attempt WPF panel automation in the probe.
2. Manually switch the panel to window mode, then run a narrow `window` E2E that checks:
   - new entity type is `TCH_OPENING`;
   - `Width`/`Height` match requested values;
   - `SillHeight` can be read back and matches requested value;
   - cleanup restores entity count and environment.
3. If readback succeeds, update only documentation and tests/handoff state; do not remove the manual precondition unless WPF automation is later built.

Stop conditions:

- `window` creates a door-mode object after the manual panel switch.
- `SillHeight` cannot be read back or cannot be written.
- Any modal/ping/environment issue appears.

## P3 mechanism routes

### UI automation for `#32770` dialogs

Reusable evidence:

- `dialog_automation.py` has a conservative whitelist-click primitive for known native dialogs: `src/t20_mcp/dialog_automation.py:3-12`, `src/t20_mcp/dialog_automation.py:43-56`.
- `TExplode` proved `BM_CLICK` can drive a known safe button, but the project chose native `EXPLODE` instead: `docs/handoff/10_fable_explode_read.md:13-14`, `docs/handoff/10_fable_explode_read.md:33-39`.
- `column` and `axis_grid` are not the same class of easy button-only dialog. `column` still needs a drawing-area placement step after the panel, and `axis_grid` has low-semantic-value controls: `docs/handoff/13_claude_column_dialog_block.md:44-51`, `docs/T20_COMMANDS.md:186-191`.

Decision gate:

- A UI route is only worth promoting if a probe proves exact control identity, exact safe button path, and post-dialog command consumption.
- The main executor must own all real-machine UI work. ds may only prepare inventories or patch drafts.

### WPF routes

Reusable evidence:

- Modal detection should rely on the owner-disabled signal, not only class name: `docs/handoff/09_fable_wpf_guard.md:14-21`.
- Non-modal WPF panels exist, so class-name matching alone can create false positives: `docs/handoff/09_fable_wpf_guard.md:17-21`.
- `window` WPF panel automation remains a separate design task: `docs/handoff/16_codex_window_contract.md:47-48`.

Decision gate:

- Write a WPF UI automation plan before touching AutoCAD/T20.
- The plan must name target window discovery, control identification, safe recovery, and a no-`WM_CLOSE` rule.

### Selection-object injection

Reusable evidence:

- Preselection can be cleared by command start: `docs/handoff/10_fable_explode_read.md:28`.
- Object-pick commands have repeatedly rejected script points or selection names: `docs/T20_COMMANDS.md:123`, `docs/handoff/21_claude_geom_batch.md:74`, `docs/handoff/22_claude_ramp_arrow.md:75-77`, `docs/handoff/23_claude_roof_batch.md:73-74`, `docs/handoff/25_claude_stair_batch.md:69`.
- `TSWall` is a warning case: selection was found but command ended with zero entity and no dialog: `docs/handoff/15_tswall_recon_stop.md:7-12`.

Decision gate:

- Treat "selection consumed" as insufficient. Success must mean entity delta plus correct `TCH_*` type.
- Explore `sssetfirst`, grip/COM, or `SendCommand` only in isolated scripts with cleanup, and stop after two no-op/zero-entity attempts.

## P4 hard tail

Keep these out of normal wrapper promotion:

- Stair Draw family and wind rose: dialog-first routes recorded in `docs/handoff/27_claude_double_multi_stair.md:39-41`.
- Girder and attached-entity classes: clean no-entity behavior means prerequisite topology is required, not a simple point sequence: `docs/T20_COMMANDS.md:120`.
- Text-edit-dependent commands such as `TLeader`, point/section index, and similar text entry paths: `docs/T20_COMMANDS.md:106`, `docs/T20_COMMANDS.md:110`, `docs/handoff/24_claude_insight_tree.md:34`.
- Object-pick annotation families: see the selection-injection route above.

## Safety rules for the next executor

- Do not edit `_prelude.lsp`, `file_ipc.py`, `mcp_dispatch.lsp`, `dialog_automation.py`, or encoding/IPC infrastructure for these routes without an explicit design review.
- Do not send `WM_CLOSE` to T20/ARX dialogs. ESC-only recovery remains the standard.
- Do not promote on `vl-cmdf` return, clean exit, or zero-entity "success". Require entity delta plus expected type, or a real output file for export.
- Keep `axis_grid`, `export_t3`, and `column` execute-disabled until a dedicated UI automation plan and fresh real-machine evidence exist.

## Next executable packets

1. P2-export packet: `TPARTSAVEAS` argument-shape probe with ESC-only recovery and environment assertions. Drafted as `scripts/itest_44_tpartsaveas_args_probe.py`; live run attempted but stopped at the AutoCAD/T20 precondition (see below).
2. P2-window packet: manual window-mode E2E with `SillHeight` readback.
3. P2-axis packet: prompt-capture-only `TSingleAxisDim` reconnaissance; no wrapper until prompt and entity type are known. Drafted as `scripts/itest_45_tsingleaxisdim_prompt_probe.py`; not yet run on a real machine.
4. P3-design packet: written WPF/#32770/selection-injection design, not a live run. Drafted as `docs/handoff/30_codex_p3_ui_selection_design.md`.

## Live-run attempt

2026-06-16 Codex follow-up:

- Attempted to run `scripts/itest_44_tpartsaveas_args_probe.py`.
- The script failed before any T20 command was dispatched because no visible AutoCAD/T20 window was available:

```text
FAIL: initialize: AutoCAD/T20 window not found (no 'acad.exe' process window). Start AutoCAD + T20 and open a .dwg, or set AUTOCAD_MCP_ACAD_PROCESS.
```

- `scripts/itest_45_tsingleaxisdim_prompt_probe.py` was not run after that, because it has the same live AutoCAD/T20 precondition.
- No real-machine `TPARTSAVEAS` / `TSingleAxisDim` result is established by this attempt. The next executor should start AutoCAD + T20 with a `.dwg`, run bringup if needed, then retry the Step 44/45 probes.
