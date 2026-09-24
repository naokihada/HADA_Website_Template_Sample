# HADA Website Operations Framework — Sample (v0.4.1)

Working example of the v0.4.1 framework. This repository contains a verified fictional
sample site built from `HADA_Website_Template_Dev`.

日本語の情報は、このページの下にあります。

**Release template:** [HADA_Website_Template](https://github.com/naokihada/HADA_Website_Template) — reusable public framework template this sample is based on.

This repository is a **complete sample/demo** of the HADA Web Site Operations Framework v0.4.1.
All site content uses **fictional data** (Sample Tea Co. / Hanako Sato). It does **not**
endorse any real company or service.

---

## What this demonstrates

| Feature | Location |
|---|---|
| Master i18n source | `content/pages/*_master.md` |
| Locale snapshots | `content/pages/*_JP.md`, `*_EN.md`, `*_DE.md` |
| Tested locales | Japanese, English, German |
| Site-wide term dictionary | `config/term_dictionary.yaml` |
| Block-aware translation (mock provider) | `tools/core/build_site.py` |
| Markdown → HTML | `site/jp/`, `site/en/`, `site/de/` |
| Publication Root | `site/` |
| PWA Timer Demo | `site/timer.html` — client-only, `03:00` default, best-effort notifications |
| Static hierarchical navigation | `site/navigation-demo/` — localized per-page HTML, About sub-navigation, and breadcrumbs without external JavaScript |

Fictional sample data: **Sample Tea Co.** / **Hanako Sato** (佐藤花子).

## Quick start

Requires **Python 3.10+**.

Open `site/navigation-demo/index.html` in the built site to review the three-language
navigation and breadcrumb example.

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
| `HADA_Website_Template_Sample` | This repo — verified v0.4.1 example |
| `HADA_Website_Template` | Clean public template (no sample content) |

See `AGENTS.md` for the canonical agent contract.

## Disclaimer

See [DISCLAIMER.md](DISCLAIMER.md).

---

# 日本語

## 概要

v0.4.1 フレームワークの動作例です。本リポジトリには、`HADA_Website_Template_Dev` で
検証した架空データによるサンプルサイトが含まれます。

AI Agent対応Webサイト運用フレームワーク v0.4.1 のサンプル実装リポジトリ。

**Release template:** [HADA_Website_Template](https://github.com/naokihada/HADA_Website_Template) — 本サンプルのベースとなる再利用可能な公開 Framework テンプレート。

本リポジトリは HADA Web Site Operations Framework v0.4.1 の **完全なサンプル／デモ** です。
サイト内容はすべて **架空データ**（Sample Tea Co. / 佐藤花子）であり、
**実在の企業・サービスを推薦するものではありません**。

---

## 本サンプルで示す機能

| Feature | Location |
|---|---|
| Master i18n source | `content/pages/*_master.md` |
| Locale snapshots | `content/pages/*_JP.md`, `*_EN.md`, `*_DE.md` |
| Tested locales | Japanese, English, German |
| Site-wide term dictionary | `config/term_dictionary.yaml` |
| Block-aware translation (mock provider) | `tools/core/build_site.py` |
| Markdown → HTML | `site/jp/`, `site/en/`, `site/de/` |
| Publication Root | `site/` |
| PWA Timer Demo | `site/timer.html` — client-only, `03:00` default, best-effort notifications |
| Static hierarchical navigation | `site/navigation-demo/` — per-page HTML, translated section navigation, breadcrumbs, and responsive no-JS behavior |

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
| `HADA_Website_Template_Sample` | 本リポジトリ — verified v0.4.1 example |
| `HADA_Website_Template` | Clean public template (no sample content) |

正規のエージェント契約は `AGENTS.md` を参照してください。

---

## Disclaimer（免責事項）

詳細な免責事項は [DISCLAIMER.md](DISCLAIMER.md) を参照してください。
