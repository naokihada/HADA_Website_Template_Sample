#!/usr/bin/env python3
"""Read-only URL and HTML signature audit for upgrade review."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from html.parser import HTMLParser
from pathlib import Path


class Signature(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.title = ""
        self.tags: list[str] = []
        self.links: list[str] = []
        self.assets: list[str] = []
        self._title = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.tags.append(tag)
        values = dict(attrs)
        if tag == "title":
            self._title = True
        for key in ("href", "src"):
            value = values.get(key)
            if value:
                (self.links if key == "href" else self.assets).append(value)

    def handle_endtag(self, tag: str) -> None:
        if tag == "title":
            self._title = False

    def handle_data(self, data: str) -> None:
        if self._title:
            self.title += data.strip()


def audit(root: Path) -> dict[str, object]:
    pages = {}
    for path in sorted(root.rglob("*.html")) if root.is_dir() else []:
        parser = Signature()
        raw = path.read_bytes()
        parser.feed(raw.decode("utf-8", errors="replace"))
        pages[str(path.relative_to(root)).replace("\\", "/")] = {
            "sha256": hashlib.sha256(raw).hexdigest(),
            "title": parser.title,
            "tags": parser.tags,
            "links": parser.links,
            "assets": parser.assets,
        }
    return {"schema_version": "0.1", "pages": pages, "page_count": len(pages)}


def compare(before: dict[str, object], after: dict[str, object]) -> dict[str, object]:
    before_pages = before.get("pages", {}) if isinstance(before.get("pages"), dict) else {}
    after_pages = after.get("pages", {}) if isinstance(after.get("pages"), dict) else {}
    added = sorted(set(after_pages) - set(before_pages))
    removed = sorted(set(before_pages) - set(after_pages))
    changed = sorted(path for path in set(before_pages) & set(after_pages) if before_pages[path] != after_pages[path])
    return {"schema_version": "0.1", "status": "PASS" if not added and not removed and not changed else "REVIEW_REQUIRED", "added": added, "removed": removed, "changed": changed}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root")
    parser.add_argument("--output")
    args = parser.parse_args()
    result = audit(Path(args.root).resolve())
    text = json.dumps(result, indent=2, ensure_ascii=False) + "\n"
    if args.output:
        Path(args.output).write_text(text, encoding="utf-8", newline="\r\n")
    sys.stdout.buffer.write(text.encode("utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
