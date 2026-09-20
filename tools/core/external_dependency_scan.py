#!/usr/bin/env python3
"""Scan published text files for external runtime dependencies."""

from __future__ import annotations

import argparse
import re
from pathlib import Path


URL = re.compile(r"(?:src|href|url)\s*=\s*[\"']?https?://|url\(\s*https?://", re.I)


def scan(root: Path) -> list[str]:
    findings: list[str] = []
    for path in root.rglob("*") if root.is_dir() else []:
        if not path.is_file() or path.suffix.lower() not in {".html", ".css", ".js", ".webmanifest"}:
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        if URL.search(text):
            findings.append(str(path.relative_to(root)).replace("\\", "/"))
    return sorted(findings)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root")
    args = parser.parse_args()
    findings = scan(Path(args.root).resolve())
    if findings:
        print("REVIEW_REQUIRED external dependencies:")
        print("\n".join(findings))
        return 1
    print("External dependency scan: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
