# Handoff 26 - Codex + Claude Code dispatch invariant hardening

Executor: Codex lead, with Claude Code read-only review
Date: 2026-06-14
Environment: local repo only; no AutoCAD/T20 execute path

## Conclusion

Added offline regression coverage for the `tangent` dispatch and safety-gating contract.

This batch keeps the recent no-dialog/no-crash rules pinned down without touching LISP templates, `_prelude.lsp`, IPC, dispatcher code, or any real-machine command path.

## Claude Code Participation

Claude Code 2.1.177 was invoked read-only with explicit instructions not to edit files and not to run AutoCAD/T20 E2E scripts. It recommended the dispatch invariant test increment as the safest next step because it is fully offline and protects the `LOW_CONFIDENCE_*` and `EXECUTE_DISABLED_*` safety maps from drift.

No files were modified by Claude Code directly.

## Changes

- `tests/test_tangent_lisp_gen.py`
  - Imported `LOW_CONFIDENCE_SUBCOMMANDS`, `LOW_CONFIDENCE_WARNINGS`, and `EXECUTE_DISABLED_SUBCOMMANDS`.
  - Added `TestDispatchInvariants`.
  - Asserted warning/disabled maps only reference known `SUBCOMMANDS`.
  - Asserted warning keys match `LOW_CONFIDENCE_SUBCOMMANDS`.
  - Asserted low-confidence and execute-disabled sets do not overlap.
  - Asserted execute-disabled subcommands still generate balanced dry-run LISP, proving execute gating remains in the MCP wrapper rather than in `generate_lisp`.
- `README.md`
  - Added this handoff to the document index.
  - Updated the integration script range from `itest_01..37` to `itest_01..41`.

## Verification

```powershell
uv run pytest -q tests/test_tangent_lisp_gen.py
# 138 passed in 0.26s

uv run pytest -q
# 157 passed in 1.02s

uv run python -m compileall -q tests
# PASS

uv run python -m compileall -q src scripts tests
# PASS

git diff --check
# PASS; only Git reported the existing LF->CRLF working-copy warning

uv run python -X utf8 scripts/itest_19_mcp_stdio_smoke.py
# tools include tangent; tangent.axis_lines dry-run PASS
```

## Safety Boundary

Did not run `execute=True`.
Did not run real-machine AutoCAD/T20 E2E scripts.
Did not touch `_prelude.lsp`, `file_ipc.py`, `mcp_dispatch.lsp`, `dialog_automation.py`, or LISP templates.

## Next

1. Continue with stable single-point or simple point-sequence command candidates only after prompt capture confirms no dialog and no object-selection step.
2. Reconcile README / `docs/T20_COMMANDS.md` todo/status text for Handoffs 22-25 if a doc-only cleanup pass is desired.
3. Keep `axis_grid`, `export_t3`, and `column` execute-disabled until there is a dedicated UI-automation plan and fresh real-machine evidence.
