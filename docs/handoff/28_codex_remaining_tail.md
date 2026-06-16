# Handoff 28 — remaining tail candidates

Executor: Codex
Date: 2026-06-15
Environment: real T20 V10 / AutoCAD 2024, `Drawing1.dwg`, `mcp_dispatch.lsp` bootstrapped by bringup.

## Result

Two remaining simple tail candidates were promoted and E2E verified:

| Subcommand | Command | Sequence | Entity |
|---|---|---|---|
| `line_pattern` | `TLinePattern` | start point -> end point -> Enter -> Enter | `TCH_PATH_ARRAY` |
| `wheelchair_diameter` | `TWheelchairDaim` | center point -> radius/direction point -> Enter | `TCH_RADIUSDIM` |

Notes:

- `TLinePattern` creates the entity after the first Enter but leaves `CMDACTIVE=1`; a second empty Enter exits cleanly.
- `TWheelchairDaim` is the official command spelling. The two-point sequence exits cleanly and `entlast` is `TCH_RADIUSDIM`; total entity delta was 2 in the test scene.

## Rejected / not promoted

| Command | Result | Disposition |
|---|---|---|
| `TBlkMask1` | two-corner sequence returned cleanly but delta=0 | Do not wrap. |
| `WIPEOUT` | four points + `C` generated native `WIPEOUT` | Not a TCH smart entity; keep out of `tangent` for now. |

## Verification

```powershell
uv run pytest -q tests/test_tangent_lisp_gen.py
# 146 passed
```

The `146 passed` count above is the scoped tangent generator test file at the time of Handoff 28. The later full-suite check below is the repository-wide count after the follow-up tests were added.

Real-machine E2E via generated LISP:

```text
line_pattern: ok=True delta=1 last=TCH_PATH_ARRAY expected=TCH_PATH_ARRAY PASS=True
wheelchair_diameter: ok=True delta=2 last=TCH_RADIUSDIM expected=TCH_RADIUSDIM PASS=True
final_count 0
```

## P0/P1 closeout follow-up

2026-06-16 Codex follow-up:

- Reviewed the current diff and Handoff 28 state directly, with OpenCode/ds used only for read-only consistency and review drafts.
- Accepted one low-risk ds-suggested coverage improvement after manual review: explicit `wheelchair_diameter` edge point coverage.
- Clarified the public docs/tool help that `wheelchair_diameter` defaults `edge` to 1500mm to the right of center when omitted.
- Re-ran offline and MCP protocol checks:

```powershell
uv run pytest -q
# 166 passed

uv run python -m compileall -q src scripts tests
# pass

git diff --check
# pass; CRLF warnings only

uv run python scripts/itest_19_mcp_stdio_smoke.py
# 9 tools visible; tangent.axis_lines dry-run PASS
```
