# HADA Website Operations Framework — Sample (v0.1.0)

Working example of the v0.1.0 framework. This repository contains a verified fictional
sample site built from `HADA_Website_Template_Dev`.

日本語の情報は、このページの下にあります。

**Release template:** [HADA_Website_Template](https://github.com/naokihada/HADA_Website_Template) — reusable public framework template this sample is based on.

This repository is a **complete sample/demo** of the HADA Web Site Operations Framework v0.1.0.
All site content uses **fictional data** (Sample Tea Co. / Hanako Sato). It does **not**
endorse any real company or service.

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

---

# 日本語

## 概要

v0.1.0 フレームワークの動作例です。本リポジトリには、`HADA_Website_Template_Dev` で
検証した架空データによるサンプルサイトが含まれます。

AI Agent対応Webサイト運用フレームワーク v0.1.0 のサンプル実装リポジトリ。

**Release template:** [HADA_Website_Template](https://github.com/naokihada/HADA_Website_Template) — 本サンプルのベースとなる再利用可能な公開 Framework テンプレート。

本リポジトリは HADA Web Site Operations Framework v0.1.0 の **完全なサンプル／デモ** です。
サイト内容はすべて **架空データ**（Sample Tea Co. / 佐藤花子）であり、
**実在の企業・サービスを推薦するものではありません**。

---

## 本サンプルで示す機能

| Feature | Location |
|---|---|
| Japanese Content Master | `content/jp/` |
| English derived locale | `content/en/` |
| Site-wide term dictionary | `config/term_dictionary.yaml` |
| jp → en translation (mock provider) | `tools/core/build_site.py` |
| Markdown → HTML | `site/jp/`, `site/en/` |
| Publication Root | `site/` |

架空サンプルデータ: **Sample Tea Co.** / **Hanako Sato**（佐藤花子）。

---

## クイックスタート

**Python 3.10+** が必要です。

```text
pip install -r tools/core/requirements.txt
python tools/core/validate_framework.py --root .
python tools/core/build_site.py --root .
python tests/test_validate_framework.py
python tests/test_translation.py
```

---

## リポジトリの役割

| Repo | Role |
|---|---|
| `HADA_Website_Template_Dev` | Development and verification |
| `HADA_Website_Template_Sample` | 本リポジトリ — verified v0.1.0 example |
| `HADA_Website_Template` | Clean public template (no sample content) |

正規のエージェント契約は `AGENTS.md` を参照してください。

---

## Disclaimer（免責事項）

詳細な免責事項は [DISCLAIMER.md](DISCLAIMER.md) を参照してください。
