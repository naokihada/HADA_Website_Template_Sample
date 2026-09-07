# Reporting rules (Cursor adapter)

Canonical source: `AGENTS.md` Agent Communication and Logging.

## Labels

| Label | Use |
|---|---|
| Fact | Directly observed |
| Unverified | Not yet confirmed |
| Inference | Reasoned, not confirmed — use sparingly |

## Where to write

- Session summary: `Cursor/reports/CHATGPT.md`
- Analysis: `Cursor/reports/ANALYSIS.md`
- Tests: `Cursor/reports/TEST.md`
- Security: `Cursor/reports/SECURITY.md`
- Release: `Cursor/reports/RELEASE.md`
- Operational detail: `Cursor/logs/`

## Do not

- Paste secrets or large file contents in reports
- Mix fact and speculation without labeling
- Claim "no issues" for areas not inspected

Prefer tables and checklists for future machine-readable parsing.
