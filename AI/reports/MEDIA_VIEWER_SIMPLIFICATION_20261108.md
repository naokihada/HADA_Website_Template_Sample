# Media Viewer Simplification and Image-Saving Deterrence — 2026-11-08

## Adopted direction

- Remove zoom-in and zoom-out controls.
- Keep fit-to-screen and intrinsic actual-size modes.
- Add lightweight, marketable deterrence against casual image saving.

## Implementation

- Synchronized the Sample media catalog renderer and viewer script with Dev.
- Generated gallery and sequence images carry a protected-image marker and
  disable native image dragging.
- The local script prevents context menus and dragstart on marked media images,
  including the modal image.
- Deterrence script loads for image collections even when the modal viewer is
  disabled. Viewer CSS and dialog markup remain conditional on viewer setting.
- Ordinary page areas retain their context menus.
- Rebuilt the Sample publication from its JSON catalog.

The feature provides lightweight deterrence only. Published derivative URLs
remain public, and JavaScript-disabled pages do not receive client-side
deterrence. This feature does not provide access control or guaranteed download
prevention.

## Verification

- Sample suite: 172 tests passed; Dev suite: 180 tests passed.
- Sample asset validation: 9 images passed; media sync reported 0 changes and
  0 findings; catalog validation reported 0 errors.
- Actual XAMPP Sample route returned HTTP 200. Chromium confirmed right-click
  suppression on gallery and viewer images, ordinary context menu availability
  on the page heading, native drag suppression, and no zoom controls.
- Browser regression covers fit/actual sizing, no-JavaScript fallback,
  image context menus and drag events, and viewer-disabled deterrence markup.

No commit, release, or deployment was performed.
