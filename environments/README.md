# Environments

Environment definitions for LOCAL, STAGING, and PRODUCTION workflows.

## Purpose

- **LOCAL** — developer machine (e.g. XAMPP, test hostnames)
- **STAGING** — pre-production verification
- **PRODUCTION** — live site (human approval required for changes)

Configuration example: `environments.example.yaml`

Local overrides: copy `config/local.example.yaml` to `config/local.yaml` (gitignored).

## Rules

- Never store production secrets in this repository.
- Deployment to STAGING or PRODUCTION requires explicit human approval.
- Only Publication Root (`site/`) content is deployed unless a task states otherwise.

See `AGENTS.md` for deployment and security rules.
