"""Read strict JSON and TOML documents used by the Website Template."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

try:
    import tomllib
except ModuleNotFoundError:  # Python 3.10 development/test compatibility only.
    import tomli as tomllib  # type: ignore[no-redef]


class DuplicateJSONKeyError(ValueError):
    """Raised when a JSON object repeats a key."""


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise DuplicateJSONKeyError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _reject_constant(value: str) -> None:
    raise ValueError(f"non-standard JSON constant: {value}")


def load_document(path: Path) -> Any:
    """Load one JSON or TOML document, rejecting duplicate JSON keys."""
    suffix = path.suffix.lower()
    text = path.read_text(encoding="utf-8-sig")
    if suffix == ".json":
        return json.loads(text, object_pairs_hook=_unique_object, parse_constant=_reject_constant)
    if suffix == ".toml":
        return tomllib.loads(text)
    raise ValueError(f"unsupported structured document format: {suffix or '(no suffix)'}")


def dump_json(value: Any, path: Path) -> None:
    """Write UTF-8 JSON using the repository's CRLF text-file policy."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\r\n")
