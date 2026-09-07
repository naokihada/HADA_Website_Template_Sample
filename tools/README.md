# Framework tools

| Path | Role |
|---|---|
| `core/` | Deterministic framework scripts and validators |
| `plugins/` | Capability plugins (spec + manifest.yaml when implemented) |

Do not add plugin directories without a written specification.

## Core validator

Script: `tools/core/validate_framework.py`

Requirements:

- Python 3.10+
- PyYAML (`pip install -r tools/core/requirements.txt`)

Run from repository root:

```text
python tools/core/validate_framework.py --root .
```

The validator checks dependencies before running and exits with code `2` if PyYAML is missing.

## Build site (translation + Markdown to HTML)

Requires `pip install -r tools/core/requirements.txt` (PyYAML, markdown).

Uses Japanese Content Master (`content/jp/`) and the single term dictionary
(`config/term_dictionary.yaml`). Dictionary entries override automatic translation.

```text
python tools/core/build_site.py --root .
```
