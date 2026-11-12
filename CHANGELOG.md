# Changelog

All notable **public** changes to HADA Website Template releases.

## [0.4.2] — 2026-11-06

### Added

- Adopted compatible HADA Base v0.1.1 operations: append-only `WHY.md` records and
  opt-in, hash-deduplicated conversation import into the Website archive.
- Added recursive manual image-set intake with stable folder-derived identities,
  natural-order previews, append-only re-import, and protected staged promotion.
- Added a progressive local image viewer with keyboard, touch, zoom, fullscreen,
  and static-link fallback while retaining generated static collection pages.
- Enforced configured canonical hosts for canonical and localized alternate URLs.

### Compatibility

- Added the direct v0.4.1 → v0.4.2 upgrade edge. Existing user content and archived
  conversations are not moved or replaced automatically.
- Existing media manifests remain supported; the viewer is an optional enhancement
  to generated pages and uses no third-party runtime.

## [Unreleased]

### Added

- Added opt-in safe partial Template Upgrade application for verified, conflict-free template-owned additions and updates; conflicts, removals, project configuration, and adoption metadata remain pending.
- Made tree-parity checks read-only by default; JSON reports are written only to an explicitly requested path.
- Automatically update the displayed Template version in recognized footer attributions linked to the Template repository during upgrades, while preserving unrelated links and refreshing matching HTML-master registry hashes.
- Added an explicit HTML-detail gallery link contract with direct image links
  disabled by default and available only through explicit project opt-in.
- Added configurable text-logo Web overlays for generated JPEG derivatives,
  with clean retained masters and thumbnails, provenance, and configuration
  fingerprints for deterministic regeneration.
- Added background-protection and foreground-first accessibility policy with a
  deterministic contrast audit for configured color pairs.
- Added configuration-driven UI profiles: `shared-shell`, `standalone`, and `pwa`.
- Added an optional Playwright browser contract runner with route discovery,
  local-server execution, external-request blocking, desktop/mobile viewports,
  overflow checks, and Display State navigation persistence checks.
- Added shared semantic light/dark surface tokens and responsive long-identifier
  safeguards.
- Added isolated candidate build promotion with ownership-aware preservation and
  `REVIEW_REQUIRED` handling for unknown publication files.
- Added browser-contract verification to the safe Template Upgrade candidate gate.

### Compatibility

- Corrected the migration graph to include **v0.4.0 → v0.4.1** and added a mandatory
  Dev release-preparation gate that checks the direct path from the latest prior
  stable Public tag before producing an apply plan.
- Published pages remain static and do not require Playwright, external JavaScript,
  a CDN, or a server runtime.
- Existing direct content builds remain supported; Release and Upgrade workflows
  should use candidate build plus explicit promotion.
- LocalStorage remains the default Display State persistence mechanism. Cookie
  persistence is not inferred as a Core requirement.

## [0.4.1] — 2026-09-23

### Added

- Added static primary and section navigation patterns with localized labels,
  current-page semantics, and logical breadcrumb hierarchies.
- Added responsive, CSS-only navigation examples: the secondary row is reserved
  on wide layouts and empty space is removed on narrow screens.
- Added per-page HTML Master authoring guidance and a multilingual Sample
  demonstration; no navigation is injected into existing consumer pages.

### Compatibility

- No route, Page Registry schema, or media data-format changes.
- Existing sites opt in by editing their localized HTML Masters; existing pages
  are not automatically rewritten by build or upgrade.
- No JavaScript, database, server routing, or external runtime dependency is added.

## [0.4.0] — 2026-09-23

### Added

- Added a media-neutral catalog for images, video, and PDF/document assets, with
  a reserved extension point for future audio support.
- Added recursive media collections, static gallery/detail output, and comic or
  sequential reading in single-page and optional two-page spread layouts.
- Added configurable reading direction, first-page placement, localized Next /
  Prev labels, filename ordering, and representative-image behavior when a
  collection listing is hidden.
- Added best-effort media metadata processing policy, separate from experimental
  embedded-signal transformation, plus configurable domain-mark precedence.
- Added a reviewable v0.3 image-catalog migration path and v0.4.0 Sample/test
  coverage for media fallbacks and comic presentation.

### Compatibility and Upgrade Warning

- **The media data structure changes in v0.4.0 and may require migration.**
  Review the generated migration plan before applying it; masters and unknown
  files are preserved.
- Existing v0.3 image manifests remain readable during transition. No migration
  silently rewrites a consumer's manifest or publication output.
- Audio playback/conversion, direct AI-master publication, and content-embedded
  provenance-signal modification are not implemented.
- Published pages remain static and do not require external JavaScript, a CDN,
  or a server runtime.

## [0.3.3] — 2026-09-20

### Added

- Added a shared, versioned Display State contract across page, locale, and gallery navigation.
- Added best-effort localStorage persistence for theme, text size, and display mode.
- Added safe fallback for invalid stored data, unsupported values, private browsing, and storage quota errors.
- Added configurable persistence storage and key through `display.persistence`.
- Added regression coverage for persistence configuration and generated page attributes.

### Compatibility

- No server communication is used for display state.
- JavaScript-disabled pages remain readable and navigable with standard display defaults.
- `config/project.yaml` `project.version` remains independent.
- Existing i18n, gallery, image, custom publication-root, and HTML Master workflows remain supported.

## [0.3.2] — 2026-09-20

### Added

- Added long-lived static Web and Web Archive compatibility policy
- Added Core display configuration for theme, text size, mode, and optional persistence
- Added local optional display enhancement without external JavaScript or CDN dependencies
- Added CSS-first fallback behavior for Light, Standard, and Standard Mode
- Added keyboard-accessible theme and text-size controls to generated Markdown pages
- Added `prefers-color-scheme` and `prefers-reduced-motion` support

### Compatibility

- Semantic HTML and ordinary links remain usable without JavaScript
- PWA Timer remains a bounded local-JavaScript exception
- `config/project.yaml` `project.version` remains independent
- Existing i18n, gallery, image, custom publication-root, and HTML Master workflows remain supported

## [0.3.1] — 2026-09-19

### Added

- Added explicit Page Registry support for Markdown and HTML Masters
- Added safe preservation of existing locale HTML files
- Added isolated candidate build output
- Added release reference snapshots and deterministic tree parity checks
- Added `OUTDATED` and `REVIEW_REQUIRED` upgrade states for HTML Master pages

### Compatibility

- Markdown Master remains the default
- `config/project.yaml` `project.version` remains independent
- Existing publication roots remain supported

## [0.2.2] — 2026-09-19

### Added

- Added the built-in `content/pages/*_master.md` i18n pipeline
- Added locale snapshots such as `*_JP.md`, `*_EN.md`, and additional locales
- Added block-aware translation with protected inline code, URLs, HTML, and code fences
- Added `i18n-comments` support for translating comments while preserving code
- Added source hashes and translation lifecycle metadata to generated snapshots
- Allowed valid additional locale codes such as `de`
- Added three-locale regression coverage for JP, EN, and DE

### Compatibility

- Preserved the legacy `content/jp/` and `content/en/` pipeline
- No Git commit, tag, push, or GitHub Release is performed by this work

## [0.2.1] — 2026-09-17

### Changed

- Added the common machine-readable manifest schema across Dev, Public, and Sample
- Added `manifest_version`, `template.release`, compatibility metadata, repository metadata, and `files.template_base`
- Added manifest/Base consistency validation and regression tests
- Preserved `schema_version` and `data_format_version` at `0.1`
- Added the `0.2.0 → 0.2.1` migration path

## [0.2.0] — 2026-09-17

### Changed

- Replaced the agent-operation workspace convention of `.cursor/` and `Cursor/` with the agent-neutral `AI/` workspace
- Updated validator and repository structure expectations to require `AI/` and keep it outside the Web Publish boundary
- Added the documented legacy workspace migration procedure for existing consumer projects
- Added required upgrade checkpoints: preserve SPEC/manifest/affected-file history, classify legacy contents, migrate useful history to `AI/history/`, then run ReSPEC, tests, validator, build, security, and diff review
- Undefined ownership, migration meaning, or legacy content is now explicitly `REVIEW_REQUIRED`; agents must not guess or delete blindly
- Added migration path: **v0.1.3 → v0.2.0**

### Upgrade Notes

- `config/project.yaml` → `project.version` remains site-project metadata and is not changed by this Template version upgrade
- Existing `.cursor/` and `Cursor/` directories belong to the consumer project migration process; they are not part of the v0.2.0 Template artifact
- Preserve useful historical evidence in `AI/history/` before removing legacy directories

## [0.1.3] — 2026-09-11

### Added

- Client-only PWA Timer Demo at `site/timer.html`
- Digital `MM:SS` timer from `00:00` through `99:59`, default `03:00`
- Web Audio API completion beep
- Best-effort local notifications through a Service Worker
- Offline app-shell cache for the timer demo
- Upgrade migration path: **v0.1.2 → v0.1.3**

### Notes

- No server, database, cron, or external API is required.
- Notification delivery while the PWA is fully terminated is best-effort and not guaranteed.

## [0.1.2] — 2026-09-09

### Added

- **Template Upgrade** from GitHub stable Release (`tools/core/upgrade_from_release.py`)
- **`config/website-template.json`** — template version and ownership contract
- **`docs/UPGRADE.md`** — public upgrade guide
- Three-way migration (Previous Template / Current Site / New Template)
- Network preflight and retained temporary clone for inspection
- First migration path: **v0.1.1 → v0.1.2**

### Safety

- User-owned content preserved (`content/`, term dictionary, site config, assets)
- Conflicts produce **REVIEW_REQUIRED** instead of blind overwrite
- Upgrade tool does not modify site Git history (no branch/commit/push)

### Documentation

- Public validation unchanged (`docs/VALIDATION.md`)
- Agent-independent framework in `AGENTS.md`

## [0.1.1] — 2026-09-09

### Added

- Public validation guide (`docs/VALIDATION.md`)
- Agent-neutral `AI/` workspace and handoff boundary
- Clarified internal AI workspace versus Web Publish boundary

### Removed

- Development-only `tools/core/SPEC.md` from public template

## [0.1.0] — Initial public template

- Core validator, build pipeline, minimal i18n (jp/en)
- Foundation directory structure and tests
## [0.3.0] - 2026-09-19

### Added

- Added a persistent image asset library with PNG masters, JPEG web derivatives,
  thumbnails, provenance, and configurable generation profiles.
- Added generated gallery index and image detail pages from the approved media
  manifest.
- Added page-scoped background visuals that can be reused in the gallery.
- Added non-destructive image replacement by immutable `image_id` values.
- Added Sample-site gallery validation and four-image demonstration coverage.

### Compatibility

- ChatGPT Image remains the default provider, but provider and prompt profiles
  are user-configurable.
- Existing images remain valid; legacy `AI/history` provenance can be copied to
  persistent metadata without deletion.
