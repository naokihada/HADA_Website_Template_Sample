# Media library covers, sorting, and viewer cleanup — 2026-11-08

## Implemented

- Added JSON collection dates: optional `publication_date` and `updated_date` fields accept valid `YYYY-MM-DD` dates.
- Parent library pages show child collections as thumbnail cards. The first approved image in configured order is the cover; nested collections use the first image in the first descendant with media. Covers remain in normal reading order.
- Added localized sort controls for name, publication date, and updated date, with ascending and descending order. Missing dates remain last. Links stay usable without JavaScript.
- Fixed the viewer caption so it overlays the stage without widening it. Scrollbars are hidden; actual-size overflow remains accessible by pointer drag, touch, and wheel/trackpad.
- Regenerated and replaced the malformed Canyon Glider. Removed its former master, derivative, thumbnail, provenance, inbox copy, and catalog entry.
- Removed the HADA template icon from media records, collection references, page bindings, master, derivatives, provenance, and generated output.
- Synchronized the implementation and tests to Sample; regenerated media and site output in Japanese, English, and German.

## Verification

- Dev suite: 183 tests passed. Sample suite: 175 tests passed.
- Dev and Sample media catalogs validate. Sample media sync is clean; all 16 approved image assets validate.
- Framework validators pass in both repositories. Each reports the existing warning that `config/site.yaml` is absent.
- Sample browser check on the actual local host: library HTTP 200; three cover cards; no icon; no horizontal overflow; no JavaScript errors.
- Viewer fit mode has no stage overflow; actual-size drag moved both scroll axes while scrollbar styles remained hidden.
- Old icon and old glider URLs return HTTP 404; replacement glider returns HTTP 200.

No commit, release, or deployment was performed. Pre-existing unrelated repository changes were preserved.
