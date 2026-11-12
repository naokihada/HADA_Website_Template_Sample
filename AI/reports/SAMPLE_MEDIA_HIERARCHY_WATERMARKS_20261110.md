# Sample media hierarchy and watermarks — 2026-11-10

## Scope

Updated the Sample media JSON catalog, its 23 image records and generated media output. Preserved existing unrelated Sample changes. No tests/browser automation, commit, Release synchronization, or deployment.

## Result

- Landscapes, vehicles, and motorcycles now use collection-scoped paths under `assets/media/{master,web,thumbnails}/<collection-id>/`.
- Manga paths and route use `manga-viewer-demo/volume-01/chapter-01`; the catalog remains the sole data master and keeps direct manga-reader entry from `/media/`.
- Manga sequence is frontispiece → back cover → body pages → cover. Obsolete parent reader pages were removed from generated en/jp/de output.
- Private watermark logo source is `assets/media/master/watermarks/hada-template-icon.png`, copied from the existing HADA site icon and excluded from gallery records. Public JPEG derivatives include the logo at bottom-left and exact case `HADA_Website_Template` text at bottom-right. Metadata stripping remains enabled; masters are retained unchanged.

## Verification

- `media_assets.py sync --apply`: 23 derivatives regenerated, no unresolved findings.
- `media_library.py validate`: passed, 0 catalog errors.
- `media_library.py build --locales en,jp,de`: completed.
- Static inspection confirmed deep manga route output, direct `/media/` link targets, and the specified order.
- Automated tests and browser checks were not run.

## Version

Dev and Sample manifest: `0.4.2`. No version number was changed.
