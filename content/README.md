# Content Master

Authoritative editable content by locale. Not deployed directly — flows to `site/` via
processing.

| Path | Locale |
|---|---|
| `en/` | English |
| `jp/` | Japanese |

Counterparts use the same basename across locales (e.g. `en/about.md` ↔ `jp/about.md`).

Japanese (`jp/`) is the authoritative Content Master locale. English (`en/`) is derived via
`tools/core/build_site.py` using the single site-wide term dictionary
(`config/term_dictionary.yaml`).

See `AGENTS.md` Content Master Rules.
