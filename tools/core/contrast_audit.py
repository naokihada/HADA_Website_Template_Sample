#!/usr/bin/env python3
"""Deterministic contrast and foreground-priority policy audit."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError:  # pragma: no cover - dependency is validated by the framework
    yaml = None  # type: ignore[assignment]


COLOR_RE = re.compile(r"^#([0-9a-fA-F]{3}|[0-9a-fA-F]{6})$")
ORDER = ["color", "font_weight", "font_size", "font_family"]


def parse_color(value: Any) -> tuple[float, float, float, float]:
    """Parse a hex or rgb/rgba CSS color into normalized sRGB channels."""
    text = str(value or "").strip()
    match = COLOR_RE.fullmatch(text)
    if match:
        value = match.group(1)
        if len(value) == 3:
            value = "".join(char * 2 for char in value)
        return tuple(int(value[index : index + 2], 16) / 255 for index in (0, 2, 4)) + (1.0,)
    rgb_match = re.fullmatch(r"rgba?\(([^)]+)\)", text, re.IGNORECASE)
    if rgb_match:
        parts = [part.strip() for part in rgb_match.group(1).split(",")]
        if len(parts) not in {3, 4}:
            raise ValueError(f"invalid color: {value}")
        channels = tuple(float(part.rstrip("%")) / (100 if "%" in part else 255) for part in parts[:3])
        alpha = float(parts[3]) if len(parts) == 4 else 1.0
        if any(channel < 0 or channel > 1 for channel in channels) or not 0 <= alpha <= 1:
            raise ValueError(f"invalid color: {value}")
        return channels + (alpha,)
    raise ValueError(f"unsupported color: {value}")


def composite(foreground: tuple[float, float, float, float], background: tuple[float, float, float, float]) -> tuple[float, float, float]:
    alpha = foreground[3] + background[3] * (1 - foreground[3])
    if alpha == 0:
        return (0.0, 0.0, 0.0)
    return tuple(
        (foreground[index] * foreground[3] + background[index] * background[3] * (1 - foreground[3])) / alpha
        for index in range(3)
    )


def _linear(channel: float) -> float:
    return channel / 12.92 if channel <= 0.04045 else ((channel + 0.055) / 1.055) ** 2.4


def relative_luminance(color: tuple[float, float, float]) -> float:
    red, green, blue = (_linear(channel) for channel in color)
    return 0.2126 * red + 0.7152 * green + 0.0722 * blue


def contrast_ratio(foreground: Any, background: Any) -> float:
    fg = parse_color(foreground) if not isinstance(foreground, tuple) else foreground
    bg = parse_color(background) if not isinstance(background, tuple) else background
    fg_rgb = composite(fg, bg)
    bg_rgb = composite(bg, (0.0, 0.0, 0.0, 1.0))
    lighter = max(relative_luminance(fg_rgb), relative_luminance(bg_rgb))
    darker = min(relative_luminance(fg_rgb), relative_luminance(bg_rgb))
    return (lighter + 0.05) / (darker + 0.05)


def validate_accessibility_policy(policy: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    normal = policy.get("normal_text_min_contrast", 4.5)
    large = policy.get("large_text_min_contrast", 3.0)
    if not isinstance(normal, (int, float)) or float(normal) < 4.5:
        errors.append("accessibility.normal_text_min_contrast must be at least 4.5")
    if not isinstance(large, (int, float)) or float(large) < 3.0:
        errors.append("accessibility.large_text_min_contrast must be at least 3.0")
    if not isinstance(policy.get("preserve_background_treatment", True), bool):
        errors.append("accessibility.preserve_background_treatment must be boolean")
    minimum_font_size = str(policy.get("minimum_font_size", "1rem")).strip().lower()
    if not minimum_font_size.endswith("rem"):
        errors.append("accessibility.minimum_font_size must use rem")
    else:
        try:
            if float(minimum_font_size[:-3]) < 1:
                errors.append("accessibility.minimum_font_size must be at least 1rem")
        except ValueError:
            errors.append("accessibility.minimum_font_size must be a valid rem value")
    order = policy.get("foreground_adjustment_order", ORDER)
    if order != ORDER:
        errors.append("accessibility.foreground_adjustment_order must be color, font_weight, font_size, font_family")
    pairs = policy.get("contrast_pairs", [])
    if not isinstance(pairs, list):
        errors.append("accessibility.contrast_pairs must be a list")
    return errors


def audit_policy(policy: dict[str, Any]) -> dict[str, Any]:
    findings: list[dict[str, Any]] = []
    errors = validate_accessibility_policy(policy)
    for error in errors:
        findings.append({"status": "FAIL", "check": "policy", "message": error})
    pairs = policy.get("contrast_pairs", [])
    if isinstance(pairs, list):
        for index, pair in enumerate(pairs):
            if not isinstance(pair, dict):
                findings.append({"status": "FAIL", "check": f"pair[{index}]", "message": "contrast pair must be a mapping"})
                continue
            try:
                actual = contrast_ratio(pair.get("foreground"), pair.get("background"))
                minimum = float(pair.get("minimum", policy.get("normal_text_min_contrast", 4.5)))
            except (TypeError, ValueError) as exc:
                findings.append({"status": "FAIL", "check": f"pair[{index}]", "message": str(exc)})
                continue
            passed = actual + 1e-9 >= minimum
            findings.append(
                {
                    "status": "PASS" if passed else "FAIL",
                    "check": str(pair.get("name", f"pair[{index}]")),
                    "actual": round(actual, 2),
                    "minimum": minimum,
                }
            )
    return {
        "schema_version": "0.1",
        "status": "PASS" if all(item["status"] == "PASS" for item in findings) else "FAIL",
        "preserve_background_treatment": policy.get("preserve_background_treatment", True),
        "foreground_adjustment_order": policy.get("foreground_adjustment_order", ORDER),
        "findings": findings,
    }


def load_policy(root: Path) -> dict[str, Any]:
    candidates = (root / "config" / "display.yaml", root / "config" / "display.example.yaml")
    for path in candidates:
        if not path.is_file():
            continue
        if yaml is None:
            raise RuntimeError("PyYAML is required")
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        display = data.get("display") if isinstance(data, dict) else {}
        policy = display.get("accessibility") if isinstance(display, dict) else {}
        return policy if isinstance(policy, dict) else {}
    return {}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=".")
    parser.add_argument("--format", choices=("text", "json"), default="text")
    args = parser.parse_args(argv)
    result = audit_policy(load_policy(Path(args.root).resolve()))
    if args.format == "json":
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        print(f"Contrast audit: {result['status']}")
        print(f"Preserve background treatment: {result['preserve_background_treatment']}")
        print(f"Foreground order: {' -> '.join(result['foreground_adjustment_order'])}")
        for finding in result["findings"]:
            print(json.dumps(finding, ensure_ascii=False))
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
