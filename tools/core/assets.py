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
from urllib.parse import urlparse

try:
    import yaml
except ImportError:
    yaml = None  # type: ignore[assignment]

try:
    from PIL import Image, ImageDraw, ImageFont
except ImportError:
    Image = None  # type: ignore[assignment]
    ImageDraw = None  # type: ignore[assignment]
    ImageFont = None  # type: ignore[assignment]


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
OVERLAY_TYPES = {"none", "text_logo"}
OVERLAY_POSITIONS = {"bottom-left", "bottom-right", "top-left", "top-right"}


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


def effective_overlay_config(generation_config: dict[str, Any]) -> dict[str, Any]:
    """Return normalized Web-derivative overlay settings."""
    configured = generation_config.get("web_overlay")
    values = configured if isinstance(configured, dict) else {}
    defaults: dict[str, Any] = {
        "enabled": False,
        "type": "none",
        "text_source": "domain",
        "domain": "",
        "text": "",
        "uppercase": True,
        "omit_www_prefix": True,
        "position": "bottom-left",
        "color": "#ffffff",
        "opacity": 0.88,
        "shadow_color": "#000000",
        "shadow_opacity": 0.38,
        "font_size_ratio": 0.035,
        "margin_ratio": 0.025,
    }
    defaults.update(values)
    if not defaults["enabled"]:
        defaults["type"] = "none"
    return defaults


def validate_overlay_config(config: dict[str, Any]) -> list[str]:
    """Validate settings that affect only published Web derivatives."""
    errors: list[str] = []
    if not isinstance(config.get("enabled"), bool):
        errors.append("web_overlay.enabled must be boolean")
    if config.get("type") not in OVERLAY_TYPES:
        errors.append("web_overlay.type must be none or text_logo")
    if config.get("position") not in OVERLAY_POSITIONS:
        errors.append("web_overlay.position is invalid")
    for key in ("opacity", "shadow_opacity"):
        value = config.get(key)
        if not isinstance(value, (int, float)) or not 0 <= float(value) <= 1:
            errors.append(f"web_overlay.{key} must be between 0 and 1")
    for key in ("font_size_ratio", "margin_ratio"):
        value = config.get(key)
        if not isinstance(value, (int, float)) or not 0 < float(value) <= 0.25:
            errors.append(f"web_overlay.{key} must be greater than 0 and at most 0.25")
    if config.get("enabled") and config.get("type") == "text_logo":
        if config.get("text_source") not in {"domain", "text"}:
            errors.append("web_overlay.text_source must be domain or text")
        if config.get("text_source") == "domain" and not str(config.get("domain", "")).strip():
            errors.append("web_overlay.domain is required for domain text_source")
        if config.get("text_source") == "text" and not str(config.get("text", "")).strip():
            errors.append("web_overlay.text is required for text text_source")
    return errors


def overlay_text(config: dict[str, Any]) -> str:
    """Resolve a stable logo label without retaining URL paths or credentials."""
    if config.get("text_source") == "text":
        value = str(config.get("text", "")).strip()
    else:
        raw = str(config.get("domain", "")).strip()
        parsed = urlparse(raw if "://" in raw else f"//{raw}")
        value = (parsed.hostname or raw.split("/", 1)[0]).strip().lower()
        if config.get("omit_www_prefix") and value.startswith("www."):
            value = value[4:]
    return value.upper() if config.get("uppercase", True) else value


def overlay_fingerprint(config: dict[str, Any]) -> str:
    """Hash normalized overlay settings for deterministic derivative sync."""
    payload = json.dumps(config, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
    return f"sha256:{hashlib.sha256(payload.encode('utf-8')).hexdigest()}"


def _color(value: Any, alpha: float = 1.0) -> tuple[int, int, int, int]:
    text = str(value or "#ffffff").strip().lstrip("#")
    if len(text) == 3:
        text = "".join(char * 2 for char in text)
    if len(text) != 6 or not re.fullmatch(r"[0-9a-fA-F]{6}", text):
        raise ValueError(f"invalid overlay color: {value}")
    return tuple(int(text[index : index + 2], 16) for index in (0, 2, 4)) + (round(255 * alpha),)


def _font(config: dict[str, Any], size: int) -> Any:
    if ImageFont is None:
        raise RuntimeError("Pillow is required")
    configured = str(config.get("font_path", "")).strip()
    if configured:
        path = Path(configured)
        if path.is_file():
            return ImageFont.truetype(str(path), size=size)
    try:
        return ImageFont.truetype("DejaVuSans.ttf", size=size)
    except OSError:
        return ImageFont.load_default()


def apply_web_overlay(image: Any, config: dict[str, Any]) -> Any:
    """Apply an optional text logo to a Web derivative only."""
    if Image is None or ImageDraw is None:
        raise RuntimeError("Pillow is required")
    base = image.convert("RGBA")
    if not config.get("enabled") or config.get("type") == "none":
        return base
    text = overlay_text(config)
    if not text:
        return base
    width, height = base.size
    minimum = min(width, height)
    size = max(12, round(minimum * float(config.get("font_size_ratio", 0.035))))
    margin = max(4, round(minimum * float(config.get("margin_ratio", 0.025))))
    font = _font(config, size)
    draw = ImageDraw.Draw(base)
    left, top, right, bottom = draw.textbbox((0, 0), text, font=font)
    text_width, text_height = right - left, bottom - top
    position = str(config.get("position", "bottom-left"))
    x = margin if position.endswith("left") else width - text_width - margin
    y = margin if position.startswith("top") else height - text_height - margin
    shadow = _color(config.get("shadow_color"), float(config.get("shadow_opacity", 0.38)))
    foreground = _color(config.get("color"), float(config.get("opacity", 0.88)))
    draw.text((x + 2, y + 2), text, font=font, fill=shadow)
    draw.text((x, y), text, font=font, fill=foreground)
    return base


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
    overlay_config: dict[str, Any],
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
        "web_overlay_fingerprint": overlay_fingerprint(overlay_config),
        "web_overlay": overlay_config,
        "review": "human approval recorded by assets.py --approve",
    }
    (directory / "PROVENANCE.yaml").write_text(
        yaml.safe_dump(record, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
        newline="\r\n",
    )


def convert_to_jpeg(source: Path, target: Path, overlay_config: dict[str, Any] | None = None) -> None:
    if Image is None:
        raise RuntimeError("Pillow is required")
    target.parent.mkdir(parents=True, exist_ok=True)
    with Image.open(source) as image:
        converted = apply_web_overlay(image, overlay_config or effective_overlay_config({}))
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
    overlay_config = effective_overlay_config(generation_config)
    overlay_errors = validate_overlay_config(overlay_config)
    if overlay_errors:
        return fail("; ".join(overlay_errors))
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
        convert_to_jpeg(master, web, overlay_config)
        create_thumbnail(master, thumbnail)
        provider = str(item.get("provider", default_provider))
        prompt_profile = str(item.get("prompt_profile", default_profile))
        write_provenance(root, image_id, source, route, provider, prompt_profile, prompt, overlay_config)
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
            "web_overlay_fingerprint": overlay_fingerprint(overlay_config),
        }
    manifest["images"] = list(entries.values())
    write_manifest(root, manifest)
    print(f"IMPORTED {len(read_plan(root, plan_path)) - skipped} asset(s), skipped={skipped}")
    return 1 if skipped else 0


def sync_assets(root: Path, apply: bool) -> int:
    manifest = load_manifest(root)
    overlay_config = effective_overlay_config(load_generation_config(root))
    overlay_errors = validate_overlay_config(overlay_config)
    if overlay_errors:
        return fail("; ".join(overlay_errors))
    current_overlay_fingerprint = overlay_fingerprint(overlay_config)
    findings: list[str] = []
    changed = 0
    unresolved = 0
    for item in manifest["images"]:
        if not isinstance(item, dict):
            findings.append("REVIEW_REQUIRED invalid registry entry")
            unresolved += 1
            continue
        image_id = str(item.get("image_id", ""))
        if not IMAGE_ID_RE.fullmatch(image_id):
            findings.append(f"REVIEW_REQUIRED invalid image_id: {image_id}")
            unresolved += 1
            continue
        master_rel = safe_relative(root, str(item.get("master", "")))
        web_rel = safe_relative(root, str(item.get("web", "")))
        thumbnail_rel = safe_relative(root, str(item.get("thumbnail", "")))
        master = root / master_rel
        web = root / web_rel
        thumbnail = root / thumbnail_rel
        if not master.is_file():
            findings.append(f"REVIEW_REQUIRED missing master: {image_id}")
            unresolved += 1
            continue
        current_master = f"sha256:{sha256(master)}"
        if item.get("master_sha256") != current_master:
            findings.append(f"CHANGED master: {image_id}")
            if apply and item.get("status") == "approved":
                convert_to_jpeg(master, web, overlay_config)
                create_thumbnail(master, thumbnail)
                item["master_sha256"] = current_master
                item["web_sha256"] = f"sha256:{sha256(web)}"
                item["thumbnail_sha256"] = f"sha256:{sha256(thumbnail)}"
                item["web_overlay_fingerprint"] = current_overlay_fingerprint
                changed += 1
            else:
                unresolved += 1
        elif (
            not web.is_file()
            or not thumbnail.is_file()
            or (overlay_config.get("enabled") and item.get("web_overlay_fingerprint") != current_overlay_fingerprint)
        ):
            findings.append(f"MISSING derivative: {image_id}")
            if apply and item.get("status") == "approved":
                convert_to_jpeg(master, web, overlay_config)
                create_thumbnail(master, thumbnail)
                item["web_sha256"] = f"sha256:{sha256(web)}"
                item["thumbnail_sha256"] = f"sha256:{sha256(thumbnail)}"
                item["web_overlay_fingerprint"] = current_overlay_fingerprint
                changed += 1
            else:
                unresolved += 1
        elif item.get("web_overlay_fingerprint") and item.get("web_overlay_fingerprint") != current_overlay_fingerprint:
            findings.append(f"OVERLAY CONFIGURATION CHANGED: {image_id}")
            if apply and item.get("status") == "approved":
                convert_to_jpeg(master, web, overlay_config)
                item["web_sha256"] = f"sha256:{sha256(web)}"
                item["web_overlay_fingerprint"] = current_overlay_fingerprint
                changed += 1
            else:
                unresolved += 1
    if apply and changed:
        write_manifest(root, manifest)
    for finding in findings:
        print(finding)
    print(f"SYNC changed={changed} findings={len(findings)}")
    return 1 if unresolved else 0


def validate_assets(root: Path) -> int:
    manifest = load_manifest(root)
    overlay_config = effective_overlay_config(load_generation_config(root))
    overlay_errors = validate_overlay_config(overlay_config)
    errors: list[str] = []
    errors.extend(overlay_errors)
    current_overlay_fingerprint = overlay_fingerprint(overlay_config)
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
        if overlay_config.get("enabled") and item.get("web_overlay_fingerprint") != current_overlay_fingerprint:
            errors.append(f"web overlay fingerprint mismatch: {image_id}")
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
