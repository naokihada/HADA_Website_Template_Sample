# Manga viewer correction — 2026-11-10

## Corrected state

- The previous Sample JSON order (`扉絵 → 裏表紙 → 本文 → 表紙`) was a mistaken data reversal. The manga order is now `表紙 → 扉絵 → 本文1〜4 → 裏表紙`.
- `Next` still advances forward through that order; `Previous` reverses it. The manga toolbar only changes placement: Next on the left, Previous on the right. Keyboard mapping remains RTL (`ArrowLeft` forward, `ArrowRight` backward).
- The left-first opening shows the cover on the left with the facing image hidden and no `src`; it does not generate or request a blank image.

## Verification

- `media_library.py validate`: passed (0 errors).
- Rebuilt generated media pages for `en`, `jp`, and `de`.
- Browser checked the generated Sample output: right-first opens cover/frontispiece, advances through both body spreads to the back cover, and reverses with Previous/keyboard. Left-first opens the cover alone on the left and Next shows frontispiece/body page 1. No JavaScript errors or blank image requests.
- Dev `tests/test_media_viewer_browser.py`: 3/3 passed, including manual-order navigation, visual button placement, both first-page sides, and empty-facing-slot handling.
- Dev `tests/test_media_library.py`: 21/23 passed; its two remaining working-tree inconsistencies are recorded in the Dev report `AI/reports/RESPEC_MANGA_VIEWER_20261110.md`.

No commit, release sync, or deployment.
