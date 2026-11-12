"""Narrowly update and normalize linked HADA Website Template attribution labels."""

from __future__ import annotations

import html
import re
import urllib.parse
from typing import Tuple

DEFAULT_RELEASE_REPOSITORY = "naokihada/HADA_Website_Template"
_ANCHOR_RE = re.compile(r"<a\b(?P<attrs>[^>]*)>(?P<body>.*?)</a\s*>", re.IGNORECASE | re.DOTALL)
_HREF_RE = re.compile(r"\bhref\s*=\s*(?:\"([^\"]*)\"|'([^']*)'|([^\s>]+))", re.IGNORECASE)
_LABEL_RE = re.compile(r"(Built\s+with\s+HADA\s+Website\s+Template\s*\(v)\d+\.\d+\.\d+(\))", re.IGNORECASE)


def _transform(text: str, release_repository: str, replacement: str) -> Tuple[str, bool]:
    expected_path = "/" + release_repository.strip("/")
    changed = False

    def transform_anchor(match: re.Match[str]) -> str:
        nonlocal changed
        href_match = _HREF_RE.search(match.group("attrs"))
        if not href_match:
            return match.group(0)
        href = next((value for value in href_match.groups() if value is not None), "")
        parsed = urllib.parse.urlsplit(html.unescape(href))
        if (parsed.scheme.lower() != "https" or parsed.netloc.lower() != "github.com"
                or parsed.path.rstrip("/") != expected_path or parsed.query or parsed.fragment):
            return match.group(0)
        body, count = _LABEL_RE.subn(
            lambda label: label.group(1) + replacement + label.group(2),
            match.group("body"), count=1,
        )
        if not count or body == match.group("body"):
            return match.group(0)
        changed = True
        body_start = match.start("body") - match.start()
        body_end = match.end("body") - match.start()
        return match.group(0)[:body_start] + body + match.group(0)[body_end:]

    return _ANCHOR_RE.sub(transform_anchor, text), changed


def update_linked_template_attribution(text: str, target_version: str, release_repository: str) -> Tuple[str, bool]:
    """Update the recognized version label only inside a link to the Template repository."""
    return _transform(text, release_repository, target_version)


def normalize_linked_template_attribution(text: str, release_repository: str = DEFAULT_RELEASE_REPOSITORY) -> str:
    """Normalize only the version digits for semantic before/after HTML comparison."""
    normalized, _ = _transform(text, release_repository, "0.0.0")
    return normalized
