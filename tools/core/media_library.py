#!/usr/bin/env python3
"""Validate and render static, media-neutral collection pages."""

from __future__ import annotations

import argparse
import html
import re
import shutil
import sys
from pathlib import Path
from typing import Any

import yaml

MEDIA_TYPES = {"image", "video", "document"}
NATURAL_PARTS = re.compile(r"(\d+)")
MANIFEST = Path("config/media.manifest.yaml")


def safe_path(root: Path, value: str) -> Path:
    candidate = Path(value)
    if candidate.is_absolute() or ".." in candidate.parts:
        raise ValueError(f"unsafe media path: {value}")
    resolved = (root / candidate).resolve()
    if not resolved.is_relative_to(root.resolve()):
        raise ValueError(f"media path escapes repository: {value}")
    return resolved


def natural_key(value: str) -> tuple[Any, ...]:
    return tuple(int(part) if part.isdigit() else part.casefold() for part in NATURAL_PARTS.split(value))


def localized(value: Any, locale: str, fallback: str = "") -> str:
    if isinstance(value, dict):
        return str(value.get(locale) or value.get("en") or value.get("jp") or next(iter(value.values()), fallback))
    return str(value) if value is not None else fallback


def effective_processing(catalog: dict[str, Any], media: dict[str, Any], collection: dict[str, Any] | None = None) -> dict[str, bool]:
    """Resolve processing flags by specificity: global, type, collection, asset."""
    policy = catalog.get("processing", {}) or {}
    result = {"metadata_strip": True, "embedded_signal_transform": False, "domain_mark": True}
    result.update(policy.get("defaults", {}) or {})
    result.update((policy.get("by_type", {}) or {}).get(str(media.get("type", "")), {}) or {})
    if collection:
        result.update(collection.get("processing", {}) or {})
    result.update(media.get("processing", {}) or {})
    return result


def load_catalog(root: Path) -> dict[str, Any]:
    path = root / MANIFEST
    if not path.is_file():
        return {"schema_version": "0.2", "media": [], "collections": []}
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        raise ValueError("media manifest must be a mapping")
    data.setdefault("media", [])
    data.setdefault("collections", [])
    if not isinstance(data["media"], list) or not isinstance(data["collections"], list):
        raise ValueError("media and collections must be lists")
    return data


def collections_flat(collections: list[dict[str, Any]]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for item in collections:
        if not isinstance(item, dict):
            raise ValueError("collection entry must be a mapping")
        result.append(item)
        children = item.get("children", [])
        if not isinstance(children, list):
            raise ValueError(f"collection children must be a list: {item.get('collection_id', '')}")
        result.extend(collections_flat(children))
    return result


def validate_catalog(root: Path) -> list[str]:
    catalog = load_catalog(root)
    errors: list[str] = []
    media_by_id: dict[str, dict[str, Any]] = {}
    for item in catalog["media"]:
        if not isinstance(item, dict):
            errors.append("media entry must be a mapping")
            continue
        media_id = str(item.get("media_id", ""))
        if not media_id or media_id in media_by_id:
            errors.append(f"missing or duplicate media_id: {media_id}")
        media_by_id[media_id] = item
        if item.get("type") not in MEDIA_TYPES:
            errors.append(f"unsupported media type for {media_id}: {item.get('type')}")
        flags = effective_processing(catalog, item)
        for flag in ("metadata_strip", "embedded_signal_transform", "domain_mark"):
            if not isinstance(flags.get(flag), bool):
                errors.append(f"processing.{flag} must be boolean: {media_id}")
        if flags.get("embedded_signal_transform"):
            errors.append(f"embedded signal transformation is not implemented in v0.4.0: {media_id}")
        public_file = item.get("public_file")
        if not isinstance(public_file, str) or not public_file:
            errors.append(f"missing public_file: {media_id}")
        else:
            try:
                target = safe_path(root, public_file)
                if not target.is_file():
                    errors.append(f"missing public media file: {media_id}")
                if "master" in target.parts or "inbox" in target.parts:
                    errors.append(f"public media points to private source/master: {media_id}")
            except ValueError as exc:
                errors.append(str(exc))
        source = item.get("source") or {}
        if isinstance(source, dict) and source.get("visibility", "private") != "private":
            errors.append(f"v0.4.0 does not permit source publication: {media_id}")
        if isinstance(source, dict) and source.get("file"):
            project_config = root / "config" / "project.yaml"
            project = yaml.safe_load(project_config.read_text(encoding="utf-8")) if project_config.is_file() else {}
            publication = str((((project or {}).get("paths") or {}).get("publication_root", "site"))).strip("/\\")
            source_path = str(source["file"]).replace("\\", "/").lstrip("/")
            if source_path == publication or source_path.startswith(publication + "/"):
                errors.append(f"private source is inside publication root: {media_id}")
        thumbnail = item.get("thumbnail")
        if thumbnail:
            try:
                if not safe_path(root, str(thumbnail)).is_file():
                    errors.append(f"missing thumbnail: {media_id}")
            except ValueError as exc:
                errors.append(str(exc))
    try:
        collections = collections_flat(catalog["collections"])
    except ValueError as exc:
        return errors + [str(exc)]
    collection_ids: set[str] = set()
    routes: set[str] = set()
    for collection in collections:
        collection_id = str(collection.get("collection_id", ""))
        route = str(collection.get("route", "")).strip("/")
        if not collection_id or collection_id in collection_ids:
            errors.append(f"missing or duplicate collection_id: {collection_id}")
        collection_ids.add(collection_id)
        if not route or route.startswith(".") or ".." in Path(route).parts:
            errors.append(f"invalid collection route: {collection_id}")
        if route in routes:
            errors.append(f"duplicate collection route: {route}")
        routes.add(route)
        mode = collection.get("presentation", "gallery")
        if mode not in {"gallery", "sequence"}:
            errors.append(f"invalid presentation for {collection_id}: {mode}")
        listing = collection.get("listing", {})
        if not isinstance(listing, dict) or not isinstance(listing.get("enabled", True), bool):
            errors.append(f"listing.enabled must be boolean: {collection_id}")
        sequence = collection.get("sequence", {}) or {}
        if sequence.get("reading_direction", "rtl") not in {"rtl", "ltr"}:
            errors.append(f"invalid reading direction: {collection_id}")
        if sequence.get("first_page_side", "right") not in {"left", "right"}:
            errors.append(f"invalid first page side: {collection_id}")
        if sequence.get("view", "single") not in {"single", "spread"}:
            errors.append(f"invalid sequence view: {collection_id}")
        media_ids = collection.get("media_ids", [])
        if not isinstance(media_ids, list):
            errors.append(f"media_ids must be a list: {collection_id}")
            continue
        if len(media_ids) >= 10000:
            print(f"MEDIA-WARNING collection {collection_id} has {len(media_ids)} listed items (10,000 soft limit)")
        for media_id in media_ids:
            if media_id not in media_by_id:
                errors.append(f"unknown media_id {media_id} in {collection_id}")
    bindings = catalog.get("page_bindings", [])
    if not isinstance(bindings, list):
        errors.append("page_bindings must be a list")
    else:
        for binding in bindings:
            if not isinstance(binding, dict):
                errors.append("page binding must be a mapping")
                continue
            page_id = str(binding.get("page_id", ""))
            role = str(binding.get("role", ""))
            if not page_id:
                errors.append("page binding requires page_id")
            if role not in {"background", "page_header", "illustration", "gallery"}:
                errors.append(f"invalid page media role: {role}")
            ids = binding.get("media_ids", [])
            if isinstance(binding.get("media_id"), str):
                ids = [binding["media_id"]]
            if not isinstance(ids, list):
                errors.append(f"page binding media_ids must be a list: {page_id}")
                continue
            for media_id in ids:
                item = media_by_id.get(str(media_id))
                if item is None:
                    errors.append(f"unknown media_id {media_id} in page binding {page_id}")
                elif role in {"background", "page_header", "illustration"} and item.get("type") != "image":
                    errors.append(f"page visual binding requires image media: {media_id}")
            if role == "illustration":
                if not binding.get("heading_id"):
                    errors.append(f"illustration binding requires heading_id: {page_id}")
                if binding.get("align", "right") not in {"left", "right"}:
                    errors.append(f"invalid illustration alignment: {page_id}")
    return errors


def _collection_media(root: Path, collection: dict[str, Any], media: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    ids = collection.get("media_ids", [])
    items = [media[media_id] for media_id in ids if media_id in media]
    directory = collection.get("source_directory")
    if directory:
        folder = safe_path(root, str(directory))
        if not folder.is_dir():
            raise ValueError(f"missing collection source directory: {directory}")
        indexed = {str(Path(str(item.get("public_file", ""))).as_posix()): item for item in media.values()}
        for path in sorted(folder.iterdir(), key=lambda p: natural_key(p.name)):
            if path.is_file():
                key = path.relative_to(root).as_posix()
                if key in indexed and indexed[key] not in items:
                    items.append(indexed[key])
    order = collection.get("sequence", {}).get("order", "filename")
    if order == "filename":
        items.sort(key=lambda item: natural_key(Path(str(item.get("public_file", ""))).name))
    return items


def _asset_href(item: dict[str, Any]) -> str:
    return "/" + str(item["public_file"]).replace("\\", "/").lstrip("/")


def page_media(root: Path, page_id: str, locale: str) -> dict[str, Any]:
    """Resolve shared logical-page bindings without modifying source masters."""
    catalog = load_catalog(root)
    media = {str(item.get("media_id")): item for item in catalog["media"] if isinstance(item, dict)}
    result: dict[str, Any] = {"background": None, "header": "", "illustrations": {}}
    bindings = catalog.get("page_bindings", [])
    if not isinstance(bindings, list):
        raise ValueError("page_bindings must be a list")
    for binding in bindings:
        if not isinstance(binding, dict) or str(binding.get("page_id", "")) != page_id:
            continue
        if binding.get("locale") not in (None, "", locale):
            continue
        role = str(binding.get("role", ""))
        ids = binding.get("media_ids", [])
        if isinstance(binding.get("media_id"), str):
            ids = [binding["media_id"]]
        if not isinstance(ids, list):
            raise ValueError(f"page binding media_ids must be a list: {page_id}")
        items = [media[str(media_id)] for media_id in ids if str(media_id) in media and media[str(media_id)].get("status") == "approved"]
        for item in items:
            if item.get("type") != "image":
                raise ValueError(f"page visual binding requires image media: {item.get('media_id')}")
        if role == "background" and items and result["background"] is None:
            result["background"] = _asset_href(items[0])
        elif role == "page_header":
            for item in items:
                title = localized(item.get("title"), locale, page_id)
                alt = localized(item.get("alt"), locale, title)
                result["header"] += f'<figure class="page-header-visual"><img src="{html.escape(_asset_href(item), quote=True)}" alt="{html.escape(alt, quote=True)}"></figure>\n'
        elif role == "illustration":
            heading_id = str(binding.get("heading_id", ""))
            if not heading_id:
                raise ValueError(f"illustration binding requires heading_id: {page_id}")
            align = str(binding.get("align", "right"))
            if align not in {"left", "right"}:
                raise ValueError(f"invalid illustration alignment: {align}")
            markup = result["illustrations"].setdefault(heading_id, "")
            for item in items:
                alt = localized(item.get("alt"), locale, "")
                caption = localized(item.get("caption"), locale, "")
                markup += f'<figure class="page-illustration align-{align}"><img src="{html.escape(_asset_href(item), quote=True)}" alt="{html.escape(alt, quote=True)}">'
                if caption:
                    markup += f'<figcaption>{html.escape(caption)}</figcaption>'
                markup += "</figure>\n"
            result["illustrations"][heading_id] = markup
        elif role not in {"gallery"}:
            raise ValueError(f"unsupported page media role: {role}")
    return result


def inject_inline_media(rendered_html: str, illustrations: dict[str, str]) -> str:
    for heading_id, markup in illustrations.items():
        escaped_id = re.escape(heading_id)
        pattern = re.compile(rf'(<h[2-6]\b[^>]*\bid="{escaped_id}"[^>]*>.*?</h[2-6]>)', re.IGNORECASE | re.DOTALL)
        rendered_html, count = pattern.subn(r"\1\n" + markup, rendered_html, count=1)
        if count != 1:
            raise ValueError(f"could not find Markdown heading id for illustration: {heading_id}")
    return rendered_html


def fill_html_master_slots(root: Path, page_id: str, locale: str, source: str) -> str:
    """Replace only explicit HADA media slot comments in an HTML Master."""
    resolved = page_media(root, page_id, locale)
    output = source.replace("<!-- HADA:MEDIA-SLOT page-header -->", resolved["header"])
    if resolved["background"]:
        output = output.replace("<!-- HADA:MEDIA-SLOT background -->", f'<div class="page-background-visual" aria-hidden="true" style="background-image:url(\'{html.escape(resolved["background"], quote=True)}\')"></div>')
    for heading_id, markup in resolved["illustrations"].items():
        output = output.replace(f"<!-- HADA:MEDIA-SLOT illustration:{heading_id} -->", markup)
    return output


def _preview(item: dict[str, Any], title: str, alt: str, root: Path) -> str:
    kind = item["type"]
    href = html.escape(_asset_href(item), quote=True)
    if kind == "image":
        return f'<img src="{href}" alt="{html.escape(alt, quote=True)}" loading="lazy">'
    if kind == "video":
        poster = f' poster="/{html.escape(str(item["thumbnail"]).lstrip("/"), quote=True)}"' if item.get("thumbnail") else ""
        return f'<video controls preload="metadata"{poster}><source src="{href}"></video><p><a href="{href}">Open or download video: {html.escape(title)}</a></p>'
    if kind == "document" and str(item.get("format", "pdf")).lower() == "pdf":
        thumb = item.get("thumbnail")
        preview = f'<img src="/{html.escape(str(thumb).lstrip("/"), quote=True)}" alt="" loading="lazy">' if thumb else ""
        return f'<object data="{href}" type="application/pdf" aria-label="{html.escape(title, quote=True)}"><p>PDF preview is not available. <a href="{href}">Open or download {html.escape(title)}</a>.</p></object>{preview}<p><a href="{href}">Open or download PDF: {html.escape(title)}</a></p>'
    return f'<p><a href="{href}">Open or download {html.escape(title)}</a></p>'


def _page_shell(locale: str, title: str, body: str, extra_css: str = "", direction: str = "ltr") -> str:
    return ("<!doctype html>\n<html lang=\"{lang}\"><head><meta charset=\"utf-8\">"
            "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\"><title>{title}</title>"
            "<style>body{{max-width:1100px;margin:2rem auto;padding:0 1rem;font-family:system-ui,sans-serif}}"
            "a{{color:inherit}}.items{{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:1rem}}"
            "img,video,object{{max-width:100%;height:auto}}.spread{{display:grid;grid-template-columns:1fr 1fr;gap:0;direction:ltr}}"
            ".spread img{{width:100%;max-height:85vh;object-fit:contain}}.nav{{display:flex;justify-content:space-between;margin:1rem 0}}"
            "@media(max-width:700px){{.spread{{grid-template-columns:1fr}}}}{css}</style></head>"
            "<body data-ui-profile=\"standalone\"><main dir=\"{direction}\"><h1>{title}</h1>{body}</main></body></html>\n").format(
                lang=html.escape(locale, quote=True), title=html.escape(title), body=body, css=extra_css,
                direction=html.escape(direction if direction in {"ltr", "rtl"} else "ltr", quote=True))


def build_media_library(root: Path, output: Path, locales: list[str]) -> int:
    catalog = load_catalog(root)
    if not catalog["media"] or not catalog["collections"]:
        return 0
    errors = validate_catalog(root)
    if errors:
        raise ValueError("Media catalog validation failed: " + "; ".join(errors))
    media = {str(item["media_id"]): item for item in catalog["media"]}
    collections = collections_flat(catalog["collections"])
    # Publish only approved public representations; source/master paths are never copied.
    published: set[str] = set()
    for item in media.values():
        if item.get("status") != "approved":
            continue
        for field in ("public_file", "thumbnail"):
            if not item.get(field):
                continue
            rel = str(item[field])
            if rel in published:
                continue
            source = safe_path(root, rel)
            target = output / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
            published.add(rel)
    for collection in collections:
        route = str(collection["route"]).strip("/")
        for locale in locales:
            page_root = output / locale / route
            page_root.mkdir(parents=True, exist_ok=True)
            title = localized(collection.get("title"), locale, str(collection["collection_id"]))
            items = [item for item in _collection_media(root, collection, media) if item.get("status") == "approved"]
            if len(items) >= 10000:
                print(f"MEDIA-WARNING {collection['collection_id']}: 10,000 items soft limit")
            listing_enabled = (collection.get("listing") or {}).get("enabled", True)
            presentation = collection.get("presentation", "gallery")
            if presentation == "sequence":
                sequence = collection.get("sequence", {}) or {}
                spread = sequence.get("view", "single") == "spread" and sequence.get("spread_enabled", True)
                groups = [items[i:i + (2 if spread else 1)] for i in range(0, len(items), 2 if spread else 1)]
                side = sequence.get("first_page_side", "right")
                next_label = localized((sequence.get("labels") or {}).get("locales", {}).get(locale, {}).get("next"), locale, str((sequence.get("labels") or {}).get("next", "Next")))
                prev_label = localized((sequence.get("labels") or {}).get("locales", {}).get(locale, {}).get("previous"), locale, str((sequence.get("labels") or {}).get("previous", "Prev")))
                cards: list[str] = []
                for group_index, group in enumerate(groups):
                    filename = f"page-{group_index + 1:05d}.html"
                    href = f"/{locale}/{route}/{filename}"
                    for item in group:
                        label = localized(item.get("title"), locale, Path(str(item["public_file"])).stem)
                        thumb = item.get("thumbnail") or item["public_file"]
                        cards.append(f'<a href="{html.escape(href, quote=True)}"><img src="/{html.escape(str(thumb).lstrip("/"), quote=True)}" alt=""><span>{html.escape(label)}</span></a>')
                    panels = []
                    for offset, item in enumerate(group):
                        label = localized(item.get("title"), locale, Path(str(item["public_file"])).stem)
                        alt = localized(item.get("alt"), locale, "")
                        preview = _preview(item, label, alt, root)
                        actual_side = side if offset == 0 else ("left" if side == "right" else "right")
                        panels.append((actual_side, f'<figure>{preview}<figcaption>{html.escape(label)}</figcaption></figure>'))
                    if spread:
                        empty = '<div aria-hidden="true"></div>' if len(panels) == 1 else ""
                        ordered = {place: value for place, value in panels}
                        left = ordered.get("left", empty)
                        right = ordered.get("right", empty)
                        content = f'<div class="spread">{left}{right}</div>'
                    else:
                        content = "".join(value for _, value in panels)
                    prev_href = f"/{locale}/{route}/page-{group_index:05d}.html" if group_index > 0 else ""
                    next_href = f"/{locale}/{route}/page-{group_index + 2:05d}.html" if group_index + 1 < len(groups) else ""
                    nav = '<nav class="nav" aria-label="Sequence navigation">'
                    nav += f'<a rel="prev" href="{prev_href}">{html.escape(prev_label)}</a>' if prev_href else "<span></span>"
                    nav += f'<a rel="next" href="{next_href}">{html.escape(next_label)}</a>' if next_href else ""
                    nav += "</nav>"
                    body = f'<p><a href="/{locale}/{route}/">{html.escape(title)}</a></p>{nav}{content}{nav}'
                    (page_root / filename).write_text(_page_shell(locale, title, body, direction=str(sequence.get("reading_direction", "rtl"))), encoding="utf-8", newline="\r\n")
                if listing_enabled:
                    index_body = '<div class="items">' + "".join(cards) + "</div>"
                elif groups:
                    index_body = f'<p><a href="/{locale}/{route}/page-00001.html">Open collection</a></p>' + _preview(groups[0][0], title, localized(groups[0][0].get("alt"), locale, ""), root)
                else:
                    index_body = "<p>No media is available.</p>"
            else:
                cards = []
                for item in items:
                    label = localized(item.get("title"), locale, Path(str(item["public_file"])).stem)
                    alt = localized(item.get("alt"), locale, "")
                    thumb = item.get("thumbnail") or item["public_file"]
                    cards.append(f'<figure><img src="/{html.escape(str(thumb).lstrip("/"), quote=True)}" alt="{html.escape(alt, quote=True)}"><figcaption>{html.escape(label)} — {html.escape(item["type"])}</figcaption>{_preview(item, label, alt, root)}</figure>')
                index_body = '<div class="items">' + "".join(cards) + "</div>" if listing_enabled else (_preview(items[0], title, localized(items[0].get("alt"), locale, ""), root) if items else "<p>No media is available.</p>")
            children = collection.get("children", [])
            if children:
                child_links = []
                for child in children:
                    child_title = localized(child.get("title"), locale, str(child.get("collection_id", "Collection")))
                    child_route = str(child.get("route", "")).strip("/")
                    child_links.append(f'<li><a href="/{locale}/{html.escape(child_route, quote=True)}/">{html.escape(child_title)}</a></li>')
                index_body += '<nav aria-label="Child collections"><ul>' + "".join(child_links) + "</ul></nav>"
            (page_root / "index.html").write_text(_page_shell(locale, title, index_body), encoding="utf-8", newline="\r\n")
    return 0


def migration_plan(root: Path) -> dict[str, Any]:
    """Translate legacy image records into a separate, review-only v0.4 file."""
    legacy = load_catalog(root)
    legacy_images = legacy.get("images", [])
    if not isinstance(legacy_images, list):
        raise ValueError("legacy images must be a list")
    media: list[dict[str, Any]] = []
    gallery_ids: list[str] = []
    warnings: list[str] = []
    for old in legacy_images:
        if not isinstance(old, dict):
            warnings.append("Ignored non-mapping legacy image entry; manual review required")
            continue
        media_id = str(old.get("image_id", ""))
        if not media_id:
            warnings.append("Legacy image missing image_id; manual review required")
            continue
        record = {
            "media_id": media_id,
            "type": "image",
            "source": {"file": old.get("master"), "visibility": "private", "origin": old.get("source", "user")},
            "public_file": old.get("web"),
            "thumbnail": old.get("thumbnail"),
            "status": old.get("status", "pending"),
            "legacy_usage": old.get("usage", []),
        }
        for key in ("title", "alt", "caption", "credit"):
            if key in old:
                record[key] = old[key]
        record["processing"] = {
            "metadata_strip": True,
            "embedded_signal_transform": False,
            "domain_mark": True,
            "migration_note": "Verify the existing derivative; policy values do not certify historical processing.",
        }
        media.append(record)
        usage = old.get("usage", [])
        usages = {str(usage)} if isinstance(usage, str) else {str(value) for value in usage}
        if "gallery" in usages or (old.get("gallery") or {}).get("visible") is True:
            gallery_ids.append(media_id)
    collections = []
    if gallery_ids:
        collections.append({
            "collection_id": "migrated-image-gallery",
            "route": "gallery",
            "title": {"en": "Gallery", "jp": "Gallery"},
            "presentation": "gallery",
            "listing": {"enabled": True},
            "media_ids": gallery_ids,
        })
    warnings.append("Review page-scoped background bindings, routes, provenance and derivatives before merging this file into config/media.manifest.yaml.")
    return {"schema_version": "0.2", "media": media, "collections": collections, "migration": {"from": str(legacy.get("schema_version", "unknown")), "warnings": warnings}}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("validate", "build", "migrate-legacy"))
    parser.add_argument("--root", default=".")
    parser.add_argument("--output", default="site")
    parser.add_argument("--locales", default="en,jp")
    parser.add_argument("--apply", action="store_true", help="write a separate reviewed migration candidate; never replaces the source manifest")
    args = parser.parse_args(argv)
    root = Path(args.root).resolve()
    try:
        if args.command == "validate":
            errors = validate_catalog(root)
            for error in errors:
                print(f"MEDIA-ERROR {error}")
            print(f"MEDIA-VALIDATION {'failed' if errors else 'passed'} errors={len(errors)}")
            return 1 if errors else 0
        if args.command == "migrate-legacy":
            target = root / "config" / "media.manifest.v0.4.yaml"
            if not args.apply:
                print(yaml.safe_dump(migration_plan(root), allow_unicode=True, sort_keys=False), end="")
                return 0
            if target.exists():
                raise ValueError(f"migration candidate already exists and will not be overwritten: {target}")
            target.write_text(yaml.safe_dump(migration_plan(root), allow_unicode=True, sort_keys=False), encoding="utf-8", newline="\r\n")
            print(f"MIGRATION-CANDIDATE {target}; source manifest preserved")
            return 0
        build_media_library(root, Path(args.output).resolve(), [value.strip() for value in args.locales.split(",") if value.strip()])
        return 0
    except (OSError, ValueError, KeyError) as exc:
        print(f"MEDIA-ERROR {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
