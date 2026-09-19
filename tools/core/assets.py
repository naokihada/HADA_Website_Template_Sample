#!/usr/bin/env python3
"""Reviewable image intake, conversion, synchronization and validation."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError:
    yaml = None  # type: ignore[assignment]

try:
    from PIL import Image
except ImportError:
    Image = None  # type: ignore[assignment]


IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".avif"}
GENERATED_EXTENSIONS = {".png"}
IMAGE_ID_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{1,95}$")
MANIFEST_REL = Path("config/media.manifest.yaml")
GENERATION_CONFIG_REL = Path("config/image-generation.yaml")
MASTER_ROOT = Path("assets/images/master")
WEB_ROOT = Path("assets/images/web")
THUMB_ROOT = Path("assets/images/thumbnails")
METADATA_ROOT = Path("assets/metadata/images")
INBOX_ROOT = Path("AI/inbox/assets")
LEGACY_PROVENANCE_ROOT = Path("AI/history/assets")


def fail(message: str) -> int:
    print(f"ASSET-ERROR {message}", file=sys.stderr)
    return 2


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def safe_relative(root: Path, value: str) -> Path:
    candidate = Path(value)
    if candidate.is_absolute() or ".." in candidate.parts:
        raise ValueError(f"unsafe path: {value}")
    resolved = (root / candidate).resolve()
    if resolved != root.resolve() and not resolved.is_relative_to(root.resolve()):
        raise ValueError(f"path escapes root: {value}")
    return candidate


def image_id_from(path: Path) -> str:
    value = re.sub(r"[^a-z0-9_-]+", "-", path.stem.lower()).strip("-")
    value = value or "image"
    if len(value) < 2:
        value = f"{value}-01"
    return value[:96]


def load_manifest(root: Path) -> dict[str, Any]:
    path = root / MANIFEST_REL
    if not path.is_file():
        return {"schema_version": "0.1", "images": []}
    if yaml is None:
        raise RuntimeError("PyYAML is required")
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        raise ValueError("media manifest must be a mapping")
    images = data.get("images", [])
    if not isinstance(images, list):
        raise ValueError("media manifest images must be a list")
    data["images"] = images
    return data


def load_generation_config(root: Path) -> dict[str, Any]:
    path = root / GENERATION_CONFIG_REL
    if not path.is_file():
        return {"provider": {"default": "chatgpt_image"}, "prompt_profile": {"name": "default-editorial"}}
    if yaml is None:
        raise RuntimeError("PyYAML is required")
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        raise ValueError("image generation config must be a mapping")
    return data


def write_manifest(root: Path, data: dict[str, Any]) -> None:
    if yaml is None:
        raise RuntimeError("PyYAML is required")
    path = root / MANIFEST_REL
    path.parent.mkdir(parents=True, exist_ok=True)
    text = yaml.safe_dump(data, allow_unicode=True, sort_keys=False)
    path.write_text(text, encoding="utf-8", newline="\r\n")


def write_provenance(
    root: Path,
    image_id: str,
    source: Path,
    route: str,
    provider: str,
    prompt_profile: str,
    prompt: str,
) -> None:
    if yaml is None:
        raise RuntimeError("PyYAML is required")
    directory = root / METADATA_ROOT / image_id
    directory.mkdir(parents=True, exist_ok=True)
    record = {
        "image_id": image_id,
        "source_route": route,
        "source_filename": source.name,
        "source_sha256": sha256(source),
        "provider": provider,
        "prompt_profile": prompt_profile,
        "prompt": prompt,
        "imported_at": datetime.now(timezone.utc).isoformat(),
        "tracking_metadata_policy": "stripped from web derivative",
        "review": "human approval recorded by assets.py --approve",
    }
    (directory / "PROVENANCE.yaml").write_text(
        yaml.safe_dump(record, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
        newline="\r\n",
    )


def convert_to_jpeg(source: Path, target: Path) -> None:
    if Image is None:
        raise RuntimeError("Pillow is required")
    target.parent.mkdir(parents=True, exist_ok=True)
    with Image.open(source) as image:
        converted = image.convert("RGBA")
        background = Image.new("RGB", converted.size, (255, 255, 255))
        background.paste(converted, mask=converted.getchannel("A"))
        # Saving a new image object with no info dict prevents source/provider
        # metadata from being copied to the published derivative.
        background.save(target, format="JPEG", quality=88, optimize=True, progressive=True)


def create_thumbnail(source: Path, target: Path) -> None:
    if Image is None:
        raise RuntimeError("Pillow is required")
    target.parent.mkdir(parents=True, exist_ok=True)
    with Image.open(source) as image:
        converted = image.convert("RGB")
        converted.thumbnail((480, 480), Image.Resampling.LANCZOS)
        converted.save(target, format="JPEG", quality=82, optimize=True, progressive=True)


def inbox_files(root: Path) -> list[tuple[Path, str]]:
    found: list[tuple[Path, str]] = []
    for route in ("generated", "manual"):
        directory = root / INBOX_ROOT / route
        if not directory.is_dir():
            continue
        for path in sorted(directory.rglob("*")):
            if path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS:
                found.append((path, route))
    return found


def scan_inbox(root: Path, plan_path: Path) -> int:
    manifest = load_manifest(root)
    known = {str(item.get("image_id")): item for item in manifest["images"] if isinstance(item, dict)}
    plan: list[dict[str, Any]] = []
    for source, route in inbox_files(root):
        image_id = image_id_from(source)
        issues: list[str] = []
        if route == "generated" and source.suffix.lower() not in GENERATED_EXTENSIONS:
            issues.append("generated input must be PNG")
        if image_id in known:
            issues.append("image_id already exists")
        plan.append(
            {
                "image_id": image_id,
                "source": str(source.relative_to(root)).replace("\\", "/"),
                "route": route,
                "status": "review_required" if issues else "pending_approval",
                "issues": issues,
            }
        )
    plan_path.parent.mkdir(parents=True, exist_ok=True)
    plan_path.write_text(json.dumps({"schema_version": "0.1", "items": plan}, indent=2) + "\n", encoding="utf-8", newline="\r\n")
    print(json.dumps({"plan": str(plan_path), "items": len(plan)}, indent=2))
    return 0


def read_plan(root: Path, plan_path: Path) -> list[dict[str, Any]]:
    data = json.loads(plan_path.read_text(encoding="utf-8"))
    items = data.get("items", [])
    if not isinstance(items, list):
        raise ValueError("plan items must be a list")
    for item in items:
        safe_relative(root, str(item["source"]))
    return items


def import_plan(root: Path, plan_path: Path, approve: bool, prompt_file: Path | None = None) -> int:
    if not approve:
        return fail("import is gated; pass --approve after reviewing the plan")
    manifest = load_manifest(root)
    generation_config = load_generation_config(root)
    provider_config = generation_config.get("provider") or {}
    profile_config = generation_config.get("prompt_profile") or {}
    default_provider = str(provider_config.get("default", "chatgpt_image"))
    default_profile = str(profile_config.get("name", "default-editorial"))
    configured_prompt = "\n".join(
        str(profile_config.get(key, "")).strip()
        for key in ("common_prompt", "style_prompt", "negative_prompt")
        if str(profile_config.get(key, "")).strip()
    )
    prompt = prompt_file.read_text(encoding="utf-8") if prompt_file and prompt_file.is_file() else configured_prompt
    entries = {str(item.get("image_id")): item for item in manifest["images"] if isinstance(item, dict)}
    skipped = 0
    for item in read_plan(root, plan_path):
        if item.get("status") == "review_required":
            print(f"SKIP REVIEW_REQUIRED {item.get('image_id', '')}: {', '.join(item.get('issues', []))}")
            skipped += 1
            continue
        image_id = str(item["image_id"])
        source = root / safe_relative(root, str(item["source"]))
        route = str(item.get("route", "manual"))
        if not source.is_file():
            return fail(f"missing source: {source}")
        if image_id in entries:
            return fail(f"image_id already exists: {image_id}")
        if route == "generated" and source.suffix.lower() not in GENERATED_EXTENSIONS:
            return fail(f"generated input must be PNG: {source}")
        master_suffix = ".png" if route == "generated" else source.suffix.lower()
        master_rel = MASTER_ROOT / f"{image_id}{master_suffix}"
        web_rel = WEB_ROOT / f"{image_id}.jpg"
        thumbnail_rel = THUMB_ROOT / f"{image_id}.jpg"
        master = root / master_rel
        web = root / web_rel
        thumbnail = root / thumbnail_rel
        master.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, master)
        convert_to_jpeg(master, web)
        create_thumbnail(master, thumbnail)
        provider = str(item.get("provider", default_provider))
        prompt_profile = str(item.get("prompt_profile", default_profile))
        write_provenance(root, image_id, source, route, provider, prompt_profile, prompt)
        entries[image_id] = {
            "image_id": image_id,
            "master": str(master_rel).replace("\\", "/"),
            "web": str(web_rel).replace("\\", "/"),
            "thumbnail": str(thumbnail_rel).replace("\\", "/"),
            "source": provider if route == "generated" else "manual",
            "provider": provider,
            "prompt_profile": prompt_profile,
            "usage": "background_fade",
            "composition": "square",
            "status": "approved",
            "license": "generated" if route == "generated" else "documented",
            "master_sha256": f"sha256:{sha256(master)}",
            "web_sha256": f"sha256:{sha256(web)}",
            "thumbnail_sha256": f"sha256:{sha256(thumbnail)}",
        }
    manifest["images"] = list(entries.values())
    write_manifest(root, manifest)
    print(f"IMPORTED {len(read_plan(root, plan_path)) - skipped} asset(s), skipped={skipped}")
    return 1 if skipped else 0


def sync_assets(root: Path, apply: bool) -> int:
    manifest = load_manifest(root)
    findings: list[str] = []
    changed = 0
    for item in manifest["images"]:
        if not isinstance(item, dict):
            findings.append("REVIEW_REQUIRED invalid registry entry")
            continue
        image_id = str(item.get("image_id", ""))
        if not IMAGE_ID_RE.fullmatch(image_id):
            findings.append(f"REVIEW_REQUIRED invalid image_id: {image_id}")
            continue
        master_rel = safe_relative(root, str(item.get("master", "")))
        web_rel = safe_relative(root, str(item.get("web", "")))
        thumbnail_rel = safe_relative(root, str(item.get("thumbnail", "")))
        master = root / master_rel
        web = root / web_rel
        thumbnail = root / thumbnail_rel
        if not master.is_file():
            findings.append(f"REVIEW_REQUIRED missing master: {image_id}")
            continue
        current_master = f"sha256:{sha256(master)}"
        if item.get("master_sha256") != current_master:
            findings.append(f"CHANGED master: {image_id}")
            if apply and item.get("status") == "approved":
                convert_to_jpeg(master, web)
                create_thumbnail(master, thumbnail)
                item["master_sha256"] = current_master
                item["web_sha256"] = f"sha256:{sha256(web)}"
                item["thumbnail_sha256"] = f"sha256:{sha256(thumbnail)}"
                changed += 1
        elif not web.is_file() or not thumbnail.is_file():
            findings.append(f"MISSING derivative: {image_id}")
            if apply and item.get("status") == "approved":
                convert_to_jpeg(master, web)
                create_thumbnail(master, thumbnail)
                item["web_sha256"] = f"sha256:{sha256(web)}"
                item["thumbnail_sha256"] = f"sha256:{sha256(thumbnail)}"
                changed += 1
    if apply and changed:
        write_manifest(root, manifest)
    for finding in findings:
        print(finding)
    print(f"SYNC changed={changed} findings={len(findings)}")
    return 1 if findings else 0


def validate_assets(root: Path) -> int:
    manifest = load_manifest(root)
    errors: list[str] = []
    ids: set[str] = set()
    for item in manifest["images"]:
        if not isinstance(item, dict):
            errors.append("invalid registry entry")
            continue
        image_id = str(item.get("image_id", ""))
        if not IMAGE_ID_RE.fullmatch(image_id) or image_id in ids:
            errors.append(f"invalid or duplicate image_id: {image_id}")
        ids.add(image_id)
        try:
            master_rel = safe_relative(root, str(item.get("master", "")))
            web_rel = safe_relative(root, str(item.get("web", "")))
            thumbnail_rel = safe_relative(root, str(item.get("thumbnail", "")))
        except ValueError as exc:
            errors.append(str(exc))
            continue
        master_text = str(master_rel).replace("\\", "/")
        web_text = str(web_rel).replace("\\", "/")
        thumbnail_text = str(thumbnail_rel).replace("\\", "/")
        if not master_text.startswith(f"{MASTER_ROOT.as_posix()}/"):
            errors.append(f"master outside master policy: {image_id}")
        if not web_text.startswith(f"{WEB_ROOT.as_posix()}/"):
            errors.append(f"web points to non-web asset: {image_id}")
        if not thumbnail_text.startswith(f"{THUMB_ROOT.as_posix()}/"):
            errors.append(f"thumbnail outside thumbnail policy: {image_id}")
        master, web = root / master_rel, root / web_rel
        thumbnail = root / thumbnail_rel
        if item.get("status") != "approved":
            continue
        provenance = root / METADATA_ROOT / image_id / "PROVENANCE.yaml"
        if not provenance.is_file():
            errors.append(f"approved asset missing provenance: {image_id}")
        if not master.is_file() or not web.is_file() or not thumbnail.is_file():
            errors.append(f"approved asset missing file: {image_id}")
            continue
        if Path(web).suffix.lower() != ".jpg":
            errors.append(f"web derivative must be JPEG: {image_id}")
        if item.get("master_sha256") != f"sha256:{sha256(master)}":
            errors.append(f"master hash mismatch: {image_id}")
        if item.get("web_sha256") != f"sha256:{sha256(web)}":
            errors.append(f"web hash mismatch: {image_id}")
        if item.get("thumbnail_sha256") != f"sha256:{sha256(thumbnail)}":
            errors.append(f"thumbnail hash mismatch: {image_id}")
        if Image is not None:
            with Image.open(web) as image:
                forbidden_metadata = {
                    "comment",
                    "exif",
                    "icc_profile",
                    "parameters",
                    "prompt",
                    "provider_tracking_id",
                    "software",
                    "xmp",
                }
                if forbidden_metadata.intersection(image.info):
                    errors.append(f"web derivative contains provider metadata: {image_id}")
            with Image.open(thumbnail) as image:
                if forbidden_metadata.intersection(image.info):
                    errors.append(f"thumbnail contains provider metadata: {image_id}")
    for path in (root / INBOX_ROOT, root / MASTER_ROOT):
        if path.is_dir():
            for candidate in path.rglob("*"):
                if candidate.is_file() and candidate.suffix.lower() in IMAGE_EXTENSIONS:
                    if candidate.parent == root / INBOX_ROOT or candidate.is_relative_to(root / MASTER_ROOT):
                        continue
    if errors:
        for error in errors:
            print(f"ASSET-ERROR {error}")
        return 1
    print(f"ASSET-VALIDATION passed images={len(manifest['images'])}")
    return 0


def migrate_legacy_provenance(root: Path, apply: bool) -> int:
    """Copy legacy AI provenance to persistent metadata without deleting evidence."""
    legacy_root = root / LEGACY_PROVENANCE_ROOT
    findings: list[str] = []
    migrated = 0
    if legacy_root.is_dir():
        for source in sorted(legacy_root.glob("*/PROVENANCE.yaml")):
            image_id = source.parent.name
            target = root / METADATA_ROOT / image_id / "PROVENANCE.yaml"
            if target.exists():
                continue
            findings.append(f"MIGRATE {source.relative_to(root)} -> {target.relative_to(root)}")
            if apply:
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, target)
                migrated += 1
    for finding in findings:
        print(finding)
    print(f"PROVENANCE-MIGRATION migrated={migrated} findings={len(findings)}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("scan-inbox", "import", "sync", "validate", "migrate-provenance"))
    parser.add_argument("--root", default=".")
    parser.add_argument("--plan-file", default="AI/state/assets-import-plan.json")
    parser.add_argument("--approve", action="store_true")
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--prompt-file", help="Persistent prompt text to record with an import")
    args = parser.parse_args(argv)
    root = Path(args.root).resolve()
    try:
        if args.command == "scan-inbox":
            return scan_inbox(root, root / safe_relative(root, args.plan_file))
        if args.command == "import":
            prompt_file = root / safe_relative(root, args.prompt_file) if args.prompt_file else None
            return import_plan(root, root / safe_relative(root, args.plan_file), args.approve, prompt_file)
        if args.command == "sync":
            return sync_assets(root, args.apply)
        if args.command == "migrate-provenance":
            return migrate_legacy_provenance(root, args.apply)
        return validate_assets(root)
    except (OSError, RuntimeError, ValueError, KeyError, json.JSONDecodeError) as exc:
        return fail(str(exc))


if __name__ == "__main__":
    raise SystemExit(main())
