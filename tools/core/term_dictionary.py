"""Site-wide term dictionary — single authoritative file (config/term_dictionary.yaml)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, List

try:
    import yaml
except ImportError:
    yaml = None  # type: ignore[assignment]

VALID_TERM_TYPES = {
    "person",
    "organization",
    "company",
    "place",
    "product",
    "service",
    "work",
    "technical",
    "other",
}


@dataclass(frozen=True)
class TermEntry:
    source: str
    target: str
    type: str
    enabled: bool = True
    note: str = ""


def load_term_dictionary(path: Path) -> List[TermEntry]:
    if yaml is None:
        raise RuntimeError("PyYAML is required to load the term dictionary")
    if not path.is_file():
        raise FileNotFoundError(f"Term dictionary not found: {path}")

    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("Term dictionary root must be a mapping")

    raw_entries = data.get("entries", [])
    if not isinstance(raw_entries, list):
        raise ValueError("Term dictionary entries must be a list")

    entries: List[TermEntry] = []
    for index, item in enumerate(raw_entries):
        if not isinstance(item, dict):
            raise ValueError(f"Term dictionary entry {index} must be a mapping")
        source = item.get("source")
        target = item.get("target")
        term_type = item.get("type", "other")
        if not source or not target:
            raise ValueError(f"Term dictionary entry {index} requires source and target")
        if term_type not in VALID_TERM_TYPES:
            raise ValueError(f"Term dictionary entry {index} has invalid type: {term_type}")
        entries.append(
            TermEntry(
                source=str(source),
                target=str(target),
                type=str(term_type),
                enabled=bool(item.get("enabled", True)),
                note=str(item.get("note", "")),
            )
        )
    return [entry for entry in entries if entry.enabled]


def apply_term_dictionary(text: str, entries: List[TermEntry]) -> tuple[str, dict[str, str]]:
    """Protect dictionary sources with placeholders before machine translation."""
    placeholders: dict[str, str] = {}
    protected = text
    ordered = sorted(entries, key=lambda entry: len(entry.source), reverse=True)
    for entry in ordered:
        if entry.source not in protected:
            continue
        key = f"__TERM_{len(placeholders)}__"
        placeholders[key] = entry.target
        protected = protected.replace(entry.source, key)
    return protected, placeholders


def restore_term_dictionary(text: str, placeholders: dict[str, str]) -> str:
    result = text
    for key, target in placeholders.items():
        result = result.replace(key, target)
    return result
