#!/usr/bin/env python3
"""Deterministic file-tree parity comparison for candidate promotion."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def inventory(root: Path) -> dict[str, str]:
    if not root.is_dir():
        return {}
    return {str(p.relative_to(root)).replace("\\", "/"): digest(p) for p in root.rglob("*") if p.is_file()}


def compare(expected: Path, candidate: Path) -> dict[str, object]:
    left, right = inventory(expected), inventory(candidate)
    added = sorted(set(right) - set(left))
    removed = sorted(set(left) - set(right))
    changed = sorted(key for key in set(left) & set(right) if left[key] != right[key])
    return {"status": "PASS" if not added and not removed and not changed else "REVIEW_REQUIRED", "added": added, "removed": removed, "changed": changed}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("expected")
    parser.add_argument("candidate")
    parser.add_argument("--report", default="tree-parity.json")
    args = parser.parse_args()
    result = compare(Path(args.expected), Path(args.candidate))
    Path(args.report).write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8", newline="\r\n")
    print(json.dumps(result, indent=2))
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
