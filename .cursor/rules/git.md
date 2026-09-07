# Git rules (Cursor adapter)

Canonical source: `AGENTS.md` Git Rules.

## Commit

- Intentional changes only; one logical unit per commit when practical
- Verify diff before commit — no secrets, no unrelated files
- Do not commit `config/local.yaml`, `.env`, or cache contents

## Push

- Do not force-push `main` without explicit instruction
- Do not push if suspicious deletions or unexpected large diffs appear

## Branches

- Foundation and feature work stay in Dev until release extraction
- Release repo updated only through approved RELEASE workflow

## Stop conditions

If unrelated changes, user-owned unexpected edits, or secrets appear — stop commit/push
and report NEEDS_REVIEW.
