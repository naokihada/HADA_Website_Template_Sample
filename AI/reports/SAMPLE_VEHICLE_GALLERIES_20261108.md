# Sample vehicle gallery update — 2026-11-08

## Scope

- Removed the placeholder `template-reader` collection from the JSON master and deleted its generated `media-reader/template/` route in Japanese, English, and German.
- Added two sibling gallery collections using the existing catalog, listing, thumbnail, and viewer behavior. No template feature or custom UI was added.
- Generated and imported eight distinct photorealistic images: four futuristic vehicles from an otherworld and four magic-engine motorcycles.
- Added localized titles and alt text for Japanese, English, and German.

## Verification

- Sample automated suite: 172 tests passed.
- Media catalog validation: passed, zero errors.
- Asset validation: passed, 17 images.
- Media sync: clean.
- Framework validator: PASS, 69 checked, zero failures; existing `CFG-010` warning because `config/site.yaml` is absent.
- Each new gallery has four distinct displayed images with existing thumbnails in all three locales.
- Actual local sample host: both new Japanese gallery routes returned HTTP 200; removed `/jp/media-reader/template/` returned HTTP 404.

No commit, release, or deployment was performed.
