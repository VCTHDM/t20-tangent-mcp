# Handoff 30 - P3 UI and selection design gate

Executor: Codex
Date: 2026-06-16
Scope: design-only packet for UI automation and selection-object injection routes.

No real-machine AutoCAD/T20 execution was performed in this pass. OpenCode/ds was attempted for read-only material gathering, but the call timed out before returning usable output; this document is based on direct repository review by the main executor.

## Baseline

P0/P1 and the P2 drafts from Handoff 28/29 stay unchanged:

- `line_pattern` and `wheelchair_diameter` remain the last promoted simple tail commands.
- `scripts/itest_44_tpartsaveas_args_probe.py` and `scripts/itest_45_tsingleaxisdim_prompt_probe.py` are P2 probes, not wrappers.
- The Step 44 live attempt stopped before dispatch because no visible AutoCAD/T20 window was available.
- `axis_grid`, `column`, and `export_t3` remain execute-disabled until fresh real-machine evidence proves a safe route.

This handoff is only a gate and route map for P3. It does not authorize broad UI clicking, `WM_CLOSE`, infrastructure edits, or wrapper promotion.

## Evidence map

| Route | Current evidence | Current state |
|---|---|---|
| Native `#32770` button-only dialog | `dialog_automation.py` has a whitelist + exact button text + `BM_CLICK` primitive, validated only for `TEXPLODE` | Reusable only for exact-title, exact-button, low-risk dialogs |
| `column` / `TGColumn` | Handoff 13 records 0 entities, `CMDACTIVE=1`, and a `#32770` panel; placement needs drawing-area input after the panel | Keep dry-run; UI route needs a separate probe |
| `axis_grid` / `TRectAxis` | Existing recon found a `#32770` parameter dialog with low-semantic-value controls | Keep dry-run; do not click or fill until controls are mapped |
| `export_t3` / `TSaveAs` | WPF/export dialog ignores `FILEDIA=0`; modal detection relies on owner-disabled signal, not class name alone | Prefer `TPARTSAVEAS` P2 route first; WPF automation is last resort |
| `window` / `TOpening` | Type follows the non-modal door/window panel; COM property/method switching was ruled out | Keep manual window-mode precondition; WPF panel automation is separate |
| Selection-object commands | Several commands reject `ssget`, scripted points, or selection names; 0 entity is common | Selection consumption is not success; require entity delta + expected type |

## P3 gates

### Gate A: dialog inventory only

Allowed first step:

1. Start from a clean AutoCAD/T20 session with a disposable `.dwg`.
2. Run a command-specific inventory probe that:
   - confirms command registration with `getcname`;
   - records baseline windows and entity count;
   - launches exactly one target command;
   - records new window class, title, owner-disabled state, enabled state, and child controls;
   - sends ESC only;
   - verifies `CMDACTIVE=0`, `CMDDIA=1`, `FILEDIA=1`, `OSMODE=0`, and no entity residue.

Disallowed in Gate A:

- Filling text boxes.
- Clicking buttons other than ESC-style cancellation.
- Drawing-area clicks.
- Adding anything to `dialog_automation.py`.
- Treating a clean exit as success.

Promotion out of Gate A requires a written control inventory with stable title/class/button/control identity and a clean recovery transcript.

### Gate B: whitelist button drive

Allowed only after Gate A succeeds and only for native `#32770` dialogs where the action is button-only.

Required proof before code changes:

- Exact dialog title.
- Exact safe button sequence.
- A forbidden-button list for destructive alternatives.
- Proof that the sequence does not apply to current drawing contents broadly.
- Proof that closing the dialog returns control to the command line or consumes the already prepared selection.

This gate is not enough for `column` because column still needs a drawing-area placement step after the panel. It is probably not enough for `axis_grid` unless the dialog itself creates the grid without a drawing click.

### Gate C: WPF/non-modal panel plan

This gate covers `window` panel automation and any WPF export route.

Required plan before touching a live session:

- Target discovery rule that distinguishes modal export dialogs from non-modal T20 panels.
- Control identification rule that does not depend only on `HwndWrapper` class names.
- A no-op inventory run showing labels, automation IDs if available, child hierarchy, and focus behavior.
- Recovery rule using ESC or explicit cancel button only; never `WM_CLOSE`.
- A rollback assertion: no new entity, no output file, and environment restored after a failed probe.

`window` remains manual-first. Even if a WPF plan exists, do not remove the manual precondition until a full E2E proves `TCH_OPENING` type, `Width`, `Height`, and `SillHeight` readback in window mode.

### Gate D: selection-object injection

Allowed experiments must be isolated scripts. They may build a tiny controlled scene, then try one injection method at a time.

Candidate methods to evaluate separately:

- `ssget "_X"` or filtered selection passed inside the same `vl-cmdf` call.
- `sssetfirst` before command start.
- command-line point picks against known geometry.
- `SendCommand` only after a design note explains why file IPC cannot represent the input sequence.

Required success evidence:

- entity count delta;
- expected `TCH_*` entity type or output file;
- command inactive at the end;
- environment restored;
- cleanup removes probe geometry;
- no hidden modal/panel residue.

Explicit non-success:

- selection set exists;
- prompt text changes;
- command exits cleanly;
- `vl-cmdf` returns truthy;
- entity count remains unchanged.

Stop after two no-op or zero-entity attempts for the same command/input family.

## Command-specific routing

### `column`

Current best route is not button-only automation. The hard part is "panel opened, then place in drawing area." Any probe must first answer:

- Does confirming/dismissing the `#32770` standard-column panel leave the command waiting for a drawing point?
- Can a later drawing-area coordinate be consumed by `vl-cmdf`, command-line text, or a controlled mouse click?
- Does the result create `TCH_COLUMN` with a true entity delta in a fresh session?

If the first fresh attempt again gives 0 entity and active command after panel cancellation, stop.

### `axis_grid`

Do not implement a wrapper from the existing dialog inventory. The controls are too low-semantic to infer safely.

Next acceptable probe is inventory-only, unless a human maps each visible field to official axis-grid parameters. A valid promotion still requires actual smart axis-grid entity evidence, not ordinary `LINE` output.

### `export_t3`

Prefer P2 `TPARTSAVEAS` route before WPF automation. A WPF route is justified only if:

- `TPARTSAVEAS` cannot create a file after the Step 44 argument-shape probe;
- the export dialog fields/buttons are stable and uniquely identified;
- output file existence and DWG type can be verified after export.

### `window`

Short-term next step remains manual window-mode E2E from Handoff 29.

WPF panel automation is only worth pursuing after the manual E2E proves that window mode can produce the correct object and `SillHeight` readback. Otherwise there is no known-good state to automate toward.

### object-pick families

Do not group all object-pick commands together. Each command gets one tiny scene and one prompt-capture transcript before any injection attempt. Prior failures show that "has a selection set" often still ends in zero entities.

## Concrete next packets

1. Run P2 Step 44 (`TPARTSAVEAS`) once AutoCAD/T20 is visible.
2. Run P2 Step 45 (`TSingleAxisDim`) once AutoCAD/T20 is visible.
3. Run the manual `window` E2E only after a human switches the panel to window mode.
4. Draft, but do not run, a `P3-Gate-A` inventory script for exactly one target command if P2 remains blocked. Drafted as `scripts/itest_46_column_gate_a_inventory.py` for `TGColumn` / `column`.
5. Hold `dialog_automation.py`, `_prelude.lsp`, `file_ipc.py`, `mcp_dispatch.lsp`, encoding, and IPC infrastructure unchanged until one Gate A inventory gives a strong reason to revisit them.

## Verification for this pass

Design-only handoff. Required verification is limited to repository checks:

- `uv run pytest -q`
- `uv run python -m compileall -q src scripts tests`
- `git diff --check`
- `uv run python scripts/itest_19_mcp_stdio_smoke.py`

## Step 46 draft

2026-06-16 follow-up:

- Added `scripts/itest_46_column_gate_a_inventory.py`.
- The script is intentionally narrow: `TGCOLUMN` registration check, baseline entity/window capture, one command launch, new-window and child-control inventory, ESC-only recovery, entity/environment assertions.
- It does not click buttons, fill fields, send `WM_CLOSE`, use `execute=True`, or edit `dialog_automation.py` / IPC infrastructure.
- It was not run on a live AutoCAD/T20 session in this pass; only Python compilation and offline repository gates are expected here.
