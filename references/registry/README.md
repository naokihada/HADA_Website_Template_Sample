# External reference registry

Register external repositories and sources for readonly reference during development.

## Layout

| Path | Role |
|---|---|
| `registry/` | Reference metadata (YAML) |
| `cache/` | Readonly cached copies from external sources |
| `reports/` | Analysis reports about references |

## Rules

- Treat registered references as **readonly** unless a task explicitly requires import.
- Do not commit secrets, credentials, or private local paths.
- Separate External Content **Source** from **Reference** metadata.

Example registry format: `registry/references.example.yaml`

See `AGENTS.md` Reference Rules.
