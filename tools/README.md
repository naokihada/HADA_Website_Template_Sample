# Framework tools

| Path | Role |
|---|---|
| `core/` | Deterministic framework scripts and validators |
| `plugins/` | Capability plugins (spec + JSON/TOML manifest when implemented) |

Do not add plugin directories without a written specification.

## Core validator

Script: `tools/core/validate_framework.py`

Requirements:

- Python 3.12+
- Project dependencies (`pip install -r tools/core/requirements.txt`)

Run from repository root:

```text
python tools/core/validate_framework.py --root .
```

The validator reads project TOML and JSON configuration with the standard library.

## Build site (translation + Markdown to HTML)

Requires `pip install -r tools/core/requirements.txt` (markdown and image/PDF tools).

Uses Japanese Content Master (`content/jp/`) and the single term dictionary
(`config/term_dictionary.json`). Dictionary entries override automatic translation.

```text
python tools/core/build_site.py --root .
```

## Template upgrade (v0.1.2+)

Upgrade framework files from a GitHub stable Release while preserving user content:

```text
python tools/core/upgrade_from_release.py --root .
```

See `docs/UPGRADE.md` for options, ownership rules, and exit codes.
