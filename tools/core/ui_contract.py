#!/usr/bin/env python3
"""Route discovery and deterministic UI-profile helpers for browser contracts."""

from __future__ import annotations

import re
from html.parser import HTMLParser
from pathlib import Path
from typing import Any

from page_registry import UI_PROFILES, load_registry, project_paths
from site_contract import publication_path, resolve_site

class ContractParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.tags: list[str] = []
        self.title = ""
        self.links: list[dict[str, str]] = []
        self.profile = ""
        self._in_title = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag_name = tag.lower()
        self.tags.append(tag_name)
        values = {str(key).lower(): str(value or "") for key, value in attrs}
        if tag_name == "body":
            self.profile = values.get("data-ui-profile", "")
        if tag_name == "title":
            self._in_title = True
        if tag_name == "a":
            self.links.append({"href": values.get("href", ""), "target": values.get("target", ""), "rel": values.get("rel", "")})

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() == "title":
            self._in_title = False

    def handle_data(self, data: str) -> None:
        if self._in_title:
            self.title += data


def parse_html(text: str) -> dict[str, Any]:
    parser = ContractParser()
    parser.feed(text)
    return {
        "tags": parser.tags,
        "title": parser.title.strip(),
        "links": parser.links,
        "profile": parser.profile,
    }


def _normalize(value: str) -> str:
    return value.replace("\\", "/").lstrip("./").strip("/")


def publication_relative(root: Path, value: str) -> str:
    publication = _normalize(str(project_paths(root).get("publication_root", "site")))
    normalized = _normalize(value)
    prefix = publication + "/"
    return normalized[len(prefix):] if normalized.startswith(prefix) else normalized


def registry_profiles(root: Path) -> dict[str, dict[str, Any]]:
    """Return publication-relative route metadata from the Page Registry."""
    result: dict[str, dict[str, Any]] = {}
    registry = load_registry(root)
    for page in registry.get("pages", []):
        if not isinstance(page, dict):
            continue
        page_id = str(page.get("page_id", ""))
        profile = str(page.get("ui_profile", ""))
        for locale, locale_cfg in (page.get("locales") or {}).items():
            cfg = locale_cfg if isinstance(locale_cfg, dict) else {"path": str(locale_cfg)}
            path = str(cfg.get("path", ""))
            if not path:
                continue
            local_profile = str(cfg.get("ui_profile") or cfg.get("profile") or profile)
            result[publication_relative(root, path)] = {
                "page_id": page_id,
                "locale": str(locale),
                "profile": local_profile,
                "source": "registry",
            }
    return result


def route_inventory(root: Path, publication: Path | None = None) -> list[dict[str, Any]]:
    """Discover every publication HTML route and resolve its UI profile."""
    publication = publication or publication_path(root)
    registry = registry_profiles(root)
    routes: list[dict[str, Any]] = []
    if not publication.is_dir():
        return routes
    for path in sorted(publication.rglob("*.html")):
        relative = path.relative_to(publication).as_posix()
        parsed = parse_html(path.read_text(encoding="utf-8"))
        metadata = dict(registry.get(relative, {}))
        profile = metadata.get("profile") or parsed.get("profile") or "review_required"
        routes.append({
            "route": relative,
            "path": path,
            "profile": profile if profile in UI_PROFILES else "review_required",
            "declared_profile": profile,
            "page_id": metadata.get("page_id"),
            "source": metadata.get("source", "html" if parsed.get("profile") else "undecclared"),
            "title": parsed.get("title", ""),
        })
    return routes


def browser_config(root: Path) -> dict[str, Any]:
    site = resolve_site(root)
    config = site.get("browser")
    return config if isinstance(config, dict) else {}


def configured_viewports(root: Path) -> list[dict[str, int]]:
    configured = browser_config(root).get("viewports")
    if not isinstance(configured, list):
        return [{"width": 1920, "height": 1080}, {"width": 390, "height": 844}]
    result: list[dict[str, int]] = []
    for item in configured:
        if not isinstance(item, dict):
            continue
        try:
            width, height = int(item["width"]), int(item["height"])
        except (KeyError, TypeError, ValueError):
            continue
        if width > 0 and height > 0:
            result.append({"width": width, "height": height})
    return result or [{"width": 1920, "height": 1080}, {"width": 390, "height": 844}]


def external_links(links: list[dict[str, str]]) -> list[dict[str, str]]:
    return [link for link in links if re.match(r"^https?://", link.get("href", ""), re.IGNORECASE)]
