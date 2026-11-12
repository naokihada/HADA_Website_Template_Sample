# Media Viewer Fit Mode Correction — 2026-11-08

This checkpoint predates the user's later approval to remove zoom controls and
add lightweight image-saving deterrence. Current implementation and verification
are recorded in MEDIA_VIEWER_SIMPLIFICATION_20261108.md.

## User direction

Fit-to-screen must scale the complete image up or down to fit the available
viewer stage. Actual size must remain one source-image pixel per CSS pixel.

## Changes

- Synchronized the Sample core viewer and generated publication script with the
  corrected Dev implementation.
- Fit scale is not capped at 100%; image aspect ratio is preserved.
- Actual size uses the intrinsic image dimensions, with scrolling when needed.
- Zoom-out cannot move below fit scale; image-load completion preserves any
  scale the user has already selected.
- Touch swipe gating follows fit scale.

## Verification

- Sample suite: 171 tests passed, including the eight-image gallery browser
  regression and enlarged-image mouse-wheel pan/reset checks.
- Asset validation passed for 9 images; media sync reported 0 changes and 0
  findings; media catalog validation reported 0 errors.
- Dev suite: 179 tests passed. The dedicated browser test verifies fit-upscale
  on a 160x120 image, intrinsic actual size, zoom, and return to fit.
- Against the actual XAMPP Sample host, the 1536px source image rendered at
  1098px in fit mode and 1536px in actual-size mode; route returned HTTP 200.
- No commit, release, or deployment was performed.
