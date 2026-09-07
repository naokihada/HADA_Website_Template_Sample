# AGENTS.md — HADA Website Operations Framework

Canonical Agent Contract for this repository. Any agent (Cursor, CLI, CI, or other)
must follow these rules. Cursor-specific settings live in `.cursor/rules/` as an adapter;
they must not contradict this document.

---

## Project Identity

| Item | Value |
|---|---|
| Name | HADA Website Operations Framework |
| Development repo | `HADA_Website_Template_Dev` |
| Release repo | `HADA_Website_Template` |
| Sample repo | `HADA_Website_Template_Sample` |
| Purpose | Agent-operable website creation, recovery, migration, maintenance, testing, and release |

Relationship: **Development → Release → Sample**. Implement and validate in Dev; extract
stable engine to Release; demonstrate usage in Sample.

---

## Architecture

### Agent independence

- `AGENTS.md` is the canonical contract.
- `.cursor/rules/` is a Cursor adapter only.
- Deterministic work belongs in `tools/`. Semantic work may use AI.
- Generated artifacts must be rebuildable from sources and configuration.

### Content pipeline

```text
Source → Source Adapter → Content Model / Content Master
    → Processing → Destination Adapter → Published Site
```

- **Content Master** holds authoritative editable content.
- **Generated artifacts** (static cache, build output, indexes) are not source of truth.

### External content

- External Content **Source** and **Reference** are separate concepts.
- `references/` stores readonly external reference metadata and cached read-only copies.
- WordPress.com is an External Content Source (adapter: `wordpress-com`), not merged with
  self-hosted WordPress (adapter: `wordpress`).

### Capabilities (plugins)

Plugins are capabilities with a defined specification. Do not use `tools/plugins/` as an
idea dump. A plugin directory exists only when it has an implementation spec and
`manifest.yaml`.

Planned capability names (not yet implemented in Foundation phase):

| Plugin | Role |
|---|---|
| `wordpress-com` | External WordPress.com source adapter |
| `wordpress` | Self-hosted WordPress adapter |
| `rss` | Generic RSS capability (FULL / PARTIAL / NO_CONTENT) |
| `static-cache` | Generated static cache (not source of truth) |
| `pwa` | PWA capability (separate from static cache) |
| `cron` | Scheduler / execution (cPanel Cron supported; no site logic inside cron) |
| `n8n` | Orchestrator (not the core site logic engine) |
| `ftp` | Deployment to Publication Root only |

### Publication Root

Default publication root: `site/`

Only configured Publication Root content is deployed to the web server document root.
Never deploy `Cursor/`, `content/`, `tools/`, `references/`, `environments/`, `docs/`,
or `config/` unless explicitly instructed for a non-production purpose.

---

## Directory Responsibilities

| Path | Role |
|---|---|
| `AGENTS.md` | Canonical agent contract |
| `.cursor/rules/` | Cursor adapter rules |
| `Cursor/` | Agent workspace: tasks, reports, logs, state (not published) |
| `content/` | Content Master by locale (`en/`, `jp/`) |
| `site/` | Publication Root — deployable web output |
| `references/` | External reference registry, cache, reports |
| `environments/` | Environment definitions (LOCAL / STAGING / PRODUCTION) |
| `tools/core/` | Deterministic framework tools |
| `tools/plugins/` | Installed capability plugins (spec + manifest required) |
| `tests/` | Automated and manual test definitions |
| `docs/` | Human-facing documentation |
| `config/` | Project and site configuration (examples committed; secrets excluded) |

---

## Core Principles

1. Agent independent — no Cursor-only assumptions in core design.
2. Small, intentional diff — minimal scope per task.
3. Scope control — stay within the requested phase and files.
4. Human approval for production — never release or deploy to production implicitly.
5. No guessing — report unknowns; do not invent requirements or paths.
6. Deterministic processing should be code — scripts, validators, linters in `tools/`.
7. Semantic processing may use AI — analysis, planning, content drafting with review.
8. Generated artifacts should be rebuildable — document inputs and regeneration steps.
9. Secrets never enter Git — use local-only config and environment-specific secrets.
10. Production must never be modified implicitly — explicit approval and target required.

### Existing Library Rule

When a standard, proven library can fulfill a requirement safely, do not reimplement the
same capability from scratch.

Applies especially to: YAML, JSON, HTTP, XML, archives, Markdown, HTML, and similar
general-purpose parsing or protocol handling.

For Python tools:

1. Check libraries available in the current environment.
2. Check dependencies already declared in the project.
3. Use an appropriate existing library when suitable.
4. If a new dependency is needed, declare it before implementation (e.g. `tools/core/requirements.txt`).
5. Replacing a library with a custom implementation requires a reported reason and approval.

**Do not implement a custom substitute merely because a library is not yet installed.**
Install and declare the dependency instead.

Standard-library-only solutions remain acceptable for genuinely simple processing. When
unsure, ask before implementing a custom parser or client.

---

## Project Modes

| Mode | Use when |
|---|---|
| `NEW` | Creating a new site from framework templates |
| `RECOVERY` | Restoring or salvaging an existing site |
| `MIGRATION` | Moving content or stack between systems |
| `MAINTENANCE` | Ongoing updates, fixes, and verification |

State the active mode at the start of significant work.

---

## Core Actions

| Action | Meaning |
|---|---|
| `CREATE` | Produce new artifacts or site structure |
| `IMPORT` | Bring external content or reference material into the framework |
| `UPDATE` | Change existing source or configuration |
| `SYNC` | Align derived artifacts with Content Master or external sources |
| `VERIFY` | Check correctness without mutating production |
| `TEST` | Run defined tests and record results |
| `RELEASE` | Prepare or publish a release candidate to Release repo |
| `ARCHIVE` | Freeze or preserve a site snapshot for long-term storage |

---

## Task Lifecycle

Standard workflow:

```text
Task → Validate → Analyze → Plan → Approval?
  → Implement → Test → Scope Check → Security Check → Diff Review
  → Release Candidate → Human Approval → Release
```

Track active work in `Cursor/tasks/CURRENT.md`. Backlog in `BACKLOG.md`. Completed
items move through `TODO.md` or changelog as appropriate.

Before `Implement`:

- Confirm scope, mode, and target paths.
- Identify Content Master vs generated files affected.

Before `Release`:

- All required tests and checks documented in `Cursor/reports/`.
- Human approval obtained for production-impacting changes.

---

## Scope Rules

- Do not expand scope beyond the current phase or explicit user request.
- Do not refactor unrelated files.
- Do not read or modify external site repositories unless the task requires it.
- Do not traverse large legacy directories (e.g. gallery album trees) without explicit need.
- Prefer updating Content Master over editing generated files in `site/` directly.
- Line-ending-only or whitespace-only diffs are unacceptable.

---

## Git Rules

- Commit only intentional, reviewed changes.
- One logical change per commit when possible.
- Never commit secrets, credentials, private local paths, or production tokens.
- Never force-push to `main` without explicit human instruction.
- Do not amend pushed commits unless explicitly requested.
- Foundation and feature work stay on Dev until extracted to Release.

---

## Plugin Rules

### Lifecycle states

`SPECIFIED` → `INSTALLING` → `INSTALLED` → `ENABLED` → (`DISABLED` | `UNINSTALLING`) → `UNINSTALLED` | `FAILED`

### Install procedure

```text
Preflight → Backup → Apply → Verify → Commit
```

- **Disable** and **Uninstall** are different operations.
- Plugin logs go to shared `Cursor/logs/`, `Cursor/state/`, and `Cursor/reports/` — not inside
  the plugin directory.
- Each plugin requires `manifest.yaml` when implemented.
- Do not create plugin directories without a written specification.

---

## Reference Rules

- `references/registry/` lists external repositories and sources (readonly by default).
- `references/cache/` holds readonly cached copies from external sources.
- `references/reports/` holds reference-related analysis output.
- Register references in `references/registry/references.example.yaml` pattern; use
  project-specific registry files as needed without committing private paths or secrets.

---

## Content Master Rules

- Authoritative content lives under `content/{locale}/`.
- Locale directories default to `en/` and `jp/`.
- Content Master changes flow through processing into `site/`.
- Do not treat `site/index.html` or other generated cache files as editable source unless
  the task explicitly targets generated output only.

---

## Generated File Rules

- Static cache, build artifacts, and pre-rendered HTML in `site/` are generated unless
  marked otherwise in task documentation.
- Regeneration steps must be documented or scripted in `tools/`.
- Deleting and rebuilding generated output is preferred over manual drift repair.

---

## Testing Rules

- Tests live under `tests/` and may be invoked from `tools/core/`.
- Record results in `Cursor/reports/TEST.md` or linked report files.
- `VERIFY` checks may be read-only; `TEST` may mutate fixtures in non-production paths only.
- Security checks documented in `Cursor/reports/SECURITY.md` before release candidates.

---

## Security Rules

Never commit:

- Passwords, API keys, tokens, or connection strings
- Private local filesystem paths tied to individuals (use examples)
- Production secrets or `.env` with real values
- Private logs containing sensitive data

Treat legacy imported content as untrusted until scanned. Do not execute untrusted PHP,
shell, or binary from reference or recovery imports without explicit review.

PWA and static-cache plugins must not cache authentication, private, or admin content
without explicit configuration and human approval.

---

## Deployment Rules

- Deployment target is **Publication Root only** (`site/` by default).
- FTP and other deployment adapters deploy publication content, not the full repository.
- STAGING and PRODUCTION require named environment config and human approval.
- LOCAL development uses `environments/` definitions; do not assume production parity.

---

## Human Approval

Required before:

- Production deployment or FTP upload
- Release extraction to `HADA_Website_Template`
- Destructive operations on Content Master or external references
- Enabling plugins that mutate live external systems (WordPress.com, cron, n8n)

Record approval context in `Cursor/reports/RELEASE.md` or task notes.

---

## Logging

- Operational logs: `Cursor/logs/`
- Persistent state: `Cursor/state/`
- Human-readable reports: `Cursor/reports/`
- Inventories and audits: `Cursor/inventory/`
- Change history: `Cursor/changelog/`

Use structured, factual entries. Separate **fact**, **unverified**, and **inference**.

---

## Error Handling

On failure:

1. Stop the current automated step.
2. Record the error in `Cursor/logs/` or the active report.
3. Do not commit partial or broken foundation changes.
4. Do not push if diff contains secrets, unexpected deletions, or unrelated changes.
5. Report `BLOCKED` or `NEEDS_REVIEW` with concrete next steps.

---

## Plugin Installation / Uninstallation

**Install:** Preflight (manifest, dependencies, scope) → Backup (state + affected files) →
Apply → Verify (tests + diff review) → Commit.

**Disable:** Stop scheduling and external side effects; leave files installed.

**Uninstall:** Disable first → remove plugin artifacts → Verify → Commit.

Failed installs enter `FAILED` state; do not leave half-applied production config.

---

## Agent Communication

Reports must distinguish:

| Label | Meaning |
|---|---|
| Fact | Directly observed or verified |
| Unverified | Not yet confirmed |
| Inference | Reasoned but not confirmed — use sparingly |

Prefer machine-readable structure in reports where practical (YAML front matter, tables,
checklists) for future automation.

Do not paste secrets or full contents of large files in reports.

---

## Completion Criteria

A task is complete when:

- Requested scope is implemented within declared mode and phase.
- Tests and checks specified for the task have passed or are explicitly deferred with reason.
- Diff is limited to intended files; no secrets present.
- `Cursor/tasks/CURRENT.md` and relevant reports are updated.
- Human approval obtained if required.
- Git status is clean or commit message accurately describes remaining intentional state.

Foundation phase complete when all Foundation paths exist, `AGENTS.md` and README describe
the framework, and configuration examples are present without live secrets.
