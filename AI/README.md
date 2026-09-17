# AI Workspace

Agent-neutral workspace for tasks, handoffs, ReSPEC checkpoints, reports, history, and scoped recovery evidence.

## Layout

| Path | Purpose |
|---|---|
| `inbox/` | Incoming Handoff Packets, grouped by `handoff_id` |
| `outbox/` | Execution reports and postflight ReSPEC results, grouped by `handoff_id` |
| `history/` | Retained preflight snapshots, Prompt Bundles, WIP checkpoints, backups, and migrated legacy reports |
| `tasks/` | Current target-project tasks and plans |
| `reports/` | Current human-readable validation and release reports |

`AI/` is an agent-neutral operation workspace. It is not the Content Master, Publication Root, or current implementation specification.

## Handoff rules

- Do not delete completed Handoff evidence by default.
- Use a new `handoff_id` for a retry; do not overwrite an earlier attempt.
- Save `SPEC_BEFORE.md` and `ReSPEC_BEFORE.md` before implementation.
- Save `ReSPEC_AFTER.md`, `ReSPEC_COMPARISON_AFTER.md`, and `EXECUTION_REPORT.md` after implementation.
- Preserve scoped pre-change files and hashes when recovery without Git is required.
- Prompt Bundles are snapshots for the Handoff and are not permanent global instructions.
