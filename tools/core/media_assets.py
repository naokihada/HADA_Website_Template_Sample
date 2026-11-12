#!/usr/bin/env python3
"""Reviewable intake and best-effort derivative preparation for v0.4 media."""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from assets import Image, ImageDraw, ImageFont, apply_web_overlay
from media_library import MEDIA_TYPES, collections_flat, effective_processing, load_catalog, natural_key, safe_path, valid_collection_route
from structured_data import dump_json, load_document

INBOX = Path("AI/inbox/media")
MASTER = Path("assets/media/master")
WEB = Path("assets/media/web")
THUMB = Path("assets/media/thumbnails")
PROVENANCE = Path("assets/metadata/media")
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".avif"}
VIDEO_EXTENSIONS = {".mp4", ".webm", ".mov"}
PDF_EXTENSIONS = {".pdf"}


def digest(path: Path) -> str:
    sha = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            sha.update(block)
    return f"sha256:{sha.hexdigest()}"


def media_id(path: Path) -> str:
    value = "".join(c.lower() if c.isalnum() else "-" for c in path.stem).strip("-")
    value = "-".join(part for part in value.split("-") if part)
    return value[:90] if len(value) >= 2 else "media-001"


def _slug(value: str) -> str:
    value = "".join(char.lower() if char.isalnum() else "-" for char in value)
    value = re.sub(r"-+", "-", value).strip("-")
    return value if len(value) >= 2 else "media-set"


def _set_media_id(set_id: str, relative: Path) -> str:
    raw = f"{set_id}--{relative.with_suffix('').as_posix()}"
    normalized = _slug(raw)
    if len(normalized) <= 90:
        return normalized
    return normalized[:78] + "-" + hashlib.sha256(raw.encode("utf-8")).hexdigest()[:11]


def _image_suffix(policy: dict[str, Any]) -> str:
    return ".webp" if str(policy.get("output_format", "jpeg")).lower() == "webp" else ".jpg"


def _processing_fingerprint(policy: dict[str, Any]) -> str:
    payload = json.dumps(policy, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
    return "sha256:" + hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _folder_node_id(set_id: str, relative: Path) -> str:
    if not relative.parts:
        return set_id
    raw = f"{set_id}--{relative.as_posix()}"
    value = _slug(raw)
    return value if len(value) <= 90 else value[:78] + "-" + hashlib.sha256(raw.encode("utf-8")).hexdigest()[:11]


def _folder_set(root: Path, folder: Path, catalog: dict[str, Any]) -> dict[str, Any]:
    set_id = _slug(folder.name)
    collections = catalog.get("collections", [])
    existing = next((entry for entry in collections if isinstance(entry, dict) and
                     (entry.get("collection_id") == set_id or str(entry.get("route", "")).strip("/") == set_id)), None)
    if existing:
        config = existing
        conflict = existing.get("collection_id") != set_id
        action = "extend"
    else:
        config = {"collection_id": set_id, "route": set_id,
                  "title": {"en": folder.name, "jp": folder.name},
                  "presentation": "sequence", "listing": {"enabled": True},
                  "source_directory": (Path("assets/media/web") / set_id).as_posix(),
                  "sequence": {"order": "filename", "reading_direction": "rtl",
                               "first_page_side": "right", "view": "single", "spread_enabled": True},
                  "viewer": {"enabled": True}}
        conflict = any(isinstance(entry, dict) and
                       (entry.get("collection_id") == set_id or str(entry.get("route", "")).strip("/") == set_id)
                       for entry in collections)
        action = "create"
    config["source_directory"] = (WEB / set_id).as_posix()
    return {"set_id": set_id, "source_directory": folder.relative_to(root).as_posix(),
            "action": action, "status": "review_required" if conflict else "pending_approval",
            "issues": ["collection ID or route conflict; resolve manually"] if conflict else [],
            "collection": config}


def scan_inbox(root: Path, plan_path: Path) -> int:
    catalog = load_catalog(root)
    known = {str(item.get("media_id")) for item in catalog["media"] if isinstance(item, dict)}
    plan: list[dict[str, Any]] = []
    sets: list[dict[str, Any]] = []
    for origin in ("generated", "manual"):
        folder = root / INBOX / origin
        if not folder.is_dir():
            continue
        children = sorted(path for path in folder.iterdir() if path.is_dir()) if origin == "manual" and folder.is_dir() else []
        set_roots = {path.resolve() for path in children}
        if origin == "manual":
            normalized_counts: dict[str, int] = {}
            for child in children:
                normalized_counts[_slug(child.name)] = normalized_counts.get(_slug(child.name), 0) + 1
            for set_root in children:
                set_plan = _folder_set(root, set_root, catalog)
                if normalized_counts[set_plan["set_id"]] > 1:
                    set_plan["status"] = "review_required"
                    set_plan["issues"].append("multiple inbox folders normalize to this set ID")
                sets.append(set_plan)
                files = sorted((path for path in set_root.rglob("*") if path.is_file()),
                               key=lambda path: natural_key(path.relative_to(set_root).as_posix()))
                set_preview: list[dict[str, Any]] = []
                folder_nodes: set[Path] = {Path(".")}
                image_position = 0
                for path in files:
                    suffix = path.suffix.lower()
                    relative = path.relative_to(set_root)
                    for parent in relative.parent.parents:
                        folder_nodes.add(parent)
                    folder_nodes.add(relative.parent)
                    kind = "image" if suffix in IMAGE_EXTENSIONS else None
                    if kind:
                        image_position += 1
                    item_id = _set_media_id(set_plan["set_id"], relative)
                    issues = []
                    if not kind:
                        issues.append("image sets accept image files only; classify this file manually")
                    if item_id in known:
                        issues.append("media_id already exists")
                    if set_plan["status"] != "pending_approval":
                        issues.extend(set_plan["issues"])
                    entry = {"media_id": item_id, "type": kind or "unsupported", "source": path.relative_to(root).as_posix(),
                             "origin": origin, "set_id": set_plan["set_id"], "set_relative_path": relative.as_posix(),
                             "collection_node_id": _folder_node_id(set_plan["set_id"], relative.parent),
                             "sequence_position": image_position if kind else None,
                             "status": "review_required" if issues else "pending_approval", "issues": issues}
                    if kind:
                        image_policy = effective_processing(catalog, {"type": "image"}, set_plan.get("collection"))
                        output_relative = relative.with_suffix(_image_suffix(image_policy))
                        entry.update({"planned_master": (MASTER / set_plan["set_id"] / relative).as_posix(),
                                      "planned_public": (WEB / set_plan["set_id"] / output_relative).as_posix(),
                                      "planned_thumbnail": (THUMB / set_plan["set_id"] / output_relative).as_posix()})
                    plan.append(entry)
                    set_preview.append({"position": image_position if kind else None, "source": relative.as_posix(),
                                        "public": entry.get("planned_public"),
                                        "status": entry["status"]})
                    known.add(item_id)
                set_plan["preview"] = {"image_count": image_position, "source_file_count": len(files),
                                        "ordered_items": set_preview}
                node_ids: dict[str, Path] = {}
                for relative_dir in sorted(folder_nodes, key=lambda item: (len(item.parts), item.as_posix())):
                    node_id = _folder_node_id(set_plan["set_id"], relative_dir)
                    if node_id in node_ids and node_ids[node_id] != relative_dir:
                        set_plan["status"] = "review_required"
                        set_plan["issues"].append(f"folder paths normalize to the same collection ID: {relative_dir}")
                    node_ids[node_id] = relative_dir
                set_plan["nodes"] = [
                    {"relative_directory": "" if str(path) == "." else path.as_posix(),
                     "collection_id": _folder_node_id(set_plan["set_id"], path)}
                    for path in sorted(folder_nodes, key=lambda item: (len(item.parts), item.as_posix()))
                ]
        for path in sorted(folder.rglob("*")):
            if not path.is_file():
                continue
            if origin == "manual" and any(path.resolve().is_relative_to(set_root) for set_root in set_roots):
                continue
            suffix = path.suffix.lower()
            kind = "image" if suffix in IMAGE_EXTENSIONS else "video" if suffix in VIDEO_EXTENSIONS else "document" if suffix in PDF_EXTENSIONS else None
            if not kind:
                continue
            item_id = media_id(path)
            issues = []
            if item_id in known:
                issues.append("media_id already exists")
            if origin == "generated" and (kind != "image" or suffix != ".png"):
                issues.append("generated intake currently accepts PNG images only")
            plan.append({"media_id": item_id, "type": kind, "source": path.relative_to(root).as_posix(), "origin": origin,
                         "status": "review_required" if issues else "pending_approval", "issues": issues})
            known.add(item_id)
    plan_path.parent.mkdir(parents=True, exist_ok=True)
    plan_path.write_text(json.dumps({"schema_version": "0.3", "items": plan, "sets": sets}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\r\n")
    print(f"MEDIA-PLAN {plan_path} items={len(plan)}")
    return 0


def _domain(root: Path, catalog: dict[str, Any]) -> str:
    configured = str(((catalog.get("processing") or {}).get("domain", ""))).strip()
    if configured:
        return configured
    site_config = root / "config" / "site.json"
    if site_config.is_file():
        data = load_document(site_config) or {}
        url = str(((data.get("site") or {}).get("public_url", ""))).strip()
        if url:
            return url
    return ""


def _illustration_profile(root: Path) -> dict[str, Any]:
    path = root / "config" / "illustration-generation.toml"
    if not path.is_file():
        path = root / "config" / "illustration-generation.example.toml"
    return load_document(path) if path.is_file() else {}


def _image_derivatives(master: Path, web: Path, thumb: Path, policy: dict[str, bool], domain: str,
                       style: dict[str, Any], root: Path | None = None) -> None:
    if Image is None:
        raise RuntimeError("Pillow is required for image media")
    watermark = dict(policy.get("watermark") or {})
    enabled = bool(watermark.get("enabled", policy.get("domain_mark")))
    if watermark.get("type", "text") not in {"text", "image"}:
        raise ValueError("processing.watermark.type must be text or image")
    if watermark.get("position", "bottom-left") not in {"bottom-left", "bottom-right", "top-left", "top-right"}:
        raise ValueError("processing.watermark.position is invalid")
    overlay = {"enabled": enabled, "type": "text_logo" if enabled else "none",
               "text_source": "domain", "domain": domain, **style, **watermark}
    web.parent.mkdir(parents=True, exist_ok=True)
    thumb.parent.mkdir(parents=True, exist_ok=True)
    with Image.open(master) as image:
        converted = image.convert("RGBA")
        max_width, max_height = int(policy.get("max_width") or 0), int(policy.get("max_height") or 0)
        if max_width > 0 or max_height > 0:
            bounds = (max_width or converted.width, max_height or converted.height)
            converted.thumbnail(bounds, Image.Resampling.LANCZOS)
        if enabled and watermark.get("type") == "image":
            if root is None or not watermark.get("logo_file"):
                raise ValueError("image watermark requires processing.watermark.logo_file")
            logo_path = safe_path(root, str(watermark["logo_file"]))
            if not logo_path.is_relative_to((root.resolve() / MASTER / "watermarks").resolve()):
                raise ValueError("watermark logo must remain under assets/media/master/watermarks")
            if not logo_path.is_file():
                raise ValueError(f"watermark logo file does not exist: {watermark['logo_file']}")
            with Image.open(logo_path) as logo_source:
                logo = logo_source.convert("RGBA")
            width, height = converted.size
            ratio = min(max(float(watermark.get("scale_ratio", 0.12)), 0.01), 0.5)
            target_width = max(1, round(min(width, height) * ratio))
            target_height = max(1, round(logo.height * target_width / logo.width))
            logo.thumbnail((target_width, target_height), Image.Resampling.LANCZOS)
            alpha = max(0.0, min(1.0, float(watermark.get("logo_opacity", watermark.get("opacity", 0.88)))))
            logo.putalpha(logo.getchannel("A").point(lambda value: round(value * alpha)))
            margin = max(1, round(min(width, height) * float(watermark.get("margin_ratio", 0.025))))
            position = str(watermark.get("position", "bottom-left"))
            x = margin if position.endswith("left") else width - logo.width - margin
            y = margin if position.startswith("top") else height - logo.height - margin
            converted.alpha_composite(logo, (x, y))
        if enabled and (watermark.get("type", "text") == "text" or watermark.get("text") or watermark.get("include_text")):
            text_overlay = {**overlay, "enabled": True, "type": "text_logo"}
            if watermark.get("type") == "image":
                text_overlay["text_source"] = watermark.get("text_source", "text")
                text_overlay["text_position"] = watermark.get("text_position", "bottom-right")
                text_overlay["position"] = text_overlay["text_position"]
            converted = apply_web_overlay(converted, text_overlay)
        background_color = str(policy.get("background", "#ffffff")).lstrip("#")
        if len(background_color) != 6 or any(char not in "0123456789abcdefABCDEF" for char in background_color):
            raise ValueError("processing.background must be a six-digit hex color")
        rgb = tuple(int(background_color[index:index + 2], 16) for index in (0, 2, 4))
        background = Image.new("RGB", converted.size, rgb)
        background.paste(converted, mask=converted.getchannel("A"))
        output_format = str(policy.get("output_format", "jpeg")).lower()
        if output_format not in {"jpeg", "webp"}:
            raise ValueError("processing.output_format must be jpeg or webp")
        configured_quality = int(policy.get("quality", 88))
        minimum_quality = int(policy.get("minimum_quality", 55))
        if not 1 <= minimum_quality <= configured_quality <= 95:
            raise ValueError("processing quality must satisfy 1 <= minimum_quality <= quality <= 95")
        format_name = "JPEG" if output_format == "jpeg" else "WEBP"
        options = {"format": format_name, "quality": int(policy.get("quality", 88)), "optimize": True}
        if output_format == "jpeg":
            options["progressive"] = True
        if not policy.get("metadata_strip"):
            if image.info.get("exif"):
                options["exif"] = image.info["exif"]
            if image.info.get("icc_profile"):
                options["icc_profile"] = image.info["icc_profile"]
        quality = configured_quality
        max_bytes = int(policy.get("max_bytes") or 0)
        if max_bytes < 0 or int(policy.get("max_width") or 0) < 0 or int(policy.get("max_height") or 0) < 0:
            raise ValueError("processing size limits must be zero or positive")
        while True:
            buffer = io.BytesIO()
            options["quality"] = quality
            background.save(buffer, **options)
            encoded = buffer.getvalue()
            if not max_bytes or len(encoded) <= max_bytes:
                web.write_bytes(encoded)
                break
            if quality > minimum_quality:
                quality = max(minimum_quality, quality - 5)
                continue
            width, height = background.size
            if max(width, height) <= 320:
                raise ValueError(f"cannot meet processing.max_bytes={max_bytes} without going below minimum quality")
            background.thumbnail((max(1, round(width * 0.85)), max(1, round(height * 0.85))), Image.Resampling.LANCZOS)
            quality = minimum_quality
        thumb_image = background.copy()
        thumb_image.thumbnail((480, 480), Image.Resampling.LANCZOS)
        thumb_options = {"format": format_name, "quality": min(int(policy.get("quality", 88)), 82), "optimize": True}
        if output_format == "jpeg":
            thumb_options["progressive"] = True
        thumb_quality = int(thumb_options["quality"])
        while True:
            buffer = io.BytesIO()
            thumb_options["quality"] = thumb_quality
            thumb_image.save(buffer, **thumb_options)
            encoded = buffer.getvalue()
            if not max_bytes or len(encoded) <= max_bytes:
                thumb.write_bytes(encoded)
                break
            if thumb_quality > minimum_quality:
                thumb_quality = max(minimum_quality, thumb_quality - 5)
                continue
            if max(thumb_image.size) <= 320:
                raise ValueError(f"cannot meet processing.max_bytes={max_bytes} for thumbnail")
            thumb_image.thumbnail((round(thumb_image.width * 0.8), round(thumb_image.height * 0.8)), Image.Resampling.LANCZOS)
            thumb_quality = minimum_quality


def _pdf_derivative(master: Path, target: Path, strip: bool) -> str:
    if not strip:
        shutil.copy2(master, target)
        return "disabled"
    try:
        from pypdf import PdfReader, PdfWriter
    except ImportError:
        shutil.copy2(master, target)
        return "unavailable:pypdf"
    reader = PdfReader(str(master))
    writer = PdfWriter()
    writer.append_pages_from_reader(reader)
    writer.add_metadata({})
    with target.open("wb") as handle:
        writer.write(handle)
    return "best_effort:pypdf_info_dictionary_removed"


def _video_derivative(master: Path, target: Path, strip: bool) -> str:
    executable = shutil.which("ffmpeg")
    if not strip:
        shutil.copy2(master, target)
        return "disabled"
    if not executable:
        shutil.copy2(master, target)
        return "unavailable:ffmpeg_source_copied_best_effort"
    process = subprocess.run([executable, "-y", "-i", str(master), "-map_metadata", "-1", "-c", "copy", str(target)],
                             capture_output=True, text=True, check=False)
    if process.returncode:
        target.unlink(missing_ok=True)
        shutil.copy2(master, target)
        return "failed:ffmpeg_source_copied_best_effort"
    return "best_effort:ffmpeg_metadata_removed"


def _staging_path(target: Path, staged: list[tuple[Path, Path]], staging_root: Path) -> Path:
    temporary = staging_root / f"asset-{len(staged):08d}{target.suffix}"
    temporary.touch(exist_ok=False)
    staged.append((temporary, target))
    return temporary


def _collection_tree_for_set(set_plan: dict[str, Any], items: list[dict[str, Any]], mode: str,
                             media_entries: dict[str, dict[str, Any]]) -> dict[str, Any]:
    root_collection = dict(set_plan["collection"])
    root_collection["intake"] = {"folder_mode": mode}
    root_collection["source_directory"] = (WEB / str(set_plan["set_id"])).as_posix()
    if mode == "flat":
        root_collection["media_ids"] = []
        root_collection.pop("children", None)
        return root_collection

    root_route = str(root_collection.get("route", set_plan["set_id"])).strip("/")
    descriptors = {str(node["collection_id"]): Path(str(node.get("relative_directory", "")))
                   for node in set_plan.get("nodes", []) if isinstance(node, dict)}
    descriptors.setdefault(str(set_plan["set_id"]), Path())
    nodes: dict[str, dict[str, Any]] = {}
    for collection_id, relative in descriptors.items():
        if not relative.parts:
            entry = dict(root_collection)
        else:
            route_suffix = "/".join(_slug(part) for part in relative.parts)
            title = relative.name
            entry = {"collection_id": collection_id, "route": f"{root_route}/{route_suffix}",
                     "title": {"en": title, "jp": title}, "presentation": "sequence",
                     "listing": {"enabled": True}, "media_ids": [],
                     "sequence": {"order": "filename", "reading_direction": "rtl",
                                  "first_page_side": "right", "view": "single", "spread_enabled": True},
                     "viewer": {"enabled": True}}
        entry.pop("source_directory", None)
        entry["media_ids"] = []
        entry["children"] = []
        nodes[collection_id] = entry

    for item in items:
        if item.get("set_id") != set_plan["set_id"] or item.get("type") != "image":
            continue
        media_id = str(item["media_id"])
        node_id = str(item.get("collection_node_id", set_plan["set_id"]))
        if media_id in media_entries and node_id in nodes and media_id not in nodes[node_id]["media_ids"]:
            nodes[node_id]["media_ids"].append(media_id)

    root = nodes[str(set_plan["set_id"])]
    for collection_id, relative in sorted(descriptors.items(), key=lambda pair: (len(pair[1].parts), pair[1].as_posix())):
        if not relative.parts:
            continue
        parent_id = _folder_node_id(str(set_plan["set_id"]), relative.parent)
        if parent_id not in nodes:
            raise ValueError(f"missing parent collection for image-set directory: {relative}")
        nodes[parent_id]["children"].append(nodes[collection_id])
    return root


def _merge_collection(existing: dict[str, Any], incoming: dict[str, Any]) -> None:
    members = existing.setdefault("media_ids", [])
    for media_id in incoming.get("media_ids", []):
        if media_id not in members:
            members.append(media_id)
    existing_children = existing.setdefault("children", [])
    by_id = {str(child.get("collection_id", "")): child for child in existing_children if isinstance(child, dict)}
    for child in incoming.get("children", []):
        child_id = str(child.get("collection_id", ""))
        if child_id in by_id:
            _merge_collection(by_id[child_id], child)
        else:
            existing_children.append(child)


def import_plan(root: Path, plan_path: Path, approve: bool, folder_mode: str = "tree") -> int:
    if not approve:
        raise ValueError("media import is gated; pass --approve after reviewing the plan")
    if folder_mode not in {"tree", "flat"}:
        raise ValueError("folder_mode must be 'tree' or 'flat'")
    catalog = load_catalog(root)
    if str(catalog.get("schema_version", "0.1")) != "0.3":
        raise ValueError("media catalog schema_version must be 0.3")
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    if str(plan.get("schema_version", "0.2")) not in {"0.2", "0.3"}:
        raise ValueError("unsupported media intake plan schema")
    pending_items = [item for item in plan.get("items", []) if item.get("status") == "pending_approval"]
    if not pending_items:
        print("MEDIA-IMPORTED 0")
        return 0
    set_plans = {str(entry["set_id"]): entry for entry in plan.get("sets", [])
                 if isinstance(entry, dict) and entry.get("status") == "pending_approval"}
    entries = {str(item.get("media_id")): item for item in catalog["media"] if isinstance(item, dict)}
    style = (catalog.get("processing") or {}).get("domain_mark_style", {}) or {}
    domain = _domain(root, catalog)
    illustration_config = _illustration_profile(root)
    provider_name = str(((illustration_config.get("provider") or {}).get("default", "chatgpt_image")))
    prompt_profile = illustration_config.get("prompt_profile") or {}
    prompt_text = "\n".join(str(prompt_profile.get(key, "")).strip() for key in ("common_prompt", "style_prompt", "negative_prompt") if str(prompt_profile.get(key, "")).strip())
    reserved_ids: set[str] = set()
    reserved_paths: set[Path] = set()
    set_routes: set[str] = set()
    validated_route_sets: set[str] = set()
    for candidate in pending_items:
        media_key = str(candidate["media_id"])
        if media_key in entries or media_key in reserved_ids:
            raise ValueError(f"media_id already exists: {media_key}")
        reserved_ids.add(media_key)
        source = safe_path(root, str(candidate["source"]))
        if not source.is_file():
            raise ValueError(f"missing inbox source: {candidate['source']}")
        kind = str(candidate["type"])
        if kind not in MEDIA_TYPES:
            raise ValueError(f"unsupported planned media type: {kind}")
        set_id = str(candidate.get("set_id", ""))
        source_parts = Path(str(candidate["source"]))
        if len(source_parts.parts) < 5 or source_parts.parts[:3] != INBOX.parts or source_parts.parts[3] not in {"manual", "generated"}:
            raise ValueError(f"source must remain under the media inbox: {candidate['source']}")
        if candidate.get("origin") != source_parts.parts[3]:
            raise ValueError(f"inbox origin does not match source: {candidate['source']}")
        if set_id:
            set_plan = set_plans.get(set_id)
            set_root = Path(str(set_plan.get("source_directory", ""))) if set_plan else Path()
            if (not set_plan or set_plan.get("action") not in {"create", "extend"} or kind != "image"
                    or len(set_root.parts) != 5 or set_root.parent != INBOX / "manual"
                    or _slug(set_root.name) != set_id):
                raise ValueError(f"invalid or unapproved image set: {set_id}")
            try:
                relative_source = Path(str(candidate["source"])).relative_to(set_root)
            except ValueError as exc:
                raise ValueError(f"source is outside its image set: {candidate['source']}") from exc
            relative = Path(str(candidate["set_relative_path"]))
            if relative.is_absolute() or ".." in relative.parts or relative != relative_source:
                raise ValueError(f"unsafe image-set relative path: {candidate['source']}")
            if str(candidate["media_id"]) != _set_media_id(set_id, relative):
                raise ValueError(f"image-set media ID was changed in the plan: {candidate['source']}")
            collection = set_plan.get("collection")
            if not isinstance(collection, dict) or collection.get("collection_id") != set_id:
                raise ValueError(f"image-set collection identity was changed: {set_id}")
            if str(collection.get("source_directory", "")).replace("\\", "/") != (WEB / set_id).as_posix():
                raise ValueError(f"image-set collection source directory is invalid: {set_id}: {collection.get('source_directory')!r}")
            title = collection.get("title")
            if not isinstance(title, dict) or any(not isinstance(title.get(locale), str) or not title[locale].strip()
                                                   for locale in ("en", "jp")):
                raise ValueError(f"image-set collection needs non-empty en and jp titles: {set_id}")
            listing = collection.get("listing")
            sequence = collection.get("sequence")
            viewer = collection.get("viewer")
            if (collection.get("presentation") != "sequence" or not isinstance(listing, dict)
                    or not isinstance(listing.get("enabled"), bool) or not isinstance(sequence, dict)
                    or sequence.get("order", "filename") not in {"filename", "manual", "modified_asc", "modified_desc", "capture_time_asc", "capture_time_desc"}
                    or sequence.get("reading_direction") not in {"rtl", "ltr"}
                    or sequence.get("first_page_side") not in {"left", "right"}
                    or sequence.get("view") not in {"single", "spread"}
                    or not isinstance(sequence.get("spread_enabled"), bool)
                    or not isinstance(viewer, dict) or not isinstance(viewer.get("enabled"), bool)):
                raise ValueError(f"invalid image-set collection settings: {set_id}")
            if set_plan.get("action") == "create" and set_id not in validated_route_sets:
                route = str(collection.get("route", "")).strip("/")
                if "?" in route or "#" in route or not valid_collection_route(route):
                    raise ValueError(f"invalid planned collection route: {route}")
                if route in set_routes:
                    raise ValueError(f"multiple new sets use the same collection route: {route}")
                set_routes.add(route)
                validated_route_sets.add(set_id)
            set_policy = effective_processing(catalog, {"type": "image"}, set_plan.get("collection"))
            output_relative = relative.with_suffix(_image_suffix(set_policy))
            targets = [MASTER / set_id / relative, WEB / set_id / output_relative,
                       THUMB / set_id / output_relative]
        else:
            suffix = source.suffix.lower()
            if candidate["origin"] == "generated" and (kind != "image" or suffix != ".png"):
                raise ValueError("generated media intake currently accepts PNG images only")
            if candidate["origin"] == "manual" and not (
                    (kind == "image" and suffix in IMAGE_EXTENSIONS) or
                    (kind == "video" and suffix in VIDEO_EXTENSIONS) or
                    (kind == "document" and suffix in PDF_EXTENSIONS)):
                raise ValueError(f"source extension does not match media type: {candidate['source']}")
            suffix = _image_suffix(effective_processing(catalog, {"type": kind}, set_plans.get(set_id, {}).get("collection") if set_id else None)) if kind == "image" else source.suffix.lower()
            targets = [MASTER / f"{media_key}{source.suffix.lower()}", WEB / f"{media_key}{suffix}"]
            if kind == "image":
                targets.append(THUMB / f"{media_key}{suffix}")
        policy = effective_processing(catalog, {"type": kind, "processing": candidate.get("processing")}, set_plans.get(set_id, {}).get("collection") if set_id else None)
        if kind == "image" and policy.get("watermark", {}).get("enabled", policy.get("domain_mark")) and policy.get("watermark", {}).get("type", "text") == "text" and policy.get("watermark", {}).get("text_source", "domain") == "domain" and not domain:
            raise ValueError("processing.domain is required when image domain_mark defaults to true")
        if kind == "image":
            if Image is None:
                raise RuntimeError("Pillow is required for image media")
            try:
                with Image.open(source) as source_image:
                    source_image.verify()
            except Exception as exc:
                raise ValueError(f"image source cannot be decoded: {candidate['source']}") from exc
        provenance_target = PROVENANCE / media_key / "PROVENANCE.json"
        if (root / provenance_target).exists():
            raise ValueError(f"provenance target exists; refusing overwrite: {media_key}")
        targets.append(provenance_target)
        for target in targets:
            if target in reserved_paths or (root / target).exists():
                raise ValueError(f"target exists or collides; refusing overwrite: {target.as_posix()}")
            reserved_paths.add(target)
    current_collections = collections_flat(catalog.get("collections", []))
    occupied_routes = {str(entry.get("route", "")).strip("/") for entry in current_collections}
    occupied_ids = {str(entry.get("collection_id", "")) for entry in current_collections}
    for set_id, set_plan in set_plans.items():
        existing_set = next((entry for entry in current_collections if str(entry.get("collection_id", "")) == set_id), None)
        if existing_set is not None:
            existing_mode = str(((existing_set.get("intake") or {}).get("folder_mode")) or
                                ("flat" if existing_set.get("source_directory") else "tree"))
            if existing_mode != folder_mode:
                raise ValueError(f"image set {set_id} uses folder_mode={existing_mode}; cannot extend it as {folder_mode}")
        if set_plan.get("action") == "create":
            proposed_route = str((set_plan.get("collection") or {}).get("route", set_id)).strip("/")
            if set_id in occupied_ids or proposed_route in occupied_routes:
                raise ValueError(f"collection ID or route conflict: {set_id}")
        if folder_mode == "tree":
            root_route = str((set_plan.get("collection") or {}).get("route", set_id)).strip("/")
            for node in set_plan.get("nodes", []):
                relative = Path(str(node.get("relative_directory", "")))
                if not relative.parts:
                    continue
                node_id = str(node["collection_id"])
                route = "/".join([root_route, *(_slug(part) for part in relative.parts)])
                if not valid_collection_route(route):
                    raise ValueError(f"invalid nested collection route: {route}")
                existing_node = next((entry for entry in current_collections if str(entry.get("collection_id", "")) == node_id), None)
                if existing_node is not None:
                    existing_route = str(existing_node.get("route", "")).strip("/")
                    if existing_route != route:
                        raise ValueError(f"nested collection route changed for {node_id}; manual review required")
                elif route in occupied_routes:
                    raise ValueError(f"nested collection route conflict: {route}")
    manifest = safe_path(root, "config/media.catalog.json")
    manifest_hash_before = digest(manifest)
    staging = tempfile.TemporaryDirectory(prefix=".media-import-", dir=root)
    staging_root = Path(staging.name)
    imported = 0
    imported_sets: set[str] = set()
    warnings: list[str] = []
    staged_files: list[tuple[Path, Path]] = []
    for item in plan.get("items", []):
        if item.get("status") != "pending_approval":
            continue
        media_key = str(item["media_id"])
        if media_key in entries:
            raise ValueError(f"media_id already exists: {media_key}")
        source = safe_path(root, str(item["source"]))
        if not source.is_file():
            raise ValueError(f"missing inbox source: {item['source']}")
        kind = str(item["type"])
        set_id = str(item.get("set_id", ""))
        set_plan = set_plans.get(set_id) if set_id else None
        if set_id and (not set_plan or set_plan.get("action") not in {"create", "extend"}):
            raise ValueError(f"set is not pending approval: {set_id}")
        if set_id and kind != "image":
            raise ValueError(f"unsupported media type in image set: {item['source']}")
        policy = effective_processing(catalog, {"type": kind, "processing": item.get("processing")},
                                      set_plans.get(set_id, {}).get("collection") if set_id else None)
        if kind == "image" and policy.get("watermark", {}).get("enabled", policy.get("domain_mark")) and policy.get("watermark", {}).get("type", "text") == "text" and policy.get("watermark", {}).get("text_source", "domain") == "domain" and not domain:
            raise ValueError("processing.domain is required when image domain_mark defaults to true")
        suffix = _image_suffix(policy) if kind == "image" else source.suffix.lower()
        if set_id:
            relative = Path(str(item["set_relative_path"]))
            if relative.is_absolute() or ".." in relative.parts:
                raise ValueError(f"unsafe set relative path: {relative}")
            output_relative = relative.with_suffix(_image_suffix(policy))
            master_rel = MASTER / set_id / relative
            web_rel = WEB / set_id / output_relative
            thumb_rel = THUMB / set_id / output_relative
        else:
            master_rel = MASTER / f"{media_key}{source.suffix.lower()}"
            web_rel = WEB / f"{media_key}{suffix}"
            thumb_rel = THUMB / f"{media_key}{_image_suffix(policy)}" if kind == "image" else None
        master_target = root / master_rel
        web_target = root / web_rel
        master = _staging_path(master_target, staged_files, staging_root)
        web = _staging_path(web_target, staged_files, staging_root)
        shutil.copy2(source, master)
        if kind == "image":
            thumb_target = root / thumb_rel
            thumb = _staging_path(thumb_target, staged_files, staging_root)
            _image_derivatives(master, web, thumb, policy, domain, style, root)
            metadata_result = "stripped:new image derivative" if policy["metadata_strip"] else "preserved:processing disabled"
        elif kind == "document":
            metadata_result = _pdf_derivative(master, web, policy["metadata_strip"])
        else:
            metadata_result = _video_derivative(master, web, policy["metadata_strip"])
        if metadata_result.startswith("unavailable") or metadata_result.startswith("failed"):
            warnings.append(f"{media_key}: {metadata_result}")
        record = {"media_id": media_key, "type": kind,
                  "source": {"file": master_rel.as_posix(), "visibility": "private", "origin": item.get("origin", "manual"), "sha256": digest(master)},
                  "public_file": web_rel.as_posix(), "status": "approved",
                  "public_sha256": digest(web),
                  "processing": item.get("processing", {}),
                  "processing_fingerprint": _processing_fingerprint(policy),
                  "processing_result": metadata_result}
        if set_id:
            record["processing_collection_id"] = set_id
        if item.get("origin") == "generated":
            record["provider"] = provider_name
            record["prompt_profile"] = str(prompt_profile.get("name", "editorial-illustration"))
        if thumb_rel:
            record["thumbnail"] = thumb_rel.as_posix()
            record["thumbnail_sha256"] = digest(thumb)
        entries[media_key] = record
        if set_id:
            imported_sets.add(set_id)
        provenance_dir = root / PROVENANCE / media_key
        provenance_target = provenance_dir / "PROVENANCE.json"
        provenance_stage = _staging_path(provenance_target, staged_files, staging_root)
        provenance = {"media_id": media_key, "type": kind, "origin": item.get("origin", "manual"),
                      "source_sha256": digest(master), "public_sha256": digest(web),
                      "metadata_processing": metadata_result, "embedded_signal_transform": "disabled",
                      "domain_mark": policy["domain_mark"], "source_visibility": "private",
                      "imported_at": datetime.now(timezone.utc).isoformat()}
        if item.get("origin") == "generated":
            provenance.update({"provider": provider_name, "prompt_profile": str(prompt_profile.get("name", "editorial-illustration")), "prompt": prompt_text})
        dump_json(provenance, provenance_stage)
        imported += 1
    catalog["media"] = list(entries.values())
    for set_id in sorted(imported_sets):
        set_plan = set_plans[set_id]
        collection = _collection_tree_for_set(set_plan, plan.get("items", []), folder_mode, entries)
        if set_plan.get("action") == "create":
            existing = any(isinstance(entry, dict) and
                           (entry.get("collection_id") == set_id or str(entry.get("route", "")).strip("/") == set_id)
                           for entry in catalog.get("collections", []))
            if existing:
                raise ValueError(f"collection ID or route became occupied: {set_id}")
            catalog.setdefault("collections", []).append(collection)
        else:
            current = next((entry for entry in collections_flat(catalog.get("collections", []))
                            if str(entry.get("collection_id", "")) == set_id), None)
            if current is None:
                raise ValueError(f"existing image-set collection disappeared: {set_id}")
            _merge_collection(current, collection)
    manifest_text = json.dumps(catalog, ensure_ascii=False, indent=2) + "\n"
    with tempfile.NamedTemporaryFile(prefix=".media-catalog-", suffix=".json",
                                     dir=manifest.parent, delete=False, mode="w",
                                     encoding="utf-8", newline="\r\n") as handle:
        manifest_stage = Path(handle.name)
        handle.write(manifest_text)
    promoted: list[tuple[Path, str]] = []
    try:
        for staged, target in staged_files:
            if target.exists():
                raise ValueError(f"target appeared during import; refusing overwrite: {target.relative_to(root).as_posix()}")
            target.parent.mkdir(parents=True, exist_ok=True)
            os.replace(staged, target)
            promoted.append((target, digest(target)))
        if digest(manifest) != manifest_hash_before:
            raise ValueError("media catalog changed during import; refusing to replace it")
        os.replace(manifest_stage, manifest)
    except Exception:
        manifest_stage.unlink(missing_ok=True)
        for target, expected_hash in reversed(promoted):
            if target.is_file() and digest(target) == expected_hash:
                target.unlink()
        raise
    finally:
        staging.cleanup()
    print(f"MEDIA-IMPORTED {imported}")
    for set_id in sorted(imported_sets):
        route = str(set_plans[set_id]["collection"].get("route", set_id)).strip("/")
        print(f"MEDIA-SET {set_id} /{{locale}}/{route}/")
    for warning in warnings:
        print(f"MEDIA-WARNING {warning}")
    return 0


def sync_media(root: Path, apply: bool) -> int:
    catalog = load_catalog(root)
    domain = _domain(root, catalog)
    style = (catalog.get("processing") or {}).get("domain_mark_style", {}) or {}
    findings = 0
    changed = 0
    unresolved = 0
    for item in catalog["media"]:
        if not isinstance(item, dict) or item.get("status") != "approved":
            continue
        source_cfg = item.get("source") or {}
        if not isinstance(source_cfg, dict) or not source_cfg.get("file"):
            print(f"REVIEW_REQUIRED missing source path: {item.get('media_id', '')}")
            findings += 1
            unresolved += 1
            continue
        try:
            master = safe_path(root, str(source_cfg["file"]))
            public_rel = safe_path(root, str(item["public_file"]))
        except (KeyError, ValueError) as exc:
            print(f"REVIEW_REQUIRED {item.get('media_id', '')}: {exc}")
            findings += 1
            unresolved += 1
            continue
        if not master.is_file():
            print(f"REVIEW_REQUIRED missing master: {item.get('media_id', '')}")
            findings += 1
            unresolved += 1
            continue
        current_hash = digest(master)
        public = public_rel
        kind = str(item.get("type", ""))
        thumb = None
        if kind == "image" and item.get("thumbnail"):
            thumb = root / safe_path(root, str(item["thumbnail"]))
        source_matches = source_cfg.get("sha256") == current_hash
        derivatives_exist = public.is_file() and (kind != "image" or (thumb is not None and thumb.is_file()))
        public_hash_matches = item.get("public_sha256") == digest(public) if public.is_file() else False
        thumbnail_hash_matches = (kind != "image" or
                                  (thumb is not None and thumb.is_file() and item.get("thumbnail_sha256") == digest(thumb)))
        processing_collection_id = str(item.get("processing_collection_id", ""))
        processing_collection = next((node for node, _ in collections_flat(catalog.get("collections", []))
                                      if str(node.get("collection_id", "")) == processing_collection_id), None) if processing_collection_id else None
        policy = effective_processing(catalog, item, processing_collection)
        policy_matches = item.get("processing_fingerprint") in {None, _processing_fingerprint(policy)}
        if source_matches and derivatives_exist and public_hash_matches and thumbnail_hash_matches and policy_matches:
            continue
        print(f"SYNC {item.get('media_id', '')}: source, derivative, or processing profile changed")
        findings += 1
        if not apply:
            continue
        # Existing derivatives without recorded output hashes can be adopted
        # without re-encoding. A recorded mismatch requires regeneration.
        recorded_public = item.get("public_sha256")
        recorded_thumb = item.get("thumbnail_sha256")
        unrecorded_hashes = (not recorded_public and not recorded_thumb and
                             source_matches and derivatives_exist and policy_matches)
        if unrecorded_hashes:
            item["public_sha256"] = digest(public)
            if kind == "image" and thumb is not None:
                item["thumbnail_sha256"] = digest(thumb)
            changed += 1
            continue
        kind = str(item.get("type", ""))
        if kind == "image":
            if policy.get("watermark", {}).get("enabled", policy.get("domain_mark")) and policy.get("watermark", {}).get("type", "text") == "text" and policy.get("watermark", {}).get("text_source", "domain") == "domain" and not domain:
                print(f"REVIEW_REQUIRED {item.get('media_id', '')}: processing.domain is required")
                unresolved += 1
                continue
            if not item.get("thumbnail"):
                print(f"REVIEW_REQUIRED missing thumbnail path: {item.get('media_id', '')}")
                unresolved += 1
                continue
            thumb = root / safe_path(root, str(item.get("thumbnail", "")))
            desired_public = public.with_suffix(_image_suffix(policy))
            desired_thumb = thumb.with_suffix(_image_suffix(policy))
            if desired_public != public and desired_public.exists():
                print(f"REVIEW_REQUIRED {item.get('media_id', '')}: target derivative already exists")
                unresolved += 1
                continue
            if desired_thumb != thumb and desired_thumb.exists():
                print(f"REVIEW_REQUIRED {item.get('media_id', '')}: target thumbnail already exists")
                unresolved += 1
                continue
            _image_derivatives(master, desired_public, desired_thumb, policy, domain, style, root)
            item["public_file"] = desired_public.relative_to(root).as_posix()
            item["thumbnail"] = desired_thumb.relative_to(root).as_posix()
            public, thumb = desired_public, desired_thumb
            result = "stripped:new image derivative" if policy["metadata_strip"] else "preserved:processing disabled"
        elif kind == "document":
            result = _pdf_derivative(master, public, policy["metadata_strip"])
        elif kind == "video":
            result = _video_derivative(master, public, policy["metadata_strip"])
        else:
            print(f"REVIEW_REQUIRED unsupported media type: {kind}")
            unresolved += 1
            continue
        source_cfg["sha256"] = current_hash
        item["processing_result"] = result
        item["processing_fingerprint"] = _processing_fingerprint(policy)
        item["public_sha256"] = digest(public)
        if kind == "image" and thumb is not None:
            item["thumbnail_sha256"] = digest(thumb)
        if result.startswith("unavailable") or result.startswith("failed"):
            print(f"MEDIA-WARNING {item.get('media_id', '')}: {result}")
        changed += 1
    if apply and changed:
        manifest = root / "config" / "media.catalog.json"
        manifest.write_text(json.dumps(catalog, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\r\n")
    print(f"MEDIA-SYNC changed={changed} findings={findings}")
    return 1 if unresolved or (findings and not apply) else 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("scan-inbox", "import", "sync"))
    parser.add_argument("--root", default=".")
    parser.add_argument("--plan-file", default="AI/state/media-import-plan.json")
    parser.add_argument("--approve", action="store_true")
    parser.add_argument("--folder-mode", choices=("tree", "flat"),
                        help="preserve nested folders as nested collections (tree, default) or flatten into one collection")
    parser.add_argument("--apply", action="store_true", help="regenerate derivatives from retained masters")
    args = parser.parse_args(argv)
    root = Path(args.root).resolve()
    try:
        plan_path = root / safe_path(root, args.plan_file)
        if args.command == "scan-inbox":
            return scan_inbox(root, plan_path)
        if args.command == "sync":
            return sync_media(root, args.apply)
        if args.approve and args.folder_mode is None:
            intake_plan = json.loads(plan_path.read_text(encoding="utf-8"))
            has_sets = any(item.get("set_id") and item.get("status") == "pending_approval"
                           for item in intake_plan.get("items", []))
            if has_sets:
                if not sys.stdin.isatty():
                    raise ValueError("noninteractive image-set import requires --folder-mode tree|flat")
                answer = input("Preserve uploaded folder hierarchy as nested collections? [Y/n] ").strip().lower()
                args.folder_mode = "flat" if answer in {"n", "no", "flat", "f"} else "tree"
        return import_plan(root, plan_path, args.approve, folder_mode=args.folder_mode or "tree")
    except (OSError, RuntimeError, ValueError, KeyError, json.JSONDecodeError) as exc:
        print(f"MEDIA-ERROR {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
