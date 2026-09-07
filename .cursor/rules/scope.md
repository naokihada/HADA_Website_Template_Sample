# Scope rules (Cursor adapter)

Canonical source: `AGENTS.md` Scope Rules and Task Lifecycle.

## Enforce

- Small, intentional diffs only
- No scope expansion without explicit user approval
- No unrelated refactors
- No line-ending or whitespace-only churn

## Forbidden without explicit request

- Recursive re-analysis of existing 17 site repositories
- Traversal of large legacy trees (e.g. gallery album directories)
- Full-file reads of large HTML/image/generated assets
- Production deployment or FTP upload
- Creating plugin directories without a written specification

## Phase awareness

Foundation phase: scaffolding and contracts only — no capability plugin implementations.

## Existing libraries

Follow `AGENTS.md` Existing Library Rule — do not custom-implement YAML/JSON/HTTP/XML/etc.
when a suitable library exists; declare dependencies first.
