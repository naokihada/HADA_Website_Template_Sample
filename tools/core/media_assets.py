#!/usr/bin/env python3
"""Reviewable intake and best-effort derivative preparation for v0.4 media."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

from assets import Image, ImageDraw, ImageFont, apply_web_overlay
from media_library import effective_processing, load_catalog, safe_path

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


def scan_inbox(root: Path, plan_path: Path) -> int:
    catalog = load_catalog(root)
    known = {str(item.get("media_id")) for item in catalog["media"] if isinstance(item, dict)}
    plan: list[dict[str, Any]] = []
    for origin in ("generated", "manual"):
        folder = root / INBOX / origin
        if not folder.is_dir():
            continue
        for path in sorted(folder.rglob("*")):
            if not path.is_file():
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
    plan_path.write_text(json.dumps({"schema_version": "0.2", "items": plan}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\r\n")
    print(f"MEDIA-PLAN {plan_path} items={len(plan)}")
    return 0


def _domain(root: Path, catalog: dict[str, Any]) -> str:
    configured = str(((catalog.get("processing") or {}).get("domain", ""))).strip()
    if configured:
        return configured
    site_config = root / "config" / "site.yaml"
    if site_config.is_file():
        data = yaml.safe_load(site_config.read_text(encoding="utf-8")) or {}
        url = str(((data.get("site") or {}).get("public_url", ""))).strip()
        if url:
            return url
    return ""


def _illustration_profile(root: Path) -> dict[str, Any]:
    path = root / "config" / "illustration-generation.yaml"
    if not path.is_file():
        path = root / "config" / "illustration-generation.example.yaml"
    return yaml.safe_load(path.read_text(encoding="utf-8")) if path.is_file() else {}


def _image_derivatives(master: Path, web: Path, thumb: Path, policy: dict[str, bool], domain: str,
                       style: dict[str, Any]) -> None:
    if Image is None:
        raise RuntimeError("Pillow is required for image media")
    overlay = {"enabled": bool(policy.get("domain_mark")), "type": "text_logo" if policy.get("domain_mark") else "none",
               "text_source": "domain", "domain": domain, **style}
    web.parent.mkdir(parents=True, exist_ok=True)
    thumb.parent.mkdir(parents=True, exist_ok=True)
    with Image.open(master) as image:
        converted = image.convert("RGBA")
        converted = apply_web_overlay(converted, overlay)
        background = Image.new("RGB", converted.size, (255, 255, 255))
        background.paste(converted, mask=converted.getchannel("A"))
        options = {"format": "JPEG", "quality": 88, "optimize": True, "progressive": True}
        if not policy.get("metadata_strip"):
            if image.info.get("exif"):
                options["exif"] = image.info["exif"]
            if image.info.get("icc_profile"):
                options["icc_profile"] = image.info["icc_profile"]
        background.save(web, **options)
        thumb_image = background.copy()
        thumb_image.thumbnail((480, 480), Image.Resampling.LANCZOS)
        thumb_image.save(thumb, format="JPEG", quality=82, optimize=True, progressive=True)


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


def import_plan(root: Path, plan_path: Path, approve: bool) -> int:
    if not approve:
        raise ValueError("media import is gated; pass --approve after reviewing the plan")
    catalog = load_catalog(root)
    if str(catalog.get("schema_version", "0.1")) != "0.2":
        raise ValueError("legacy image manifest must first be migrated and reviewed; source manifest is not modified")
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    entries = {str(item.get("media_id")): item for item in catalog["media"] if isinstance(item, dict)}
    style = (catalog.get("processing") or {}).get("domain_mark_style", {}) or {}
    domain = _domain(root, catalog)
    illustration_config = _illustration_profile(root)
    provider_name = str(((illustration_config.get("provider") or {}).get("default", "chatgpt_image")))
    prompt_profile = illustration_config.get("prompt_profile") or {}
    prompt_text = "\n".join(str(prompt_profile.get(key, "")).strip() for key in ("common_prompt", "style_prompt", "negative_prompt") if str(prompt_profile.get(key, "")).strip())
    imported = 0
    warnings: list[str] = []
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
        policy = effective_processing(catalog, {"type": kind, "processing": item.get("processing")})
        if kind == "image" and policy["domain_mark"] and not domain:
            raise ValueError("processing.domain is required when image domain_mark defaults to true")
        suffix = ".jpg" if kind == "image" else source.suffix.lower()
        master_rel = MASTER / f"{media_key}{source.suffix.lower()}"
        web_rel = WEB / f"{media_key}{suffix}"
        thumb_rel = THUMB / f"{media_key}.jpg" if kind == "image" else None
        master = root / master_rel
        web = root / web_rel
        if master.exists() or web.exists():
            raise ValueError(f"target exists; refusing overwrite: {media_key}")
        master.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, master)
        web.parent.mkdir(parents=True, exist_ok=True)
        if kind == "image":
            _image_derivatives(master, web, root / thumb_rel, policy, domain, style)
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
                  "processing": {**policy, "metadata_result": metadata_result, "embedded_signal_transform": False}}
        if item.get("origin") == "generated":
            record["provider"] = provider_name
            record["prompt_profile"] = str(prompt_profile.get("name", "editorial-illustration"))
        if thumb_rel:
            record["thumbnail"] = thumb_rel.as_posix()
        entries[media_key] = record
        provenance_dir = root / PROVENANCE / media_key
        provenance_dir.mkdir(parents=True, exist_ok=True)
        provenance = {"media_id": media_key, "type": kind, "origin": item.get("origin", "manual"),
                      "source_sha256": digest(master), "public_sha256": digest(web),
                      "metadata_processing": metadata_result, "embedded_signal_transform": "disabled",
                      "domain_mark": policy["domain_mark"], "source_visibility": "private",
                      "imported_at": datetime.now(timezone.utc).isoformat()}
        if item.get("origin") == "generated":
            provenance.update({"provider": provider_name, "prompt_profile": str(prompt_profile.get("name", "editorial-illustration")), "prompt": prompt_text})
        (provenance_dir / "PROVENANCE.yaml").write_text(yaml.safe_dump(provenance, sort_keys=False), encoding="utf-8", newline="\r\n")
        imported += 1
    catalog["media"] = list(entries.values())
    manifest = root / "config" / "media.manifest.yaml"
    manifest.write_text(yaml.safe_dump(catalog, allow_unicode=True, sort_keys=False), encoding="utf-8", newline="\r\n")
    print(f"MEDIA-IMPORTED {imported}")
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
        if source_cfg.get("sha256") == current_hash and public.is_file():
            continue
        print(f"SYNC {item.get('media_id', '')}: source changed or derivative missing")
        findings += 1
        if not apply:
            continue
        kind = str(item.get("type", ""))
        policy = effective_processing(catalog, item)
        if kind == "image":
            if policy["domain_mark"] and not domain:
                print(f"REVIEW_REQUIRED {item.get('media_id', '')}: processing.domain is required")
                unresolved += 1
                continue
            if not item.get("thumbnail"):
                print(f"REVIEW_REQUIRED missing thumbnail path: {item.get('media_id', '')}")
                unresolved += 1
                continue
            thumb = root / safe_path(root, str(item.get("thumbnail", "")))
            _image_derivatives(master, public, thumb, policy, domain, style)
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
        item.setdefault("processing", {})["metadata_result"] = result
        item["public_sha256"] = digest(public)
        if result.startswith("unavailable") or result.startswith("failed"):
            print(f"MEDIA-WARNING {item.get('media_id', '')}: {result}")
        changed += 1
    if apply and changed:
        manifest = root / "config" / "media.manifest.yaml"
        manifest.write_text(yaml.safe_dump(catalog, allow_unicode=True, sort_keys=False), encoding="utf-8", newline="\r\n")
    print(f"MEDIA-SYNC changed={changed} findings={findings}")
    return 1 if unresolved or (findings and not apply) else 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("scan-inbox", "import", "sync"))
    parser.add_argument("--root", default=".")
    parser.add_argument("--plan-file", default="AI/state/media-import-plan.json")
    parser.add_argument("--approve", action="store_true")
    parser.add_argument("--apply", action="store_true", help="regenerate derivatives from retained masters")
    args = parser.parse_args(argv)
    root = Path(args.root).resolve()
    try:
        plan_path = root / safe_path(root, args.plan_file)
        if args.command == "scan-inbox":
            return scan_inbox(root, plan_path)
        if args.command == "sync":
            return sync_media(root, args.apply)
        return import_plan(root, plan_path, args.approve)
    except (OSError, RuntimeError, ValueError, KeyError, json.JSONDecodeError) as exc:
        print(f"MEDIA-ERROR {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
