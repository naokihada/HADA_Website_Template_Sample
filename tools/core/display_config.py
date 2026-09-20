#!/usr/bin/env python3
"""Validate optional Core display configuration."""

from __future__ import annotations

from typing import Any


THEMES = {"light", "dark"}
TEXT_SIZES = {"standard", "large", "xlarge"}


def validate_display(data: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    display = data.get("display") or {}
    theme = display.get("theme") or {}
    text_size = display.get("text_size") or {}
    mode = display.get("mode") or {}
    javascript = data.get("javascript") or {}
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
    if javascript.get("external", False) is True:
        errors.append("javascript.external must remain false for Template Core")
    if javascript.get("required_for_content", False) is True:
        errors.append("javascript.required_for_content must remain false")
    return errors
