#!/usr/bin/env python3
"""Resolve the safe site contract for custom publication-root projects."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml


SCAFFOLDS = {"present", "absent", "managed"}


def load_project(root: Path) -> dict[str, Any]:
    path = root / "config" / "project.yaml"
    if not path.is_file():
        return {}
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return data if isinstance(data, dict) else {}


def resolve_site(root: Path) -> dict[str, Any]:
    data = load_project(root)
    site = data.get("site") if isinstance(data.get("site"), dict) else {}
    paths = data.get("paths") if isinstance(data.get("paths"), dict) else {}
    publication = str(site.get("publication_root") or paths.get("publication_root") or "site")
    scaffold = str(site.get("template_scaffold") or ("present" if publication == "site" else "managed"))
    return {
        "id": site.get("id"),
        "name": site.get("name"),
        "public_url": site.get("public_url"),
        "test_url": site.get("test_url"),
        "repository": site.get("repository"),
        "deploy_target": site.get("deploy_target", "manual"),
        "publication_root": publication,
        "template_scaffold": scaffold,
        "generated_root": str(paths.get("generated_root") or "build"),
        "page_registry": str(paths.get("page_registry") or "config/page-registry.yaml"),
        "template_references": str(paths.get("template_references") or "references/template-releases"),
    }


def publication_path(root: Path) -> Path:
    value = Path(resolve_site(root)["publication_root"])
    if value.is_absolute() or ".." in value.parts:
        raise ValueError("publication_root must stay inside the repository")
    return root / value


def allows_absent_scaffold(root: Path) -> bool:
    site = resolve_site(root)
    return site["template_scaffold"] == "absent" and site["publication_root"] != "site"
