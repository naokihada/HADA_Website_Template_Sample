# Sample Template Specification Summary

This repository demonstrates the public HADA Website Template contract at version
`0.2.0`. The machine-readable contract is `config/template.manifest.yaml`; its
compatibility schema/data format versions remain `0.1`.

The Sample site preserves its own content, assets, pages, settings, and bilingual
README. Template Upgrade must preserve those project-owned files, classify legacy
`.cursor/` and `Cursor/` contents before migration to `AI/`, and finish with ReSPEC,
tests, validator, build, and diff review.

## Media library master specification

`SPEC.md` is the sole normative source for media library behavior. Intake,
catalog, generated pages, UI, publication boundaries, supported depth, and
verification are defined here. Other documents may link here but must not
duplicate or override these requirements.

### Source of truth and publication model

- `config/media.catalog.json` is the versioned project-owned media catalog.
- Generated HTML and published derivatives are rebuildable output. Masters and
  provenance remain outside the publication root.
- Original masters are stored in `assets/media/master/`, web derivatives in
  `assets/media/web/`, thumbnails in `assets/media/thumbnails/`, and provenance
  in `assets/metadata/media/`.
- Only approved public representations may be copied into the publication root.
  Private source/master files must never be published. AI-generated originals
  are not published by the Core import path.
- Import refuses to overwrite an existing media ID. Re-encoding strips image
  metadata by default. PDF and video metadata stripping is best effort and must
  report when an optional local tool is unavailable or fails. This does not
  establish that all embedded metadata/signals were removed.
- Generated image masters enter through `AI/inbox/media/generated/`; user-
  prepared media enters through `AI/inbox/media/manual/`. Intake planning is
  descriptive until explicitly reviewed and approved.
- A direct child directory in `AI/inbox/media/manual/` forms an initial
  collection. Descendants are scanned recursively and relative paths retained.
  Supported image files are accepted in a set; other formats require manual
  classification. Scanning is additive, existing files are not replaced, and a
  renamed source folder creates a new set rather than migrating/deleting the old
  one. Import requires explicit approval.
- Standard reviewed intake flow:

  ```powershell
  python tools/core/media_assets.py scan-inbox --root .
  python tools/core/media_assets.py import --root . --approve
  python tools/core/media_library.py validate --root .
  python tools/core/media_assets.py sync --root .
  python tools/core/media_assets.py sync --root . --apply
  ```

  Inspect the import plan before approval. `sync` without `--apply` previews
  derivative updates; apply only after reviewing that preview. Files directly
  inside `manual/` retain individual intake handling.
- Domain marking is enabled by default for image derivatives and thumbnails;
  set `processing.domain` to the intended domain before importing. Embedded
  signal transformation is separate, disabled, and not implemented.

### Routes, collections, and navigation

- `paths.media_route` in `config/project.yaml` controls the locale-local public
  media root. Its default is `media`, producing `/jp/media/`, `/en/media/`, and
  equivalent paths for configured locales. It must be a safe relative route;
  no leading slash, traversal, query, fragment, or platform-invalid path parts.
- Collection `route` values resolve below this media root. A collection route
  matching the first top-level collection route is the library root; descendant
  route values beginning with that legacy root are rebased below the configured
  root while preserving their suffix. Other route values are appended below the
  configured root. This preserves current catalogs while shortening the public
  URL. New catalogs should use paths relative to the configured media root.
- Changing `paths.media_route` changes generated links and output locations
  without rewriting collection IDs or item metadata.
- Collections may nest and render as a gallery or ordered sequence. Collections
  with children render a cover-card library. A cover is the first approved
  image in configured order, or the first image in the first descendant for
  nested books. A cover remains in the collection's normal reading order.
- Collections may declare `publication_date` and `updated_date` as `YYYY-MM-DD`.
  Library cards can sort by localized name or either date in ascending or
  descending order. Missing dates sort last; without JavaScript, catalog order
  and all links remain available.
- A sequence defaults to right-to-left, single-page reading, filename order, and
  page 1 on the right. A collection may override reading direction, opening
  side, order, and optional two-page spread. Navigation labels can be localized.
- Zero-padded filenames such as `00001.jpg` are recommended. At 10,000 or more
  listed media items in one collection, validation/build emits a soft-limit
  warning; it does not reject the collection. No overall media count, album
  count, or maximum hierarchy depth is guaranteed by this warning.
- Nested collections are supported and four levels are covered by regression
  tests. There is no specified hard maximum depth; deeper structures remain
  unverified and should be tested before adoption.
- No hand-maintained page-per-item system or CMS is required. The JSON catalog
  generates public collection pages and sequence pages. Public library pages
  are navigation for visitors, not the content-management source of truth.

### Shared site UI and work viewing

- The library entry, collection indexes, and generated sequence pages must use
  the same shared site shell as locale content pages: shared core stylesheet,
  header/language navigation, main content container, display controls,
  footer, and display-preferences behavior. Media-specific styles may extend the
  shell but must not replace it with an independent standalone page frame.
- Work previews open in the same browser tab. Images may progressively enhance
  into the local in-page viewer; ordinary image links remain as a no-JavaScript
  fallback. Do not open each work in a new window by default. External resources
  may follow the site's external-link policy.
- The local viewer supports fit/actual sizing, panning, fullscreen when
  supported, previous/next navigation, keyboard controls, and touch swipes. It
  loads only the selected full-size image. Static pages retain direct links and
  sequence navigation without JavaScript; no external runtime is used.
- Context-menu suppression and disabled native image dragging are only casual
  saving deterrents. Public derivatives remain directly addressable and are not
  access-controlled.
- Videos use native controls and a direct-file fallback. PDFs use the browser's
  native viewer when available and always include an ordinary open/download
  link. Audio has no player in this release.
- The active catalog format is JSON schema `0.3` in
  `config/media.catalog.json`, based on `config/media.catalog.example.json`.
  YAML registries and the prior migration command are retired; catalogs must be
  converted to JSON before media tooling.

### Logical page bindings and image handling

- Stable `page_id` bindings may provide a background, page-header image, or
  multiple heading-level illustrations. Illustrations default to right
  alignment and may be set left. Locales share an asset unless explicitly
  overridden.
- HTML Masters opt in only through exact slots such as
  `<!-- HADA:MEDIA-SLOT page-header -->` or
  `<!-- HADA:MEDIA-SLOT illustration:preparation -->`. Unmarked HTML remains
  unchanged.
- Image metadata is removed by JPEG re-encoding by default. Image derivatives
  and thumbnails receive configured domain marks by default. These settings
  and processing results are recorded in the catalog/provenance.

### Scale and verification contract

- The current 10,000-item threshold is a warning for one collection, not a
  performance guarantee. No tested maximum for total media, albums, build time,
  output size, browser DOM size, or hosting capacity is specified.
- Before declaring a large archive production-ready, benchmark a representative
  catalog and assets, including build time/output size, collection-page initial
  load, thumbnail behavior, mobile layout, and route/link integrity. Use real
  scale targets such as 50 albums and 3,000 works when those are the intended
  operating values.
- Validation must cover route safety and uniqueness, valid catalog references,
  private/public path separation, nested collection generation, shared-shell
  conformance for every generated locale route, same-tab viewer behavior, and
  no-JavaScript links.
