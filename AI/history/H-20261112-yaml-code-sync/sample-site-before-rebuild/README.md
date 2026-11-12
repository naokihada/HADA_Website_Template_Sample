# Publication Root

This directory is the **configured Publication Root** for this framework project.

## Deploy rule

Only content under this Publication Root (`site/`) is intended for deployment to the web
server document root. All other repository paths are **not** public web content unless
explicitly stated for a non-production purpose.

Do **not** deploy or expose:

- `Cursor/`
- `content/`
- `tools/`
- `references/`
- `environments/`
- `docs/`
- `config/`
- `.cursor/`

## Structure

| Path | Role |
|---|---|
| `en/` | English published output |
| `jp/` | Japanese published output |
| `assets/` | Shared static assets (images, css, js) |
| `index.html` | Language selection entry (links to `en/`, `jp/`) |

## Generated artifacts

Files here (including `index.html`) are **generated / published output**, not Content
Master. Edit authoritative content under `content/` and regenerate into `site/` using
framework tools when available.

See `AGENTS.md` for Content Master vs generated file rules.
