# HADA Website Template Sample — Demonstration Contract

| Contract field | Value |
|---|---|
| Consumes | HADA Website Template 0.5.0 |
| HADA Base compatibility | 0.2.0 |
| Purpose | Demonstrate and regression-check features that exist in the Template |

This is the Sample project's concrete content and route contract. It does not add
capabilities to the Template. The Template implementation contract is maintained
in the Development repository and reflected in the Public Release contract.
Sample content is sourced from the checked-in masters and assets; no filler or
hand-created substitute media is part of the gallery demonstration.

## 1. Sources and generated output

- `config/media.catalog.json` is the master for the media library, collection
  hierarchy, ordered items, viewer modes, and public derivatives.
- `assets/media/master/` retains private image masters; `assets/media/web/` and
  `assets/media/thumbnails/` contain rebuildable approved representations.
- `site/` is generated Publication Root output. Rebuild it from the catalog,
  content masters, configuration, and assets; do not hand-edit generated media
  pages as a source of truth.
- Generated media routes use the shared shell's Display State persistence flag and configured storage key so theme and text size survive locale and collection navigation.
- Project configuration and machine records use TOML/JSON/JSONL as specified by
  the Template. YAML is not valid Sample input or output.

## 2. Media library routes and datasets

The configured route is `media`, so each locale library begins at:

- Japanese: `/jp/media/`
- English: `/en/media/`
- German: `/de/media/`

The library is generated from the four catalog collections below. Collection
routes remain nested below the locale library root. The landing page presents
cover thumbnails and supports sorting by name, publication date, and updated date
in ascending or descending order.

| Dataset | Route below `/media/` | Catalog contents | Demonstrated behavior |
|---|---|---:|---|
| Otherworld landscapes | `otherworld-landscapes/` | 8 images | Gallery and image viewer |
| Future otherworld vehicles | `otherworld-vehicles/` | 4 images | Gallery and image viewer |
| Magic-engine motorcycles | `magic-engine-motorcycles/` | 4 images | Gallery and image viewer |
| Japanese manga demo | `manga-viewer-demo/volume-01/chapter-01/` | 7 images | Page order, single-page and manga modes, both opening sides |

The three English- and Japanese-language gallery datasets use the same collection
IDs and item order; localized title and alt text are catalog data. The manga
dataset's seven actual images are ordered as cover, frontispiece, body pages, and
back cover. The catalog order is authoritative. No placeholder or blank image is
inserted to alter a spread.

## 3. Manga viewer acceptance contract

- The manga collection starts directly in the viewer to avoid exposing the page
  list before reading.
- `manga` is the Japanese right-to-left spread mode. `single` displays one image
  at a time. Desktop defaults to `manga`; mobile defaults to `single`.
- The viewer offers first-page-on-right and first-page-on-left options. Changing
  this option changes the facing-page grouping only; it never reverses catalog
  order or makes Next navigate backward.
- In manga mode, the visible previous/next button positions are adapted for
  right-to-left reading. Keyboard navigation keeps its established forward/back
  semantics.
- An absent facing page is an empty layout slot, not a synthetic image or catalog
  item. Public media records remain exactly the seven supplied manga pages.
- Without JavaScript, the generated static pages retain usable navigation and
  direct media links.

## 4. Regeneration and checks

Regenerate the Sample publication tree from checked-in sources using the Template
build. Validate the media catalog, framework structure, internal routes, and
browser behavior at desktop and mobile sizes when Playwright is available. Verify
that every collection card, breadcrumb, language link, and manga navigation target
resolves beneath the configured locale route; no legacy unprefixed collection
route or `/media-library/` link is part of this contract.
