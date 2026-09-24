# Media Library

The media catalog is a versioned, project-owned data source. Generated pages and
published derivatives are rebuildable output; source masters and provenance are
kept outside the publication root.

## Intake

Place user-prepared files in `AI/inbox/media/manual/`. Place generated image
masters as PNG in `AI/inbox/media/generated/`. The intake planner only describes
files; inspect its output before approving an import:

```powershell
python tools/core/media_assets.py scan-inbox --root .
python tools/core/media_assets.py import --root . --approve
python tools/core/media_library.py validate --root .
python tools/core/media_assets.py sync --root .
python tools/core/media_assets.py sync --root . --apply
```

Originals are retained under `assets/media/master/`, public derivatives under
`assets/media/web/`, thumbnails under `assets/media/thumbnails/`, and provenance
under `assets/metadata/media/`. The import process refuses to overwrite an
existing media ID. AI-generated originals are not published by the Core path.
The illustration prompt profile is configured separately in
`config/illustration-generation.yaml`; ChatGPT Image is the default provider,
and the prompt requests square composition without a pixel-size instruction.
Generated provider and prompt details are retained in persistent provenance.
Edit a retained master under `assets/media/master/`, run `sync` to preview
changes, then use `sync --apply` to regenerate the matching derivative and
refresh its recorded source hash. The operation never changes the source master.

Image metadata is removed by re-encoding to JPEG by default. PDF metadata
stripping uses pypdf; video metadata stripping uses local FFmpeg when installed.
Those container operations are best effort. If an optional tool is unavailable
or fails, the importer warns and records that result; this does not establish
that metadata or embedded provenance signals are absent. Embedded-signal
modification is separate, disabled, and not implemented. Image derivatives and
thumbnails receive the configured domain mark by default. Set `processing.domain`
to the intended site domain before importing marked images.

## Collections and page bindings

Edit `config/media.manifest.yaml` from
[`config/media.manifest.example.yaml`](../config/media.manifest.example.yaml).
Collections may nest and may render as a gallery or ordered sequence. Use
zero-padded names such as `00001.jpg`; 10,000 items in one folder is a warning,
not a hard rejection. If a sequence listing is hidden, its first ordered item
is the representative image and remains part of the sequence.

Comic defaults are right-to-left, single page, page 1 on the right. A collection
may override reading direction, opening side, and optional two-page spread.
Navigation uses `Next` / `Prev` by default, including Japanese, and can be
localized per collection. The static output uses ordinary links and no
page-turn JavaScript.

Logical-page bindings use stable `page_id` values and can provide a background,
page-header image, or multiple heading-level illustrations. Illustrations
default to right alignment and can be set left. Locale pages share the same
asset unless an explicit locale override is added. HTML Masters must opt into
insertion with exact comments such as
`<!-- HADA:MEDIA-SLOT page-header -->` or
`<!-- HADA:MEDIA-SLOT illustration:preparation -->`; unmarked HTML remains
unchanged.

Videos use native browser controls and a direct-file fallback. PDF previews use
the browser's native viewer when available and always include an ordinary
download/open link. Audio is reserved for future extension and has no player in
this release.

## v0.3 migration

The legacy image registry can be converted to a separate review candidate:

```powershell
python tools/core/media_library.py migrate-legacy --root . --apply
```

This writes `config/media.manifest.v0.4.yaml` and preserves the source manifest.
Review the candidate, verify page bindings and derivatives, then merge manually.
The operation never changes publication HTML or deletes any file. The v0.4.0
data model is new and may require migration; stop for `REVIEW_REQUIRED` when
ownership or source paths are ambiguous.
