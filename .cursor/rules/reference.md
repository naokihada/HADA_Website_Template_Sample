# Reference rules (Cursor adapter)

Canonical source: `AGENTS.md` Reference Rules.

## Layout

- `references/registry/` — metadata (YAML)
- `references/cache/` — readonly cached external copies (gitignored contents)
- `references/reports/` — reference analysis output

## Rules

- External references are readonly by default
- Separate External Content Source from Reference registry entry
- WordPress.com registers as external source (`wordpress-com` adapter when implemented)
- Do not commit private paths or credentials in registry files

Example: `references/registry/references.example.yaml`
