# HADA Website Operations Framework — Sample (v0.1.0)

Working example of the v0.1.0 framework. This repository contains a verified fictional
sample site built from `HADA_Website_Template_Dev`.

AI Agent対応Webサイト運用フレームワーク v0.1.0 のサンプル実装リポジトリ。

---

## What this demonstrates

| Feature | Location |
|---|---|
| Japanese Content Master | `content/jp/` |
| English derived locale | `content/en/` |
| Site-wide term dictionary | `config/term_dictionary.yaml` |
| jp → en translation (mock provider) | `tools/core/build_site.py` |
| Markdown → HTML | `site/jp/`, `site/en/` |
| Publication Root | `site/` |

Fictional sample data: **Sample Tea Co.** / **Hanako Sato** (佐藤花子).

## Quick start

Requires **Python 3.10+**.

```text
pip install -r tools/core/requirements.txt
python tools/core/validate_framework.py --root .
python tools/core/build_site.py --root .
python tests/test_validate_framework.py
python tests/test_translation.py
```

## Repository roles

| Repo | Role |
|---|---|
| `HADA_Website_Template_Dev` | Development and verification |
| `HADA_Website_Template_Sample` | This repo — verified v0.1.0 example |
| `HADA_Website_Template` | Clean public template (no sample content) |

See `AGENTS.md` for the canonical agent contract.

## Disclaimer

See [DISCLAIMER.md](DISCLAIMER.md).
