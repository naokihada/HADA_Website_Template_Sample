#!/usr/bin/env python3
"""Page Registry loading and safe HTML Master candidate generation."""

from __future__ import annotations

import hashlib
import html
import json
import re
from pathlib import Path
from typing import Any

import yaml
from media_library import fill_html_master_slots

MASTER_TYPES = {"html", "markdown", "generated", "project-template", "unknown", "review_required"}
UI_PROFILES = {"shared-shell", "standalone", "pwa"}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def project_paths(root: Path) -> dict[str, str]:
    config_path = root / "config" / "project.yaml"
    config = yaml.safe_load(config_path.read_text(encoding="utf-8")) if config_path.is_file() else {}
    return ((config or {}).get("paths") or {})


def load_registry(root: Path) -> dict[str, Any]:
    paths = project_paths(root)
    path = root / str(paths.get("page_registry", "config/page-registry.yaml"))
    if not path.is_file():
        return {"schema_version": "0.1", "pages": []}
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict) or not isinstance(data.get("pages", []), list):
        raise ValueError("page registry must contain a pages list")
    return data


def classify_page(page: dict[str, Any]) -> str:
    master = page.get("master") if isinstance(page.get("master"), dict) else {}
    source = page.get("source") if isinstance(page.get("source"), dict) else {}
    value = master.get("type") or source.get("type") or page.get("master_type") or "unknown"
    return str(value) if str(value) in MASTER_TYPES else "review_required"


def classify_ui_profile(page: dict[str, Any]) -> str:
    """Resolve a page's browser contract profile without guessing unsupported values."""
    value = page.get("ui_profile")
    if not value:
        return "review_required"
    return str(value) if str(value) in UI_PROFILES else "review_required"


def safe_rel(root: Path, value: str) -> Path:
    path = Path(value)
    if path.is_absolute() or ".." in path.parts:
        raise ValueError(f"unsafe registry path: {value}")
    resolved = (root / path).resolve()
    if resolved != root.resolve() and not resolved.is_relative_to(root.resolve()):
        raise ValueError(f"registry path escapes root: {value}")
    return path


def _publication_relative(root: Path, value: str) -> Path:
    publication = str(project_paths(root).get("publication_root", "site")).replace("\\", "/").strip("/")
    normalized = value.replace("\\", "/").lstrip("/")
    prefix = f"{publication}/"
    return Path(normalized[len(prefix):] if normalized.startswith(prefix) else normalized)


def _copy_with_language(source: str, locale: str) -> str:
    if locale.lower() in {"jp", "ja"}:
        return source
    return re.sub(r'(<html\b[^>]*\blang=)["\'][^"\']*(["\'])', rf'\1"{html.escape(locale)}\2', source, count=1, flags=re.I)


def build_html_masters(root: Path, candidate_root: Path) -> list[dict[str, Any]]:
    registry = load_registry(root)
    if not registry.get("pages"):
        return []
    publication = root / str(project_paths(root).get("publication_root", "site"))
    statuses: list[dict[str, Any]] = []
    for page in registry.get("pages", []):
        if not isinstance(page, dict):
            statuses.append({"status": "REVIEW_REQUIRED", "reason": "invalid page entry"})
            continue
        source = page.get("source") or {}
        if source.get("type", "markdown") != "html":
            continue
        page_id = str(page.get("page_id", ""))
        master_path = root / safe_rel(root, str(source.get("master_path", "")))
        if not page_id or not master_path.is_file():
            statuses.append({"page_id": page_id, "status": "REVIEW_REQUIRED", "reason": "missing HTML Master"})
            continue
        master_text = master_path.read_text(encoding="utf-8")
        source_hash = sha256(master_path)
        old_hash = str(source.get("source_hash", page.get("source_hash", "")))
        for locale, locale_cfg in (page.get("locales") or {}).items():
            locale_cfg = locale_cfg if isinstance(locale_cfg, dict) else {"path": str(locale_cfg)}
            target_value = str(locale_cfg.get("path", ""))
            target_rel = _publication_relative(root, target_value)
            target = candidate_root / target_rel
            existing = publication / target_rel
            if existing.is_file():
                target.parent.mkdir(parents=True, exist_ok=True)
                preserved_html = existing.read_text(encoding="utf-8")
                target.write_text(fill_html_master_slots(root, page_id, str(locale), preserved_html), encoding="utf-8", newline="\r\n")
                status = "OUTDATED" if old_hash and old_hash != source_hash else "PRESERVED"
            else:
                target.parent.mkdir(parents=True, exist_ok=True)
                source_html = _copy_with_language(master_text, str(locale))
                target.write_text(fill_html_master_slots(root, page_id, str(locale), source_html), encoding="utf-8", newline="\r\n")
                status = "SOURCE" if str(locale) == str(source.get("master_locale", "jp")) else "REVIEW_REQUIRED"
            statuses.append({"page_id": page_id, "locale": str(locale), "status": status, "source_hash": source_hash, "path": str(target_rel).replace("\\", "/")})
    report = candidate_root / ".build" / "page-status.json"
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text(json.dumps({"pages": statuses}, indent=2) + "\n", encoding="utf-8", newline="\r\n")
    return statuses
