# Safety rules (Cursor adapter)

Canonical source: `AGENTS.md` Security Rules and Deployment Rules.

## Never commit

- Passwords, API keys, tokens, FTP credentials
- `config/local.yaml` or other gitignored local secrets
- Production connection strings
- Private individual local paths when sensitive

## Production

- Human approval required before production or staging deployment
- Deploy Publication Root (`site/`) only — never `Cursor/`, `tools/`, `config/`, etc.

## Legacy / recovery content

- Treat imported legacy files as untrusted until scanned
- Do not execute unknown PHP, shell, or binaries from recovery imports

## Cache / PWA (when implemented)

- Do not cache auth, private, or admin content by default
