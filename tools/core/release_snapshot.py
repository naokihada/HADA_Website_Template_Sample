#!/usr/bin/env python3
"""Create a reference-only template release snapshot.

Snapshots are evidence for review and parity checks. They are never build input.
"""

from __future__ import annotations

import argparse
import hashlib
import shutil
from pathlib import Path

import yaml


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def snapshot(root: Path, version: str, source: Path | None = None) -> Path:
    project = yaml.safe_load((root / "config" / "project.yaml").read_text(encoding="utf-8")) or {}
    paths = project.get("paths") or {}
    publication = source or (root / str(paths.get("publication_root", "site")))
    if not publication.is_dir():
        raise ValueError(f"publication root does not exist: {publication}")
    version = version.removeprefix("v")
    target = root / str(paths.get("template_references", "references/template-releases")) / f"v{version}"
    if target.exists():
        raise FileExistsError(f"snapshot already exists: {target}")
    site = target / "site"
    shutil.copytree(publication, site)
    manifest = root / "config" / "template.manifest.yaml"
    target.mkdir(parents=True, exist_ok=True)
    (target / "manifest.yaml").write_text(manifest.read_text(encoding="utf-8"), encoding="utf-8", newline="\r\n")
    (target / "README.md").write_text(
        f"# Template reference snapshot v{version}\r\n\r\n"
        "Reference-only snapshot of the configured publication root. It is not build input.\r\n",
        encoding="utf-8", newline="\r\n"
    )
    lines = []
    for path in sorted(p for p in site.rglob("*") if p.is_file()):
        lines.append(f"{digest(path)}  site/{path.relative_to(site).as_posix()}")
    (target / "checksums.sha256").write_text("\r\n".join(lines) + "\r\n", encoding="utf-8", newline="\r\n")
    return target


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=".")
    parser.add_argument("--version", required=True)
    parser.add_argument("--source", help="Optional publication tree to snapshot")
    args = parser.parse_args()
    print(snapshot(Path(args.root).resolve(), args.version, Path(args.source).resolve() if args.source else None))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
