# CURRENT

## Completed — Sample media-library repair (2026-11-07)

- Removed the duplicate image rendering in catalog cards; one thumbnail now represents each image, linked to the public derivative through the viewer.
- Added localized ancestry breadcrumbs and child labels; corrected logical DOM order and spread placement.
- Localized reader navigation for Japanese, English, and German.
- Retired the duplicate legacy gallery route from the Sample entry points and generated output.
- Enabled the Sample browser contract and declared German publication output ownership.
- Verified the publication with 14 media tests, 2 promotion tests, the fullscreen browser regression, an 81-route real-browser contract, a zero-missing-reference crawl, and direct reader/viewer checks including fullscreen.
- Detailed link map and evidence: `AI/reports/MEDIA_LIBRARY_REPAIR_20261107.md`.
- No commit, release, Public synchronization, XAMPP configuration edit, or Apache restart.
- 2026-11-08 media JSON cleanup: legacy media/gallery YAML and fabricated duplicate restaurant media/output removed; Sample now demonstrates a nested JSON catalog with the existing HADA icon. Full Sample suite 170/170 passes; media validator passes; framework validator passes with expected missing-site-config warning. No commit/release/deployment.

- 2026-11-08 follow-up (user correction): created eight individually prompted otherworld-fantasy landscape images; registered and promoted the multilingual JSON gallery. Sample full suite 171/171 and Dev 179/179 pass. Sample assets validation passes for 9 images; media sync clean; catalog validation has 0 errors; actual XAMPP host browser check passed 46 assertions. Detailed evidence: AI/reports/FANTASY_GALLERY_TEST_20261108.md. No commit/release/deployment.
- 2026-11-08 viewer correction: fit-to-screen now enlarges as well as shrinks to
  the stage; actual-size remains at intrinsic image pixels. Browser regression
  covers both modes and enlarged-image panning. Sample full suite 171/171 passes.
  Evidence: AI/reports/VIEWER_FIT_MODE_20261108.md.
- 2026-11-08 adopted viewer simplification: zoom controls removed; right-click
  menu and native drag suppressed on generated media images, even when the modal
  viewer is disabled. Full Sample suite 172/172 passes; Sample asset/media/
  catalog validation passes; actual XAMPP browser check passed. Evidence:
  AI/reports/MEDIA_VIEWER_SIMPLIFICATION_20261108.md. No commit/release/deploy.

- 2026-11-08 sample dataset cleanup: removed the placeholder `media-reader/template` collection and generated route; added two JSON-master gallery datasets with four distinct photorealistic generated images each (future otherworld vehicles, magic-engine motorcycles). Existing import, gallery, and viewer functions only. Full Sample suite 172/172 passes; media catalog validation 0 errors; asset validation 17 images; media sync clean; framework validation passes with expected missing-site-config warning. Both new Japanese routes return HTTP 200; retired route returns 404. Evidence: `AI/reports/SAMPLE_VEHICLE_GALLERIES_20261108.md`. No commit/release/deployment.

## 2026-11-08 — Media library covers, sorting, and viewer cleanup

- Status: implemented and verified in Dev and Sample.
- Added cover cards from the first ordered image, localized sorting by name/publication/update date and direction, and scrollbar-free viewer panning.
- Removed the HADA icon and former Canyon Glider media; registered the replacement.
- Verification: Dev 183/183 and Sample 175/175 tests; media/framework validators pass; Sample media sync clean; actual local-host browser check passed.
- Evidence: AI/reports/MEDIA_LIBRARY_COVERS_SORTING_20261108.md.
- No commit, release, or deployment.

## 2026-11-09 — Manga viewer Sample

- Added the four supplied manga pages as one JSON-master gallery collection with
  unique IDs and thumbnail/web derivatives.
- Demonstrates slideshow and comic modes, RTL right-first and left-first layouts,
  plus no-JavaScript static routes for both choices.
- Catalog validation and media sync pass; full Sample suite passes 178/178. Actual
  Sample URL browser check confirmed the left-first view fits without page/stage
  overflow.
- Details: Dev `AI/reports/MANGA_VIEWER_IMPLEMENTATION_20261109.md`.
- No commit, release, or deployment.

## 2026-11-09 — Manga reader corrections

- Corrected comic opening controls, direct viewer entry, spoiler-free index, old body order, supplied book assets, and root `/media/` links.
- Removed generated side-specific comic routes.
- Sample full unittest suite and browser contract pass; catalog validation has zero errors.
- Evidence: Dev `AI/reports/MANGA_VIEWER_CORRECTIONS_20261109.md`. No commit/release/deployment.

## 2026-11-09 — Manga order and viewer control polish

- Sample manga sequence changed to frontispiece (B), back cover (C), body pages, cover (A).
- Updated template viewer mode controls to borderless text and Japanese image navigation to `戻る` / `次へ`.
- Sample manga browser contract passed; no Release sync or deployment.

## 2026-11-10 — Japanese manga and responsive page modes

- Sample viewer modes are `single` and `manga`; `comic` is reserved for later.
- Desktop opens in manga spreads, mobile up to 600px opens in single-page mode.
- Sample JSON order remains B → C → body → A.
- Full Sample suite: 178 passed; browser contract: 4 passed; catalog errors: 0; asset validation: 23 images.
- Evidence: Dev `AI/reports/MANGA_RESPONSIVE_MODES_20261110.md`. No Release sync or deployment.

## 2026-11-10 — Sample media folder hierarchy and watermarks

- Relocated 23 image masters, Web derivatives, and thumbnails into collection folders; manga uses `volume-01/chapter-01` in both filesystem and route hierarchy.
- Manga remains a direct viewer entry from `/media/`, ordered扉絵 → 裏表紙 → 本文 → 表紙. Removed stale parent reader pages from en/jp/de generated output.
- Web JPEGs are regenerated with the existing HADA icon at bottom-left and exact `HADA_Website_Template` text at bottom-right; metadata stripping is enabled.
- Media catalog validation passed (0 errors), derivative sync regenerated 23 images, and media pages rebuilt for en/jp/de. Automated tests and browser checks were not run.
- Current Dev and Sample template version: 0.4.2. No version bump, commit, Release sync, or deployment.

## 2026-11-10 — Manga order and blank-facing correction

- Corrected Sample manga catalog order to cover → frontispiece → body → back cover; the earlier frontispiece → back cover → body → cover order was erroneous.
- `Next` and `Previous` actions and keyboard mapping are unchanged. Manga mode places Next left and Previous right. Left-first mode hides the unused facing image and does not request a blank asset.
- Media validation passed; en/jp/de media output rebuilt; generated-Sample browser flow passed. Dev manga browser tests passed 3/3.
- Details: `AI/reports/MANGA_VIEWER_CORRECTION_20261110.md`. No commit or deployment.
