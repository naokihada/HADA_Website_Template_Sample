#!/usr/bin/env python3
"""Validate optional Core display configuration."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml


THEMES = {"light", "dark"}
TEXT_SIZES = {"standard", "large", "xlarge"}
STORAGE_TYPES = {"none", "local_storage"}
DEFAULT_STORAGE_KEY = "hada.display.v1"


def load_display_config(root: Path) -> dict[str, Any]:
    """Load project display settings, falling back to the committed example."""
    candidates = (root / "config" / "display.yaml", root / "config" / "display.example.yaml")
    for path in candidates:
        if path.is_file():
            data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
            if not isinstance(data, dict):
                raise ValueError(f"display configuration root must be a mapping: {path}")
            return data
    return {}


def display_runtime_settings(root: Path) -> dict[str, Any]:
    """Return the small, serializable state contract embedded in generated pages."""
    data = load_display_config(root)
    display = data.get("display") or {}
    persistence = display.get("persistence") or {}
    enabled = persistence.get("enabled", True)
    storage = persistence.get("storage", "local_storage" if enabled else "none")
    return {
        "persistence_enabled": enabled is True and storage == "local_storage",
        "storage": storage,
        "storage_key": str(persistence.get("key", DEFAULT_STORAGE_KEY)),
    }


def validate_display(data: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    display = data.get("display") or {}
    theme = display.get("theme") or {}
    text_size = display.get("text_size") or {}
    mode = display.get("mode") or {}
    persistence = display.get("persistence") or {}
    javascript = data.get("javascript") or {}
    accessibility = display.get("accessibility") or {}
    if display.get("enabled") not in (None, True, False):
        errors.append("display.enabled must be boolean")
    if theme.get("default", "light") not in THEMES:
        errors.append("display.theme.default must be light or dark")
    levels = set(text_size.get("levels", ["standard", "large", "xlarge"]))
    if text_size.get("default", "standard") not in levels or not levels.issubset(TEXT_SIZES):
        errors.append("display.text_size levels/default are invalid")
    allowed_modes = set(mode.get("allowed", ["standard"]))
    if mode.get("default", "standard") not in allowed_modes or "standard" not in allowed_modes:
        errors.append("display.mode must include standard and its default")
    if persistence.get("enabled", False) not in (None, True, False):
        errors.append("display.persistence.enabled must be boolean")
    if persistence.get("storage", "none") not in STORAGE_TYPES:
        errors.append("display.persistence.storage must be none or local_storage")
    if persistence.get("enabled", False) and persistence.get("storage", "none") != "local_storage":
        errors.append("display.persistence.enabled requires local_storage")
    if not str(persistence.get("key", DEFAULT_STORAGE_KEY)).strip():
        errors.append("display.persistence.key must not be empty")
    if javascript.get("external", False) is True:
        errors.append("javascript.external must remain false for Template Core")
    if javascript.get("required_for_content", False) is True:
        errors.append("javascript.required_for_content must remain false")
    try:
        from contrast_audit import validate_accessibility_policy

        errors.extend(validate_accessibility_policy(accessibility))
    except ImportError:  # pragma: no cover - direct use without the core path
        pass
    return errors
