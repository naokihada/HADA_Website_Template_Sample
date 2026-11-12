# Sample Site Functional Audit — 2026-11-07

## Scope and preservation

- Target: the live local XAMPP vhost `http://HADA_Website_Template_Sample/` and the checked-out Sample repository.
- This is a read-only functional audit. No application code, content, settings, Apache/XAMPP files, or generated pages were changed by the audit.
- The Sample working tree already contained uncommitted v0.4.2 synchronization and gallery changes before this audit. Those changes were preserved.

## Observed facts

### Automated checks

- All 27 `tests/test_*.py` modules pass.
- `tests/test_browser_ui.py` returns exit code 0 with status **SKIPPED** because `verification.browser.enabled` is false in `config/site.example.yaml`. It inventories and tests zero routes in this Sample configuration.
- `tests/test_media_viewer_browser.py` passes, but it constructs a temporary two-image fixture and temporary HTTP server. It does not load this Sample site's manifest, pages, or XAMPP host.
- Framework validator and media catalog validator pass.

### Live XAMPP checks

- The root, English/Japanese home pages, gallery routes for `en`, `jp`, and `de`, media-library route, single/spread reader pages, and viewer JS/CSS return HTTP 200.
- The three locale gallery indexes each render five image cards. All five images load and each card opens its corresponding detail page with a loaded image.
- The media library renders five viewer triggers. Opening an image, loading it in the dialog, updating position, moving to the next image, closing, and restoring focus work.
- The single-page reader viewer moves to the next static page and reopens the viewer. The spread viewer advances through sequence positions 1 → 2 → 3 and across spreads when opened from the position-1 image.
- With JavaScript disabled, sequence image links open the public image directly.
- The English gallery has no horizontal overflow at 390 px. No JavaScript page errors were observed on the sampled routes.
- Crawling all 99 generated HTML files found 117 unique same-site URLs: 116 returned HTTP 200 and one returned HTTP 404: `/de/index.html`. The broken link is the “Home” link in each generated `/de/gallery/` page.

### Confirmed quality gaps

- German has a gallery route but no `/de/index.html` home route, so the gallery's Home link is broken.
- The gallery heading is `Background Gallery` in English, Japanese, and German.
- The sequence navigation labels render `Next` in all three locales. Viewer toolbar labels are localized.
- On a spread page whose first page is visually on the right, the DOM lists `media-item-00002` (left page) before `media-item-00001` (right, first page). This disagrees with the intended right-to-left reading order for assistive technology and sequential keyboard reading.
- The public Sample exposes two galleries with the same five assets: the legacy `/gallery/` with image detail pages and `/media-library/` with a modal viewer and reader links. Both work, but the overlap makes the product surface unclear.

## Test interpretation

The green unit suite is not evidence that the deployed Sample flow works. Its site-wide Playwright contract is disabled, and its viewer browser test is fixture-only. The live crawl found a broken route that those checks did not cover. A first spread smoke assertion also selected the first DOM element rather than the first logical page; after targeting `#media-item-00001`, the viewer sequence worked. The DOM-order mismatch remains a separate confirmed accessibility finding.

## Initial recommendation — superseded by the user implementation direction

### Keep the Sample site's public journey small

1. Keep the language entry page, localized home pages, and one canonical image gallery built from the media manifest.
2. Keep five reviewed sample images and one understandable interaction: a thumbnail opens the local viewer, with direct-image fallback when JavaScript is unavailable.
3. Retire the duplicate gallery listing. Do not keep both `/gallery/` and `/media-library/` presenting the same five images.
4. Defer the single-page and spread readers from the main Sample until their user-facing purpose and acceptance cases are agreed. Preserve Template Core code unless a separate approved decision removes it.
5. Keep unrelated demonstrations such as the PWA timer and navigation showcase out of the gallery journey. Decide separately whether the Sample needs them; do not remove their source based only on this audit.

### Required quality gates before calling the Sample functional

- Enable and run the browser UI contract for Sample; a disabled contract must produce a visible non-pass status in release reporting.
- Add a live-host smoke run against the configured XAMPP vhost, not only a temporary fixture server.
- Crawl every generated local link and asset. Require zero same-site 4xx responses; include locale home, gallery, image, and navigation routes.
- Test image load, modal open/close, keyboard operation, position order, no-JS fallback, and both desktop and 390 px layouts on actual Sample pages.
- Require translated page titles/navigation labels for every supported locale, and DOM order that matches the configured reading direction.
- Build into a candidate first, inspect the exact route/file delta, then promote. Avoid direct edits to generated `site/` pages where a source/configuration input exists.

### Implementation boundary

This section records the initial read-only audit proposal. The user subsequently directed implementation. The duplicate gallery was retired, the media library and readers were repaired, and both Dev Template Core and Sample were updated. See `AI/reports/MEDIA_LIBRARY_REPAIR_20261107.md` for the route map and verified implementation results. Existing uncommitted work was preserved; no commit, tag, Public synchronization, Apache/XAMPP configuration edit, or restart occurred.

## Conclusion

This conclusion describes the initial audit state and is superseded by the completed implementation report at `AI/reports/MEDIA_LIBRARY_REPAIR_20261107.md`. The repaired publication passed the full route crawl and browser contract; the requested XAMPP routes and viewer controls were verified there.
