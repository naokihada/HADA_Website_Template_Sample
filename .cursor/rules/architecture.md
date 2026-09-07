# Architecture rules (Cursor adapter)

Canonical source: `AGENTS.md` Architecture sections.

## Key boundaries

| Concept | Location |
|---|---|
| Content Master | `content/` |
| Publication Root | `site/` |
| External references | `references/` |
| Capabilities (plugins) | `tools/plugins/` with spec + manifest |
| Agent workspace | `Cursor/` (not published) |

## Pipeline

Source → Source Adapter → Content Master → Processing → Destination → `site/`

## Do not

- Merge WordPress.com and self-hosted WordPress into one plugin concept
- Treat static cache or `site/index.html` as source of truth
- Mix PWA client cache with static-cache capability
- Put site core logic inside cron or n8n definitions

## Repository flow

Development (this repo) → Release (`HADA_Website_Template`) → Sample (`HADA_Website_Template_Sample`)
