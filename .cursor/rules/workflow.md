# Workflow rules (Cursor adapter)

Canonical source: `AGENTS.md` Task Lifecycle and Core Actions.

## Standard flow

Task → Validate → Analyze → Plan → Approval? → Implement → Test → Scope Check
→ Security Check → Diff Review → Release Candidate → Human Approval → Release

## Modes

NEW | RECOVERY | MIGRATION | MAINTENANCE — state at task start.

## Actions

CREATE | IMPORT | UPDATE | SYNC | VERIFY | TEST | RELEASE | ARCHIVE

## Cursor session

- Track work in `Cursor/tasks/CURRENT.md`
- Record tests in `Cursor/reports/TEST.md`
- Record security review in `Cursor/reports/SECURITY.md`
- Record release in `Cursor/reports/RELEASE.md`

Stop and report BLOCKED if diff contains secrets, unexpected deletions, or unrelated changes.
