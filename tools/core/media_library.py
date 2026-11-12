#!/usr/bin/env python3
"""Validate and render static, media-neutral collection pages."""

from __future__ import annotations

import argparse
import hashlib
import html
import re
import shutil
import sys
from datetime import date, datetime
from pathlib import Path
from typing import Any

import json
from structured_data import load_document
from display_config import display_runtime_settings

try:
    from PIL import Image
except ImportError:  # metadata date sorting remains usable without the optional image library
    Image = None

MEDIA_TYPES = {"image", "video", "document"}
NATURAL_PARTS = re.compile(r"(\d+)")
MANIFEST = Path("config/media.catalog.json")
VIEWER_JS = Path(__file__).with_name("media-viewer.js")
VIEWER_CSS = Path(__file__).with_name("media-viewer.css")

DEFAULT_VIEWER_LABELS: dict[str, dict[str, str]] = {
    "en": {
        "open": "Open image", "close": "Close", "previous": "Previous image",
        "next": "Next image", "fit": "Fit to screen", "actual": "Actual size",
        "fullscreen": "Fullscreen", "single": "Single page", "manga": "Spread",
        "first_right": "Page 1 right", "first_left": "Page 1 left",
    },
    "jp": {
        "open": "画像を開く", "close": "閉じる", "previous": "戻る",
        "next": "次へ", "fit": "画面に合わせる", "actual": "等倍",
        "fullscreen": "全画面", "single": "単ページ", "manga": "見開き",
        "first_right": "1ページ目を右", "first_left": "1ページ目を左",
    },
    "de": {
        "open": "Bild öffnen", "close": "Schließen", "previous": "Vorheriges Bild",
        "next": "Nächstes Bild", "fit": "An Bildschirm anpassen", "actual": "Originalgröße",
        "fullscreen": "Vollbild", "single": "Einzelseite", "manga": "Doppelseite",
        "first_right": "Seite 1 rechts", "first_left": "Seite 1 links",
    },
}

DEFAULT_SEQUENCE_LABELS = {
    "jp": {"next": "次へ", "previous": "前へ"},
    "en": {"next": "Next", "previous": "Previous"},
    "de": {"next": "Weiter", "previous": "Zurück"},
}

COLLECTION_UI_LABELS = {
    "jp": {"sequence": "ページナビゲーション", "children": "下位コレクション", "open": "コレクションを開く", "empty": "メディアがありません", "sort_by": "並べ替え", "sort_order": "順序", "name": "名前", "publication_date": "出版日", "updated_date": "更新日", "ascending": "昇順", "descending": "降順"},
    "en": {"sequence": "Sequence navigation", "children": "Child collections", "open": "Open collection", "empty": "No media is available", "sort_by": "Sort by", "sort_order": "Order", "name": "Name", "publication_date": "Publication date", "updated_date": "Updated date", "ascending": "Ascending", "descending": "Descending"},
    "de": {"sequence": "Seitennavigation", "children": "Untergeordnete Sammlungen", "open": "Sammlung öffnen", "empty": "Keine Medien verfügbar", "sort_by": "Sortieren nach", "sort_order": "Reihenfolge", "name": "Name", "publication_date": "Veröffentlichungsdatum", "updated_date": "Aktualisierungsdatum", "ascending": "Aufsteigend", "descending": "Absteigend"},
}


def safe_path(root: Path, value: str) -> Path:
    candidate = Path(value)
    if candidate.is_absolute() or ".." in candidate.parts:
        raise ValueError(f"unsafe media path: {value}")
    resolved = (root / candidate).resolve()
    if not resolved.is_relative_to(root.resolve()):
        raise ValueError(f"media path escapes repository: {value}")
    return resolved


def valid_collection_route(value: str) -> bool:
    route = value.strip("/")
    if not route or route.startswith(".") or "\\" in route:
        return False
    reserved = {"CON", "PRN", "AUX", "NUL", *(f"COM{i}" for i in range(1, 10)), *(f"LPT{i}" for i in range(1, 10))}
    for part in route.split("/"):
        if (part in {"", ".", ".."} or part.endswith((".", " "))
                or any(ord(char) < 32 or char in '<>:"|?*' for char in part)
                or part.split(".", 1)[0].upper() in reserved):
            return False
    return True


def build_spread_plan(page_count: int, first_page_side: str = "right",
                      reading_direction: str = "rtl") -> list[dict[str, int | None]]:
    """Return visual right/left page indexes without duplicating logical pages."""
    if page_count < 0 or first_page_side not in {"left", "right"} or reading_direction not in {"rtl", "ltr"}:
        raise ValueError("invalid spread plan parameters")
    leading_side = "right" if reading_direction == "rtl" else "left"
    trailing_side = "left" if leading_side == "right" else "right"
    frames: list[dict[str, int | None]] = []
    index = 0
    if page_count and first_page_side != leading_side:
        frame: dict[str, int | None] = {"right": None, "left": None}
        frame[first_page_side] = 0
        frames.append(frame)
        index = 1
    while index < page_count:
        frame = {"right": None, "left": None}
        frame[leading_side] = index
        index += 1
        if index < page_count:
            frame[trailing_side] = index
            index += 1
        frames.append(frame)
    return frames


def natural_key(value: str) -> tuple[Any, ...]:
    return tuple(int(part) if part.isdigit() else part.casefold() for part in NATURAL_PARTS.split(value))


def localized(value: Any, locale: str, fallback: str = "") -> str:
    if isinstance(value, dict):
        return str(value.get(locale) or value.get("en") or value.get("jp") or next(iter(value.values()), fallback))
    return str(value) if value is not None else fallback


def effective_processing(catalog: dict[str, Any], media: dict[str, Any], collection: dict[str, Any] | None = None) -> dict[str, Any]:
    """Resolve processing flags by specificity: global, type, collection, asset."""
    policy = catalog.get("processing", {}) or {}
    result: dict[str, Any] = {"metadata_strip": True, "embedded_signal_transform": False, "domain_mark": True}
    watermark: dict[str, Any] = dict(policy.get("domain_mark_style", {}) or {})
    watermark_configured = False
    watermark_enabled_explicit = False
    layers = [policy.get("defaults", {}) or {},
              (policy.get("by_type", {}) or {}).get(str(media.get("type", "")), {}) or {},
              (collection or {}).get("processing", {}) or {}, media.get("processing", {}) or {}]
    for layer in layers:
        for key, value in layer.items():
            if key == "watermark" and isinstance(value, dict):
                watermark.update(value)
                watermark_configured = True
                watermark_enabled_explicit |= "enabled" in value
            else:
                result[key] = value
    if watermark_configured or policy.get("domain_mark_style"):
        if not watermark_enabled_explicit:
            watermark["enabled"] = bool(result.get("domain_mark"))
        result["watermark"] = {"type": "text", "text_source": "domain", "position": "bottom-left",
                               "opacity": 0.88, "scale_ratio": 0.12, "margin_ratio": 0.025, **watermark}
    return result


def load_catalog(root: Path) -> dict[str, Any]:
    path = root / MANIFEST
    if not path.is_file():
        return {"schema_version": "0.3", "media": [], "collections": [], "page_bindings": [], "processing": {}}
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("media catalog must be a JSON object")
    if data.get("schema_version") != "0.3":
        raise ValueError("unsupported media catalog schema_version; expected 0.3 JSON")
    if "images" in data:
        raise ValueError("legacy parallel images list is not supported; use the media array")
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


def collections_with_ancestors(collections: list[dict[str, Any]]) -> list[tuple[dict[str, Any], list[dict[str, Any]]]]:
    result: list[tuple[dict[str, Any], list[dict[str, Any]]]] = []
    def walk(nodes: list[dict[str, Any]], ancestors: list[dict[str, Any]]) -> None:
        for node in nodes:
            if not isinstance(node, dict):
                raise ValueError("collection entry must be a mapping")
            result.append((node, ancestors))
            children = node.get("children", [])
            if not isinstance(children, list):
                raise ValueError(f"collection children must be a list: {node.get('collection_id', '')}")
            walk(children, [*ancestors, node])
    walk(collections, [])
    return result


def _breadcrumbs(locale: str, ancestors: list[dict[str, Any]], output: Path,
                 media_route: str = "media") -> str:
    labels = {"jp": "ホーム", "en": "Home", "de": "Startseite"}
    home = output / locale / "index.html"
    parts = ([f'<li><a href="/{html.escape(locale, quote=True)}/">{labels.get(locale, labels["en"])}</a></li>']
             if home.is_file() else [])
    library_index = output / locale / media_route / "index.html"
    media_labels = {"jp": "メディア", "en": "Media", "de": "Medien"}
    if library_index.is_file():
        parts.append(f'<li><a href="/{html.escape(locale, quote=True)}/{html.escape(media_route, quote=True)}/">'
                     f'{html.escape(media_labels.get(locale, "Media"))}</a></li>')
    for ancestor in ancestors:
        title = localized(ancestor.get("title"), locale, str(ancestor.get("collection_id", "Collection")))
        route = str(ancestor.get("route", "")).strip("/")
        parts.append(f'<li><a href="/{html.escape(locale, quote=True)}/{html.escape(route, quote=True)}/">{html.escape(title)}</a></li>')
    nav_label = {"jp": "パンくずリスト", "en": "Breadcrumb", "de": "Brotkrumennavigation"}.get(locale, "Breadcrumb")
    return f'<nav aria-label="{html.escape(nav_label, quote=True)}"><ol class="breadcrumbs">' + "".join(parts) + '</ol></nav>'


def _collection_ui(locale: str) -> dict[str, str]:
    return COLLECTION_UI_LABELS.get(locale, COLLECTION_UI_LABELS["en"])


def validate_catalog(root: Path) -> list[str]:
    catalog = load_catalog(root)
    errors: list[str] = []

    def validate_processing(policy: dict[str, Any], label: str) -> None:
        if policy.get("output_format", "jpeg") not in {"jpeg", "webp"}:
            errors.append(f"processing.output_format must be jpeg or webp: {label}")
        quality = policy.get("quality", 88)
        minimum = policy.get("minimum_quality", 55)
        if (not isinstance(quality, int) or isinstance(quality, bool) or
                not isinstance(minimum, int) or isinstance(minimum, bool) or not 1 <= minimum <= quality <= 95):
            errors.append(f"processing quality must satisfy 1 <= minimum_quality <= quality <= 95: {label}")
        for key in ("max_width", "max_height", "max_bytes"):
            value = policy.get(key, 0)
            if not isinstance(value, int) or isinstance(value, bool) or value < 0:
                errors.append(f"processing.{key} must be a non-negative integer: {label}")
        watermark = policy.get("watermark", {}) or {}
        if not isinstance(watermark, dict):
            errors.append(f"processing.watermark must be an object: {label}")
            return
        if not isinstance(watermark.get("enabled", policy.get("domain_mark", True)), bool):
            errors.append(f"processing.watermark.enabled must be boolean: {label}")
        if watermark.get("type", "text") not in {"text", "image"}:
            errors.append(f"processing.watermark.type must be text or image: {label}")
        if watermark.get("position", "bottom-left") not in {"bottom-left", "bottom-right", "top-left", "top-right"}:
            errors.append(f"processing.watermark.position is invalid: {label}")
        if watermark.get("text_position", "bottom-right") not in {"bottom-left", "bottom-right", "top-left", "top-right"}:
            errors.append(f"processing.watermark.text_position is invalid: {label}")
        opacity = watermark.get("opacity", 0.88)
        if not isinstance(opacity, (int, float)) or isinstance(opacity, bool) or not 0 <= opacity <= 1:
            errors.append(f"processing.watermark.opacity must be between 0 and 1: {label}")
        logo_opacity = watermark.get("logo_opacity", opacity)
        if not isinstance(logo_opacity, (int, float)) or isinstance(logo_opacity, bool) or not 0 <= logo_opacity <= 1:
            errors.append(f"processing.watermark.logo_opacity must be between 0 and 1: {label}")
        if watermark.get("type", "text") == "text" or watermark.get("text") or watermark.get("include_text"):
            if watermark.get("text_source", "domain") not in {"domain", "text"}:
                errors.append(f"processing.watermark.text_source must be domain or text: {label}")
            if watermark.get("text_source", "domain") == "text" and not str(watermark.get("text", "")).strip():
                errors.append(f"processing.watermark.text is required for text source: {label}")
        if watermark.get("type") == "image" and watermark.get("enabled", policy.get("domain_mark", True)):
            logo = str(watermark.get("logo_file", ""))
            try:
                logo_path = safe_path(root, logo)
                if not logo_path.is_relative_to((root / "assets/media/master/watermarks").resolve()):
                    errors.append(f"watermark logo must remain under assets/media/master/watermarks: {label}")
                elif not logo_path.is_file():
                    errors.append(f"watermark logo file is missing: {label}")
            except ValueError:
                errors.append(f"watermark logo path is unsafe: {label}")
        for key, default in (("scale_ratio", 0.12), ("margin_ratio", 0.025)):
            value = watermark.get(key, default)
            if not isinstance(value, (int, float)) or isinstance(value, bool) or not 0 < value <= 0.5:
                errors.append(f"processing.watermark.{key} must be greater than 0 and at most 0.5: {label}")

    validate_processing(effective_processing(catalog, {"type": "image"}), "catalog defaults")
    try:
        configured_collections = collections_flat(catalog.get("collections", []))
    except ValueError as exc:
        errors.append(str(exc))
        configured_collections = []
    for collection in configured_collections:
        validate_processing(effective_processing(catalog, {"type": "image"}, collection),
                            str(collection.get("collection_id", "collection")))
        sequence_config = collection.get("sequence") or {}
        order = sequence_config.get("order", "filename") if isinstance(sequence_config, dict) else None
        if order not in {"filename", "manual", "modified_asc", "modified_desc", "capture_time_asc", "capture_time_desc"}:
            errors.append(f"unsupported image sequence order: {collection.get('collection_id', '')}")
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
        validate_processing(flags, media_id)
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
                if item.get("type") == "image" and target.suffix.lower() not in {".jpg", ".jpeg", ".webp"}:
                    errors.append(f"public image derivative must use JPEG or WebP, not PNG: {media_id}")
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
            project_config = root / "config" / "project.toml"
            project = load_document(project_config) if project_config.is_file() else {}
            publication = str((((project or {}).get("paths") or {}).get("publication_root", "site"))).strip("/\\")
            source_path = str(source["file"]).replace("\\", "/").lstrip("/")
            if source_path == publication or source_path.startswith(publication + "/"):
                errors.append(f"private source is inside publication root: {media_id}")
        thumbnail = item.get("thumbnail")
        if thumbnail:
            try:
                thumbnail_path = safe_path(root, str(thumbnail))
                if item.get("type") == "image" and thumbnail_path.suffix.lower() not in {".jpg", ".jpeg", ".webp"}:
                    errors.append(f"image thumbnail must use JPEG or WebP: {media_id}")
                if not thumbnail_path.is_file():
                    errors.append(f"missing thumbnail: {media_id}")
            except ValueError as exc:
                errors.append(str(exc))
    try:
        collections = collections_flat(catalog["collections"])
    except ValueError as exc:
        return errors + [str(exc)]
    collection_ids: set[str] = set()
    routes: set[str] = set()
    empty_route_count = 0
    top_level_ids = {str(item.get("collection_id", "")) for item in catalog["collections"]}
    for collection in collections:
        collection_id = str(collection.get("collection_id", ""))
        route = str(collection.get("route", ""))
        if not collection_id or collection_id in collection_ids:
            errors.append(f"missing or duplicate collection_id: {collection_id}")
        collection_ids.add(collection_id)
        empty_root = not route.strip("/") and collection_id in top_level_ids
        if empty_root:
            empty_route_count += 1
        if not empty_root and not valid_collection_route(route):
            errors.append(f"invalid collection route: {collection_id}")
        if route in routes:
            errors.append(f"duplicate collection route: {route}")
        routes.add(route)
        mode = collection.get("presentation", "gallery")
        if mode not in {"gallery", "sequence"}:
            errors.append(f"invalid presentation for {collection_id}: {mode}")
        for field in ("publication_date", "updated_date"):
            value = collection.get(field)
            if value is not None:
                try:
                    if not isinstance(value, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
                        raise ValueError
                    date.fromisoformat(value)
                except ValueError:
                    errors.append(f"{field} must be a valid YYYY-MM-DD date: {collection_id}")
        listing = collection.get("listing", {})
        if not isinstance(listing, dict) or not isinstance(listing.get("enabled", True), bool):
            errors.append(f"listing.enabled must be boolean: {collection_id}")
        viewer = collection.get("viewer", {})
        if not isinstance(viewer, dict) or not isinstance(viewer.get("enabled", True), bool):
            errors.append(f"viewer.enabled must be boolean: {collection_id}")
        else:
            if viewer.get("labels") is not None and not isinstance(viewer.get("labels"), dict):
                errors.append(f"viewer.labels must be a mapping: {collection_id}")
            modes = viewer.get("modes", ["single"])
            if (not isinstance(modes, list) or not modes
                    or any(not isinstance(mode, str) or mode not in {"single", "manga"} for mode in modes)
                    or len(modes) != len(set(modes))):
                errors.append(f"viewer.modes must be a unique non-empty list of single/manga: {collection_id}")
            else:
                if viewer.get("default_mode", "single") not in modes:
                    errors.append(f"viewer.default_mode must be enabled in viewer.modes: {collection_id}")
                if viewer.get("mobile_default_mode", viewer.get("default_mode", "single")) not in modes:
                    errors.append(f"viewer.mobile_default_mode must be enabled in viewer.modes: {collection_id}")
                if "manga" in modes and mode != "gallery":
                    errors.append(f"manga viewer mode is supported only for gallery collections: {collection_id}")
                if ("manga" in modes
                        and (collection.get("sequence") or {}).get("reading_direction", "rtl") != "rtl"):
                    errors.append(f"manga viewer mode requires right-to-left reading: {collection_id}")
        sequence = collection.get("sequence", {}) or {}
        if sequence.get("reading_direction", "rtl") not in {"rtl", "ltr"}:
            errors.append(f"invalid reading direction: {collection_id}")
        if sequence.get("first_page_side", "right") not in {"left", "right"}:
            errors.append(f"invalid first page side: {collection_id}")
        if sequence.get("view", "single") not in {"single", "spread"}:
            errors.append(f"invalid sequence view: {collection_id}")
        side_options = sequence.get("first_page_side_options")
        if side_options is not None and (not isinstance(side_options, list) or not side_options
                or any(not isinstance(side, str) or side not in {"left", "right"} for side in side_options)
                or len(side_options) != len(set(side_options))
                or sequence.get("first_page_side", "right") not in side_options):
            errors.append(f"invalid first_page_side_options: {collection_id}")
        media_ids = collection.get("media_ids", [])
        if not isinstance(media_ids, list):
            errors.append(f"media_ids must be a list: {collection_id}")
            continue
        if len(media_ids) != len(set(map(str, media_ids))):
            errors.append(f"duplicate media_id in collection {collection_id}")
        if len(media_ids) >= 10000:
            print(f"MEDIA-WARNING collection {collection_id} has {len(media_ids)} listed items (10,000 soft limit)")
        for media_id in media_ids:
            if media_id not in media_by_id:
                errors.append(f"unknown media_id {media_id} in {collection_id}")
            elif isinstance(viewer, dict) and "manga" in viewer.get("modes", []) and media_by_id[media_id].get("type") != "image":
                errors.append(f"manga viewer collections may contain only images: {collection_id}")
    if empty_route_count > 1:
        errors.append("only one top-level collection may use the empty library-root route")
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
            if len(ids) != len(set(map(str, ids))):
                errors.append(f"duplicate media_id in page binding {page_id}")
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
        for path in sorted(folder.rglob("*"), key=lambda p: natural_key(p.relative_to(folder).as_posix())):
            if path.is_file():
                key = path.relative_to(root).as_posix()
                if key in indexed and indexed[key] not in items:
                    items.append(indexed[key])
    order = collection.get("sequence", {}).get("order", "filename")
    if order == "filename":
        items.sort(key=lambda item: natural_key(Path(str(item.get("public_file", ""))).as_posix()))
    elif order in {"modified_asc", "modified_desc", "capture_time_asc", "capture_time_desc"}:
        descending = order.endswith("desc")
        capture_time = order.startswith("capture_time")
        dated: list[tuple[float | datetime, dict[str, Any]]] = []
        undated: list[dict[str, Any]] = []
        for item in items:
            source = item.get("source") or {}
            relative = source.get("file") if isinstance(source, dict) else None
            path = safe_path(root, str(relative or item.get("public_file", "")))
            date_value: float | datetime | None = None
            if path.is_file():
                if capture_time and Image is not None:
                    try:
                        with Image.open(path) as image:
                            exif = image.getexif()
                            raw = exif.get(36867) or exif.get(36868) or exif.get(306)
                        if raw:
                            date_value = datetime.strptime(str(raw), "%Y:%m:%d %H:%M:%S")
                    except (OSError, ValueError, TypeError):
                        date_value = None
                elif not capture_time:
                    date_value = path.stat().st_mtime
            (dated if date_value is not None else undated).append((date_value, item) if date_value is not None else item)
        dated.sort(key=lambda pair: natural_key(Path(str(pair[1].get("public_file", ""))).as_posix()))
        dated.sort(key=lambda pair: pair[0], reverse=descending)
        undated.sort(key=lambda item: natural_key(Path(str(item.get("public_file", ""))).as_posix()))
        items = [item for _, item in dated] + undated
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
                result["header"] += f'<figure class="page-header-visual"><img src="{html.escape(_asset_href(item), quote=True)}" alt="{html.escape(alt, quote=True)}"></figure>\r\n'
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
                markup += "</figure>\r\n"
            result["illustrations"][heading_id] = markup
        elif role not in {"gallery"}:
            raise ValueError(f"unsupported page media role: {role}")
    return result


def inject_inline_media(rendered_html: str, illustrations: dict[str, str]) -> str:
    for heading_id, markup in illustrations.items():
        escaped_id = re.escape(heading_id)
        pattern = re.compile(rf'(<h[2-6]\b[^>]*\bid="{escaped_id}"[^>]*>.*?</h[2-6]>)', re.IGNORECASE | re.DOTALL)
        rendered_html, count = pattern.subn(r"\1\r\n" + markup, rendered_html, count=1)
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


def _preview(item: dict[str, Any], title: str, alt: str, root: Path,
             viewer: dict[str, str] | None = None) -> str:
    kind = item["type"]
    href = html.escape(_asset_href(item), quote=True)
    if kind == "image":
        image = f'<img class="media-protected-image" draggable="false" src="{href}" alt="{html.escape(alt, quote=True)}" loading="lazy">'
        if viewer is None:
            return image
        attributes = " ".join(
            f'data-viewer-{key}="{html.escape(value, quote=True)}"'
            for key, value in viewer.items() if key != "id"
        )
        return (f'<a class="media-viewer-trigger" id="{html.escape(viewer["id"], quote=True)}" '
                f'href="{href}" aria-label="{html.escape(viewer.get("open", title), quote=True)}" '
                f'{attributes}>{image}</a>')
    if kind == "video":
        poster = f' poster="/{html.escape(str(item["thumbnail"]).lstrip("/"), quote=True)}"' if item.get("thumbnail") else ""
        return f'<video controls preload="metadata"{poster}><source src="{href}"></video><p><a href="{href}">Open or download video: {html.escape(title)}</a></p>'
    if kind == "document" and str(item.get("format", "pdf")).lower() == "pdf":
        thumb = item.get("thumbnail")
        preview = f'<img class="media-protected-image" draggable="false" src="/{html.escape(str(thumb).lstrip("/"), quote=True)}" alt="" loading="lazy">' if thumb else ""
        return f'<object data="{href}" type="application/pdf" aria-label="{html.escape(title, quote=True)}"><p>PDF preview is not available. <a href="{href}">Open or download {html.escape(title)}</a>.</p></object>{preview}<p><a href="{href}">Open or download PDF: {html.escape(title)}</a></p>'
    return f'<p><a href="{href}">Open or download {html.escape(title)}</a></p>'


def _viewer_labels(collection: dict[str, Any], locale: str) -> dict[str, str]:
    configured = ((collection.get("viewer") or {}).get("labels") or {}).get("locales", {})
    defaults = DEFAULT_VIEWER_LABELS.get(locale, DEFAULT_VIEWER_LABELS["en"])
    chosen = configured.get(locale, {}) if isinstance(configured, dict) else {}
    return {key: str(chosen.get(key) or defaults[key]) for key in defaults}


def _viewer_shell(labels: dict[str, str], direction: str, viewer_config: dict[str, Any] | None = None,
                  sequence_config: dict[str, Any] | None = None) -> str:
    viewer_config = viewer_config or {}
    sequence_config = sequence_config or {}
    button = lambda action, key: (  # noqa: E731
        f'<button type="button" data-viewer-action="{action}" '
        f'aria-label="{html.escape(labels[key], quote=True)}">{html.escape(labels[key])}</button>'
    )
    return (
        f'<dialog class="media-viewer" data-reading-direction="{html.escape(direction, quote=True)}" '
        f'data-viewer-modes="{html.escape(",".join(viewer_config.get("modes", ["single"])), quote=True)}" '
        f'data-viewer-default-mode="{html.escape(viewer_config.get("default_mode", "single"), quote=True)}" '
        f'data-viewer-mobile-default-mode="{html.escape(viewer_config.get("mobile_default_mode", viewer_config.get("default_mode", "single")), quote=True)}" '
        f'data-viewer-open-on-load="{str(bool(viewer_config.get("open_on_load"))).lower()}" '
        f'data-viewer-side-options="{html.escape(",".join(sequence_config.get("first_page_side_options", [sequence_config.get("first_page_side", "right")])), quote=True)}" '
        f'data-viewer-first-side="{html.escape(sequence_config.get("first_page_side", "right"), quote=True)}" '
        f'aria-label="{html.escape(labels["open"], quote=True)}">'
        '<div class="media-viewer__shell">'
        '<div class="media-viewer__toolbar">'
        f'<button type="button" class="media-viewer__mode-label" data-viewer-mode="single">{html.escape(labels.get("single", "Single page"))}</button>'
        f'<button type="button" class="media-viewer__mode-label" data-viewer-mode="manga">{html.escape(labels.get("manga", "Spread"))}</button>'
        f'<button type="button" data-viewer-side="right">{html.escape(labels.get("first_right", "Page 1 right"))}</button>'
        f'<button type="button" data-viewer-side="left">{html.escape(labels.get("first_left", "Page 1 left"))}</button>'
        '<span class="media-viewer__navigation">'
        f'{button("previous", "previous")}{button("next", "next")}'
        '</span>'
        '<span data-viewer-position aria-live="polite"></span>'
        f'{button("fit", "fit")}{button("actual", "actual")}'
        f'{button("fullscreen", "fullscreen")}{button("close", "close")}'
        '</div><div class="media-viewer__stage" data-viewer-stage tabindex="0">'
        '<div class="media-viewer__spread" data-viewer-spread><div class="media-viewer__page-slot" data-viewer-slot-left><img class="media-protected-image" draggable="false" data-viewer-left alt=""></div><div class="media-viewer__page-slot" data-viewer-slot-right><img class="media-protected-image" draggable="false" data-viewer-right alt=""></div></div>'
        '<img class="media-protected-image" draggable="false" data-viewer-image alt=""><p data-viewer-caption></p></div></div></dialog>'
    )


def _page_shell(locale: str, title: str, body: str, extra_css: str = "", direction: str = "ltr",
                viewer_markup: str = "", viewer_enabled: bool = False,
                image_deterrence_enabled: bool = False,
                library_sorting_enabled: bool = False, locale_route: str = "",
                display_persistence_enabled: bool = True,
                display_storage_key: str = "hada.display.v1") -> str:
    viewer_assets = ('<link rel="stylesheet" href="/assets/css/media-viewer.css">'
                     if viewer_enabled else "")
    if image_deterrence_enabled:
        viewer_assets += '<script src="/assets/js/media-viewer.js" defer></script>'
    if library_sorting_enabled:
        viewer_assets += '<script src="/assets/js/media-library.js" defer></script>'
    library_css = (
        ".collection-library-controls{display:flex;flex-wrap:wrap;gap:1rem;margin:1.5rem 0}"
        ".collection-library-controls label{display:flex;align-items:center;gap:.5rem}"
        ".collection-library-controls select{font:inherit;min-height:2.5rem;max-width:100%}"
        ".collection-library{display:grid;grid-template-columns:repeat(auto-fill,minmax(min(100%,220px),1fr));gap:1.25rem;list-style:none;margin:0;padding:0;direction:ltr}"
        ".collection-library__link{display:block;height:100%;color:inherit;text-align:start;text-decoration:none}"
        ".collection-library__cover{display:block;width:100%;aspect-ratio:4/3;object-fit:cover}"
        ".collection-library__title{display:block;padding:.65rem 0;font-weight:600}"
        ".collection-library__link:focus-visible{outline:3px solid #2878c8;outline-offset:3px}"
        if library_sorting_enabled else ""
    )
    local_path = locale_route.strip("/")
    jp_path = f"/jp/{local_path}/" if local_path else "/jp/"
    en_path = f"/en/{local_path}/" if local_path else "/en/"
    controls = ('<header class="site-header" data-site-header><nav aria-label="Language navigation">'
                f'<a href="{html.escape(jp_path, quote=True)}">日本語</a> '
                f'<a href="{html.escape(en_path, quote=True)}" hreflang="en">English</a></nav></header>'
                '<div class="display-controls" data-display-controls hidden aria-label="Display settings">'
                '<span>Theme:</span><button type="button" data-set-theme="light" aria-pressed="true">Light</button>'
                '<button type="button" data-set-theme="dark" aria-pressed="false">Dark</button>'
                '<span>Text size:</span><button type="button" data-set-text-size="standard" aria-pressed="true">Standard</button>'
                '<button type="button" data-set-text-size="large" aria-pressed="false">Large</button>'
                '<button type="button" data-set-text-size="xlarge" aria-pressed="false">Extra large</button></div>')
    return ("<!doctype html>\r\n<html lang=\"{lang}\"><head><meta charset=\"utf-8\">"
            "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\"><title>{title}</title>"
            "<link rel=\"stylesheet\" href=\"/assets/css/core.css\">"
            "{viewer_assets}"
            "<style>body{{max-width:1100px;margin:2rem auto;padding:0 1rem;font-family:system-ui,sans-serif}}"
            "a{{color:inherit}}.items{{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:1rem}}"
            "img,video,object{{max-width:100%;height:auto}}.spread{{display:grid;grid-template-columns:1fr 1fr;gap:0;direction:ltr}}"
            ".spread__right{{grid-column:2}}.spread__left{{grid-column:1}}.breadcrumbs{{display:flex;flex-wrap:wrap;gap:.5rem;list-style:none;padding:0}}"
            ".spread img{{width:100%;max-height:85vh;object-fit:contain}}.nav{{display:flex;justify-content:space-between;margin:1rem 0}}"
            "@media(max-width:700px){{.spread{{grid-template-columns:1fr}}.spread__right,.spread__left{{grid-column:1}}.spread [aria-hidden=true]{{display:none}}}}{library_css}{css}</style></head>"
            "<body data-ui-profile=\"shared-shell\" data-display-persistence=\"{persistence}\" data-display-storage-key=\"{storage_key}\">{controls}<main class=\"site-main\" data-site-main dir=\"{direction}\"><h1>{title}</h1>{body}</main>"
            "<footer class=\"site-footer\" data-site-footer><small>HADA Website Template</small></footer>{viewer}"
            "<script src=\"/assets/js/display-preferences.js\" defer></script></body></html>\r\n").format(
                lang=html.escape(locale, quote=True), title=html.escape(title), body=body, css=extra_css,
                direction=html.escape(direction if direction in {"ltr", "rtl"} else "ltr", quote=True),
                viewer_assets=viewer_assets, viewer=viewer_markup, library_css=library_css, controls=controls,
                persistence="true" if display_persistence_enabled else "false",
                storage_key=html.escape(display_storage_key, quote=True))


def _write_media_page(target: Path, collection_id: str, content: str) -> None:
    owner = hashlib.sha256(collection_id.encode("utf-8")).hexdigest()
    marker = f"<!-- HADA_MEDIA_COLLECTION:{owner} -->"
    _assert_media_page_owner(target, marker)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content.replace("</main>", f"{marker}</main>", 1), encoding="utf-8", newline="\r\n")


def _assert_media_page_owner(target: Path, marker: str) -> None:
    if target.is_file() and marker not in target.read_text(encoding="utf-8"):
        raise ValueError(f"media route would overwrite an existing non-media page; preserve it and choose a distinct route: {target}")


def _preflight_media_routes(root: Path, output: Path, collections: list[dict[str, Any]],
                            locales: list[str], media: dict[str, dict[str, Any]]) -> None:
    for collection in collections:
        collection_id = str(collection["collection_id"])
        route = str(collection["route"]).strip("/")
        items = [item for item in _collection_media(root, collection, media) if item.get("status") == "approved"]
        presentation = collection.get("presentation", "gallery")
        sequence = collection.get("sequence", {}) or {}
        for locale in locales:
            page_root = output / locale / route
            targets = [page_root / "index.html"]
            if presentation == "sequence" and items:
                spread = sequence.get("view", "single") == "spread" and sequence.get("spread_enabled", True)
                frames = build_spread_plan(len(items), sequence.get("first_page_side", "right"),
                                           sequence.get("reading_direction", "rtl")) if spread else items
                targets.extend(page_root / f"page-{index + 1:05d}.html" for index in range(len(frames)))
            elif ("manga" in (collection.get("viewer") or {}).get("modes", []) and items
                  and not (collection.get("viewer") or {}).get("open_on_load")):
                options = sequence.get("first_page_side_options", [sequence.get("first_page_side", "right")])
                for side in options:
                    side_root = page_root / "manga" / side
                    frames = build_spread_plan(len(items), side, sequence.get("reading_direction", "rtl"))
                    targets.extend(side_root / f"page-{index + 1:05d}.html" for index in range(len(frames)))
            marker = f"<!-- HADA_MEDIA_COLLECTION:{hashlib.sha256(collection_id.encode('utf-8')).hexdigest()} -->"
            for target in targets:
                _assert_media_page_owner(target, marker)


def _collection_library_markup(root: Path, children: list[dict[str, Any]],
                               media: dict[str, dict[str, Any]], locale: str) -> str:
    labels = _collection_ui(locale)
    controls = (
        f'<form class="collection-library-controls" data-library-sort data-locale="{html.escape(locale, quote=True)}">'
        f'<label><span>{html.escape(labels["sort_by"])}</span><select name="key">'
        f'<option value="name" selected>{html.escape(labels["name"])}</option>'
        f'<option value="publication_date">{html.escape(labels["publication_date"])}</option>'
        f'<option value="updated_date">{html.escape(labels["updated_date"])}</option></select></label>'
        f'<label><span>{html.escape(labels["sort_order"])}</span><select name="direction">'
        f'<option value="asc" selected>{html.escape(labels["ascending"])}</option>'
        f'<option value="desc">{html.escape(labels["descending"])}</option></select></label></form>'
    )
    ordered = sorted(children, key=lambda child: localized(child.get("title"), locale,
                                                             str(child.get("collection_id", ""))).casefold())
    cards: list[str] = []
    for child in ordered:
        child_title = localized(child.get("title"), locale, str(child.get("collection_id", "Collection")))
        child_route = str(child.get("route", "")).strip("/")
        href = f"/{locale}/{child_route}/"
        cover = _first_collection_image(root, child, media)
        cover_html = ""
        if cover:
            image_path = str(cover.get("thumbnail") or cover["public_file"]).lstrip("/")
            alt = localized(cover.get("alt"), locale, child_title)
            cover_html = (f'<img class="collection-library__cover" src="/{html.escape(image_path, quote=True)}" '
                          f'alt="{html.escape(alt, quote=True)}" loading="lazy">')
        publication = str(child.get("publication_date", ""))
        updated = str(child.get("updated_date", ""))
        cards.append(
            f'<li class="collection-library__item" data-sort-name="{html.escape(child_title, quote=True)}" '
            f'data-sort-publication-date="{html.escape(publication, quote=True)}" '
            f'data-sort-updated-date="{html.escape(updated, quote=True)}">'
            f'<a class="collection-library__link" href="{html.escape(href, quote=True)}">{cover_html}'
            f'<span class="collection-library__title">{html.escape(child_title)}</span></a></li>'
        )
    return controls + '<ul class="collection-library" data-collection-library>' + "".join(cards) + "</ul>"


def _first_collection_image(root: Path, collection: dict[str, Any],
                            media: dict[str, dict[str, Any]]) -> dict[str, Any] | None:
    items = [item for item in _collection_media(root, collection, media)
             if item.get("status") == "approved"]
    cover = next((item for item in items if item.get("type") == "image"), None)
    if cover:
        return cover
    for child in collection.get("children", []):
        cover = _first_collection_image(root, child, media)
        if cover:
            return cover
    return None


def build_media_library(root: Path, output: Path, locales: list[str]) -> int:
    catalog = load_catalog(root)
    if not catalog["media"] or not catalog["collections"]:
        return 0
    errors = validate_catalog(root)
    if errors:
        raise ValueError("Media catalog validation failed: " + "; ".join(errors))
    media = {str(item["media_id"]): item for item in catalog["media"]}
    project_path = root / "config" / "project.toml"
    project = load_document(project_path) if project_path.is_file() else {}
    display_settings = display_runtime_settings(root)
    media_route = str((((project or {}).get("paths") or {}).get("media_route", "media"))).strip("/")
    if not valid_collection_route(media_route):
        raise ValueError("paths.media_route must be a safe non-empty relative route")

    # Normalize the catalog's hierarchical routes once, then use these route
    # values consistently for generated files, breadcrumbs, and links.
    def normalize_nodes(nodes: list[dict[str, Any]], parent_raw: str = "",
                        parent_public: str = "") -> list[dict[str, Any]]:
        normalized: list[dict[str, Any]] = []
        for original in nodes:
            node = dict(original)
            raw = str(original.get("route", "")).strip("/")
            if parent_raw and raw.startswith(parent_raw + "/"):
                suffix = raw[len(parent_raw) + 1:]
                public = "/".join(part for part in (parent_public, suffix) if part)
            else:
                public = "/".join(part for part in (parent_public, raw) if part)
            node["route"] = "/".join(part for part in (media_route, public) if part)
            node["children"] = normalize_nodes(original.get("children", []), raw, public)
            normalized.append(node)
        return normalized

    normalized_catalog = normalize_nodes(catalog["collections"])
    collection_hierarchy = collections_with_ancestors(normalized_catalog)
    collections = [collection for collection, _ in collection_hierarchy]
    ancestors_by_id = {str(collection.get("collection_id")): ancestors
                       for collection, ancestors in collection_hierarchy}
    _preflight_media_routes(root, output, collections, locales, media)
    # A catalog without an explicit empty-route root still gets a stable library
    # landing page at the configured media route.
    has_root_collection = any(str(item.get("route", "")).strip("/") == media_route
                              for item in normalized_catalog)
    if not has_root_collection:
        for locale in locales:
            target = output / locale / media_route / "index.html"
            marker = f"<!-- HADA_MEDIA_COLLECTION:{hashlib.sha256(b'__media_library_root__').hexdigest()} -->"
            _assert_media_page_owner(target, marker)
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
            children = collection.get("children", [])
            listing_enabled = (collection.get("listing") or {}).get("enabled", True)
            library_sorting_enabled = bool(children) and listing_enabled
            viewer_config = collection.get("viewer") or {}
            viewer_enabled = bool(viewer_config.get("enabled", True)) and any(item.get("type") == "image" for item in items)
            image_deterrence_enabled = any(
                item.get("type") == "image" or
                (item.get("type") == "document" and item.get("thumbnail"))
                for item in items
            )
            viewer_labels = _viewer_labels(collection, locale)
            if image_deterrence_enabled:
                assets = [(VIEWER_JS, Path("assets/js/media-viewer.js"))]
                if viewer_enabled:
                    assets.insert(0, (VIEWER_CSS, Path("assets/css/media-viewer.css")))
                for source, relative in assets:
                    if not source.is_file():
                        raise ValueError(f"missing media viewer asset: {source.name}")
                    target = output / relative
                    target.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(source, target)
            if library_sorting_enabled:
                source = Path(__file__).with_name("media-library.js")
                if not source.is_file():
                    raise ValueError("missing media library sorting asset")
                target = output / "assets/js/media-library.js"
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, target)
            if len(items) >= 10000:
                print(f"MEDIA-WARNING {collection['collection_id']}: 10,000 items soft limit")
            presentation = collection.get("presentation", "gallery")
            if presentation == "sequence":
                sequence = collection.get("sequence", {}) or {}
                spread = sequence.get("view", "single") == "spread" and sequence.get("spread_enabled", True)
                side = sequence.get("first_page_side", "right")
                spread_plan = build_spread_plan(len(items), side, sequence.get("reading_direction", "rtl")) if spread else [
                    {"right": i if side == "right" else None, "left": i if side == "left" else None} for i in range(len(items))]
                groups = [sorted((index, items[index]) for index in (frame["right"], frame["left"]) if index is not None)
                          for frame in spread_plan]
                page_for_index = {index: page_no for page_no, group in enumerate(groups, start=1)
                                  for index, _item in group}
                group_size = 2 if spread else 1
                sequence_labels = sequence.get("labels") or {}
                localized_labels = sequence_labels.get("locales", {}).get(locale, {})
                defaults = DEFAULT_SEQUENCE_LABELS.get(locale, DEFAULT_SEQUENCE_LABELS["en"])
                next_label = str(localized_labels.get("next") or defaults["next"] or sequence_labels.get("next", "Next"))
                prev_label = str(localized_labels.get("previous") or defaults["previous"] or sequence_labels.get("previous", "Previous"))
                cards: list[str] = []
                for group_index, group in enumerate(groups):
                    filename = f"page-{group_index + 1:05d}.html"
                    href = f"/{locale}/{route}/{filename}"
                    for item_index, item in group:
                        label = localized(item.get("title"), locale, Path(str(item["public_file"])).stem)
                        thumb = item.get("thumbnail") or item["public_file"]
                        cards.append(f'<a href="{html.escape(href, quote=True)}#media-item-{item_index + 1:05d}"><img class="media-protected-image" draggable="false" src="/{html.escape(str(thumb).lstrip("/"), quote=True)}" alt=""><span>{html.escape(label)}</span></a>')
                    panels = []
                    for item_index, item in group:
                        label = localized(item.get("title"), locale, Path(str(item["public_file"])).stem)
                        alt = localized(item.get("alt"), locale, "")
                        previous = (f"/{locale}/{route}/page-{page_for_index[item_index - 1]:05d}.html"
                                    f"#media-item-{item_index:05d}") if item_index > 0 else ""
                        following = (f"/{locale}/{route}/page-{page_for_index[item_index + 1]:05d}.html"
                                     f"#media-item-{item_index + 2:05d}") if item_index + 1 < len(items) else ""
                        viewer = ({"id": f"media-item-{item_index + 1:05d}", "previous": previous,
                                   "next": following, "open": viewer_labels["open"], "caption": label,
                                   "position": f"{item_index + 1} / {len(items)}"}
                                  if viewer_enabled and item.get("type") == "image" else None)
                        preview = _preview(item, label, alt, root, viewer=viewer)
                        actual_side = next(slot for slot in ("right", "left") if spread_plan[group_index][slot] == item_index)
                        panels.append(f'<figure class="spread__{actual_side}">{preview}<figcaption>{html.escape(label)}</figcaption></figure>')
                    if spread:
                        content = f'<div class="spread">{"".join(panels)}</div>'
                    else:
                        content = "".join(panels)
                    prev_href = f"/{locale}/{route}/page-{group_index:05d}.html" if group_index > 0 else ""
                    next_href = f"/{locale}/{route}/page-{group_index + 2:05d}.html" if group_index + 1 < len(groups) else ""
                    labels_ui = _collection_ui(locale)
                    nav = f'<nav class="nav" aria-label="{html.escape(labels_ui["sequence"], quote=True)}">'
                    nav += f'<a rel="prev" href="{prev_href}">{html.escape(prev_label)}</a>' if prev_href else "<span></span>"
                    nav += f'<a rel="next" href="{next_href}">{html.escape(next_label)}</a>' if next_href else ""
                    nav += "</nav>"
                    body = f'{_breadcrumbs(locale, ancestors_by_id[str(collection["collection_id"])], output, media_route)}<p><a href="/{locale}/{route}/">{html.escape(title)}</a></p>{nav}{content}{nav}'
                    direction = str(sequence.get("reading_direction", "rtl"))
                    viewer_markup = _viewer_shell(viewer_labels, direction, viewer_config, sequence) if viewer_enabled else ""
                    _write_media_page(page_root / filename, str(collection["collection_id"]),
                        _page_shell(locale, title, body, direction=direction, viewer_markup=viewer_markup,
                                    viewer_enabled=viewer_enabled,
                                    image_deterrence_enabled=image_deterrence_enabled,
                                    locale_route=f"{route}/{filename}",
                                    display_persistence_enabled=display_settings["persistence_enabled"],
                                    display_storage_key=display_settings["storage_key"]))
                if listing_enabled:
                    index_body = '<div class="items">' + "".join(cards) + "</div>"
                elif groups:
                    first = groups[0][0][1]
                    following = (f"/{locale}/{route}/page-{page_for_index[1]:05d}.html#media-item-00002"
                                 if viewer_enabled and len(items) > 1 else "")
                    first_viewer = ({"id": "media-item-00001", "previous": "", "next": following,
                                     "open": viewer_labels["open"], "caption": title,
                                     "position": f"1 / {len(items)}"}
                                    if viewer_enabled and first.get("type") == "image" else None)
                    index_body = (f'<p><a href="/{locale}/{route}/page-00001.html">{html.escape(_collection_ui(locale)["open"])}</a></p>'
                                  + _preview(first, title, localized(first.get("alt"), locale, ""), root,
                                             viewer=first_viewer))
                else:
                    index_body = "<p>No media is available.</p>"
            else:
                cards = []
                for item_index, item in enumerate(items):
                    label = localized(item.get("title"), locale, Path(str(item["public_file"])).stem)
                    alt = localized(item.get("alt"), locale, "")
                    thumb = item.get("thumbnail") or item["public_file"]
                    previous = f"/{locale}/{route}/#media-item-{item_index:05d}" if item_index else ""
                    following = f"/{locale}/{route}/#media-item-{item_index + 2:05d}" if item_index + 1 < len(items) else ""
                    viewer = ({"id": f"media-item-{item_index + 1:05d}", "previous": previous,
                               "next": following, "open": viewer_labels["open"], "caption": label,
                               "position": f"{item_index + 1} / {len(items)}", "index": str(item_index)}
                              if viewer_enabled and item.get("type") == "image" else None)
                    if item.get("type") == "image":
                        attributes = " ".join(f'data-viewer-{key}="{html.escape(value, quote=True)}"' for key, value in (viewer or {}).items() if key != "id")
                        image = f'<img class="media-protected-image" draggable="false" src="/{html.escape(str(thumb).lstrip("/"), quote=True)}" alt="{html.escape(alt, quote=True)}" loading="lazy">'
                        card_media = (f'<a class="media-viewer-trigger" id="{html.escape(viewer["id"], quote=True)}" href="{html.escape(_asset_href(item), quote=True)}" aria-label="{html.escape(viewer.get("open", label), quote=True)}" {attributes}>{image}</a>' if viewer else f'<a href="{html.escape(_asset_href(item), quote=True)}">{image}</a>')
                    else:
                        card_media = _preview(item, label, alt, root)
                    cards.append(f'<figure>{card_media}<figcaption>{html.escape(label)} — {html.escape(item["type"])}</figcaption></figure>')
                if viewer_config.get("open_on_load") and viewer_enabled and items:
                    index_body = (
                        f'<button type="button" data-viewer-reopen>{html.escape(_collection_ui(locale)["open"])}</button>'
                        f'<noscript><p><a href="{html.escape(_asset_href(items[0]), quote=True)}">{html.escape(_collection_ui(locale)["open"])}</a></p></noscript>'
                        '<div class="media-viewer__page-index" hidden>' + "".join(cards) + "</div>"
                    )
                else:
                    index_body = ('<div class="items">' + "".join(cards) + "</div>" if cards else "") if listing_enabled else (_preview(items[0], title, localized(items[0].get("alt"), locale, ""), root) if items else f'<p>{html.escape(_collection_ui(locale)["empty"])}</p>')
                if "manga" in viewer_config.get("modes", []) and items and not viewer_config.get("open_on_load"):
                    sequence = collection.get("sequence") or {}
                    side_options = sequence.get("first_page_side_options", [sequence.get("first_page_side", "right")])
                    links = ['<nav aria-label="Manga mode">']
                    for first_side in side_options:
                        frames = build_spread_plan(len(items), first_side, sequence.get("reading_direction", "rtl"))
                        manga_route = f"{route}/manga/{first_side}"
                        side_root = page_root / "manga" / first_side
                        side_root.mkdir(parents=True, exist_ok=True)
                        links.append(f'<a href="/{locale}/{manga_route}/page-00001.html">{html.escape(viewer_labels.get("first_right" if first_side == "right" else "first_left", first_side))}</a> ')
                        for frame_index, frame in enumerate(frames):
                            panels = []
                            for side_name in ("right", "left"):
                                page_index = frame[side_name]
                                if page_index is None:
                                    panels.append(f'<div class="spread__{side_name}" aria-hidden="true"></div>')
                                    continue
                                item = items[page_index]
                                alt_text = localized(item.get("alt"), locale, "")
                                href = _asset_href(item)
                                panels.append(f'<figure class="spread__{side_name}"><a href="{html.escape(href, quote=True)}"><img class="media-protected-image" draggable="false" src="{html.escape(href, quote=True)}" alt="{html.escape(alt_text, quote=True)}"></a></figure>')
                            previous = f'/{locale}/{manga_route}/page-{frame_index:05d}.html' if frame_index else ""
                            following = f'/{locale}/{manga_route}/page-{frame_index + 2:05d}.html' if frame_index + 1 < len(frames) else ""
                            manga_labels = DEFAULT_SEQUENCE_LABELS.get(locale, DEFAULT_SEQUENCE_LABELS["en"])
                            nav = f'<nav class="nav" aria-label="{html.escape(_collection_ui(locale)["sequence"], quote=True)}">'
                            nav += f'<a rel="prev" href="{previous}">{html.escape(manga_labels["previous"])}</a>' if previous else '<span></span>'
                            nav += f'<a rel="next" href="{following}">{html.escape(manga_labels["next"])}</a>' if following else ""
                            nav += "</nav>"
                            body = f'<p><a href="/{locale}/{route}/">{html.escape(title)}</a></p>{nav}<div class="spread">{"".join(panels)}</div>{nav}'
                            filename = f"page-{frame_index + 1:05d}.html"
                            _write_media_page(side_root / filename, str(collection["collection_id"]),
                                _page_shell(locale, title, body, direction=sequence.get("reading_direction", "rtl"),
                                            locale_route=f"{manga_route}/{filename}",
                                            display_persistence_enabled=display_settings["persistence_enabled"],
                                            display_storage_key=display_settings["storage_key"]))
                    links.append("</nav>")
                    index_body += "".join(links)
            if children:
                if library_sorting_enabled:
                    index_body += _collection_library_markup(root, children, media, locale)
                else:
                    child_links = []
                    for child in children:
                        child_title = localized(child.get("title"), locale, str(child.get("collection_id", "Collection")))
                        child_route = str(child.get("route", "")).strip("/")
                        child_links.append(f'<li><a href="/{locale}/{html.escape(child_route, quote=True)}/">{html.escape(child_title)}</a></li>')
                    index_body += f'<nav aria-label="{html.escape(_collection_ui(locale)["children"], quote=True)}"><ul>' + "".join(child_links) + "</ul></nav>"
            index_body = _breadcrumbs(locale, ancestors_by_id[str(collection["collection_id"])], output,
                                      media_route) + index_body
            direction = str(((collection.get("sequence") or {}).get("reading_direction", "rtl")))
            index_viewer = _viewer_shell(viewer_labels, direction, viewer_config, collection.get("sequence") or {}) if viewer_enabled else ""
            _write_media_page(page_root / "index.html", str(collection["collection_id"]),
                _page_shell(locale, title, index_body, direction=direction,
                            viewer_markup=index_viewer, viewer_enabled=viewer_enabled,
                            image_deterrence_enabled=image_deterrence_enabled,
                            library_sorting_enabled=library_sorting_enabled, locale_route=route,
                            display_persistence_enabled=display_settings["persistence_enabled"],
                            display_storage_key=display_settings["storage_key"]))
    if not has_root_collection:
        for locale in locales:
            title = {"jp": "メディア", "en": "Media", "de": "Medien"}.get(locale, "Media")
            body = _collection_library_markup(root, normalized_catalog, media, locale)
            marker_id = "__media_library_root__"
            _write_media_page(output / locale / media_route / "index.html", marker_id,
                              _page_shell(locale, title, body, library_sorting_enabled=bool(normalized_catalog),
                                          locale_route=media_route,
                                          display_persistence_enabled=display_settings["persistence_enabled"],
                                          display_storage_key=display_settings["storage_key"]))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("validate", "build"))
    parser.add_argument("--root", default=".")
    parser.add_argument("--output", default="site")
    parser.add_argument("--locales", default="en,jp")
    args = parser.parse_args(argv)
    root = Path(args.root).resolve()
    try:
        if args.command == "validate":
            errors = validate_catalog(root)
            for error in errors:
                print(f"MEDIA-ERROR {error}")
            print(f"MEDIA-VALIDATION {'failed' if errors else 'passed'} errors={len(errors)}")
            return 1 if errors else 0
        build_media_library(root, Path(args.output).resolve(), [value.strip() for value in args.locales.split(",") if value.strip()])
        return 0
    except (OSError, ValueError, KeyError) as exc:
        print(f"MEDIA-ERROR {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
