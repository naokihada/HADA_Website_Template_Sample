#!/usr/bin/env python3
"""Configuration and link-policy helpers for generated image galleries."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from site_link_policy import site_url

try:
    import yaml
except ImportError:  # pragma: no cover - dependency is validated by the framework
    yaml = None  # type: ignore[assignment]


SUPPORTED_CARD_LINK_TYPES = {"html_detail", "direct_image"}
DEFAULT_SETTINGS: dict[str, Any] = {
    "enabled": True,
    "route": "gallery",
    "card_link_type": "html_detail",
    "direct_image_links": False,
    "detail_path": "/{locale}/{route}/{image_id}.html",
}


def load_gallery_settings(root: Path) -> dict[str, Any]:
    """Load gallery settings and apply safe defaults."""
    path = root / "config" / "gallery.yaml"
    if not path.is_file() or yaml is None:
        return dict(DEFAULT_SETTINGS)
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        return dict(DEFAULT_SETTINGS)
    settings = dict(DEFAULT_SETTINGS)
    configured = data.get("gallery")
    if isinstance(configured, dict):
        settings.update(configured)
    return settings


def validate_gallery_settings(settings: dict[str, Any]) -> list[str]:
    """Return deterministic configuration errors for gallery link behavior."""
    errors: list[str] = []
    link_type = settings.get("card_link_type", "html_detail")
    direct = settings.get("direct_image_links", False)
    detail_path = settings.get("detail_path", "/{locale}/{route}/{image_id}.html")
    if link_type not in SUPPORTED_CARD_LINK_TYPES:
        errors.append("gallery.card_link_type must be html_detail or direct_image")
    if not isinstance(direct, bool):
        errors.append("gallery.direct_image_links must be boolean")
    elif link_type == "html_detail" and direct:
        errors.append("gallery.direct_image_links must be false when card_link_type is html_detail")
    elif link_type == "direct_image" and not direct:
        errors.append("gallery.direct_image_links must be true when card_link_type is direct_image")
    if not isinstance(detail_path, str) or "{image_id}" not in detail_path:
        errors.append("gallery.detail_path must contain {image_id}")
    elif not detail_path.startswith("/"):
        errors.append("gallery.detail_path must be root-relative")
    elif ".." in Path(detail_path).parts:
        errors.append("gallery.detail_path must not escape the gallery route")
    return errors


def gallery_card_href(
    settings: dict[str, Any],
    image_id: str,
    web_filename: str,
    locale: str = "en",
    link_policy: dict[str, Any] | None = None,
) -> str:
    """Return the configured card destination from the gallery index."""
    errors = validate_gallery_settings(settings)
    if errors:
        raise ValueError("; ".join(errors))
    if settings.get("card_link_type") == "direct_image":
        return site_url(f"/assets/images/{web_filename}", link_policy)
    route = str(settings.get("route", "gallery")).strip("/") or "gallery"
    detail_path = str(settings.get("detail_path", "/{locale}/{route}/{image_id}.html"))
    detail_path = (
        detail_path.replace("{image_id}", image_id)
        .replace("{locale}", locale)
        .replace("{route}", route)
    )
    return site_url(detail_path, link_policy)
