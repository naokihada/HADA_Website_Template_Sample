#!/usr/bin/env python3
"""Promote an isolated candidate build without overwriting project-owned files."""

from __future__ import annotations

import argparse
import fnmatch
import json
import sys
import uuid
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError:  # pragma: no cover
    yaml = None  # type: ignore[assignment]

import file_transaction as tx
from site_contract import publication_path, resolve_site

EXIT_SUCCESS = 0
EXIT_FAILED = 1
EXIT_REVIEW = 4
SAFE_OWNERS = {"template", "generated"}


def load_manifest(root: Path) -> dict[str, Any]:
    if yaml is None:
        raise RuntimeError("PyYAML is required")
    path = root / "config/template.manifest.yaml"
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return data if isinstance(data, dict) else {}


def _normalized(value: str) -> str:
    return value.replace("\\", "/").lstrip("./")


def ownership_patterns(root: Path) -> list[tuple[str, str, int]]:
    manifest = load_manifest(root)
    ownership = manifest.get("ownership") or {}
    patterns: list[tuple[str, str, int]] = []
    if not isinstance(ownership, dict):
        return patterns
    for owner in ("template", "generated", "user"):
        values = ownership.get(owner) or []
        if not isinstance(values, list):
            continue
        for raw in values:
            if isinstance(raw, str):
                pattern = _normalized(raw)
                patterns.append((owner, pattern, len(pattern.replace("*", ""))))
    return patterns


def generated_media_paths(root: Path) -> set[str]:
    """Resolve approved derivative destinations without claiming all project images."""
    if yaml is None:
        return set()
    manifest_path = root / "config/media.manifest.yaml"
    if not manifest_path.is_file():
        return set()
    data = yaml.safe_load(manifest_path.read_text(encoding="utf-8")) or {}
    publication = _normalized(str(resolve_site(root)["publication_root"]))
    result: set[str] = set()
    for item in (data.get("images", []) if isinstance(data, dict) else []):
        if not isinstance(item, dict) or item.get("status") != "approved":
            continue
        web = Path(str(item.get("web", ""))).name
        thumbnail = Path(str(item.get("thumbnail", ""))).name
        if web:
            result.add(f"{publication}/assets/images/{web}")
        if thumbnail:
            result.add(f"{publication}/assets/images/thumbnails/{thumbnail}")
    return result


def classify(root: Path, relative: str) -> str:
    value = _normalized(relative)
    if value in generated_media_paths(root):
        return "generated"
    matches = [(owner, specificity) for owner, pattern, specificity in ownership_patterns(root) if fnmatch.fnmatch(value, pattern)]
    if not matches:
        return "unknown"
    matches.sort(key=lambda item: item[1], reverse=True)
    return matches[0][0]


def safe_path(root: Path, path: Path, label: str) -> Path:
    resolved_root = root.resolve()
    resolved = path.resolve()
    if resolved == resolved_root or not resolved.is_relative_to(resolved_root):
        raise ValueError(f"{label} must stay inside the repository")
    return resolved


def candidate_files(candidate: Path) -> set[str]:
    return {
        path.relative_to(candidate).as_posix()
        for path in candidate.rglob("*")
        if path.is_file() and ".build" not in path.relative_to(candidate).parts
    }


def publication_files(publication: Path) -> set[str]:
    if not publication.is_dir():
        return set()
    return {path.relative_to(publication).as_posix() for path in publication.rglob("*") if path.is_file()}


def build_plan(root: Path, candidate: Path, publication: Path) -> dict[str, Any]:
    candidate_names = candidate_files(candidate)
    publication_names = publication_files(publication)
    actions: list[dict[str, Any]] = []
    for relative in sorted(candidate_names | publication_names):
        source = candidate / relative
        target = publication / relative
        owner = classify(root, f"{publication.relative_to(root).as_posix()}/{relative}")
        source_exists, target_exists = source.is_file(), target.is_file()
        if source_exists and target_exists and source.read_bytes() == target.read_bytes():
            actions.append({"path": relative, "owner": owner, "action": "UNCHANGED"})
            continue
        if owner in SAFE_OWNERS:
            action = "ADD" if source_exists and not target_exists else "UPDATE" if source_exists else "REMOVE"
            actions.append({"path": relative, "owner": owner, "action": action})
        elif owner == "user":
            actions.append({"path": relative, "owner": owner, "action": "PRESERVE"})
        else:
            actions.append({"path": relative, "owner": owner, "action": "REVIEW_REQUIRED"})
    review = [item for item in actions if item["action"] == "REVIEW_REQUIRED"]
    return {
        "status": "REVIEW_REQUIRED" if review else "PASS",
        "candidate": str(candidate),
        "publication": str(publication),
        "actions": actions,
        "safe_updates": [item for item in actions if item["action"] in {"ADD", "UPDATE", "REMOVE"}],
        "preserved": [item for item in actions if item["action"] in {"UNCHANGED", "PRESERVE"}],
        "review_required": review,
    }


def apply_plan(root: Path, plan: dict[str, Any], candidate: Path, publication: Path) -> list[str]:
    if plan["status"] != "PASS":
        raise ValueError("Cannot apply a plan with REVIEW_REQUIRED paths")
    entries: list[dict[str, Any]] = []
    for item in plan["safe_updates"]:
        relative = item["path"]
        source = candidate / relative
        data = source.read_bytes() if source.is_file() else None
        target_relative = f"{publication.relative_to(root).as_posix()}/{relative}"
        entries.append(tx.entry(root, target_relative, data))
    if not entries:
        return []
    backup = root / "AI/history" / f"promotion-{uuid.uuid4().hex}"
    return tx.apply(root, entries, backup)


def run(root: Path, candidate_arg: str | None = None, apply: bool = False) -> dict[str, Any]:
    site = resolve_site(root)
    candidate = safe_path(root, root / (candidate_arg or site["generated_root"]), "candidate root")
    publication = safe_path(root, publication_path(root), "publication root")
    if candidate == publication:
        raise ValueError("candidate root and publication root must be different")
    if not candidate.is_dir():
        raise ValueError(f"candidate root does not exist: {candidate}")
    plan = build_plan(root, candidate, publication)
    if apply:
        plan["applied"] = apply_plan(root, plan, candidate, publication)
    else:
        plan["applied"] = []
    return plan


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Review or promote an isolated HADA candidate build")
    parser.add_argument("--root", default=".")
    parser.add_argument("--candidate-root", help="Candidate directory; defaults to paths.generated_root")
    parser.add_argument("--apply", action="store_true", help="Apply only when no REVIEW_REQUIRED paths exist")
    parser.add_argument("--format", choices=["text", "json", "both"], default="both")
    args = parser.parse_args(argv)
    try:
        plan = run(Path(args.root).resolve(), args.candidate_root, args.apply)
    except (OSError, ValueError, RuntimeError) as exc:
        print(f"FAILED: {exc}", file=sys.stderr)
        return EXIT_FAILED
    if args.format in {"text", "both"}:
        print(f"Promotion status: {plan['status']}")
        print(f"Candidate: {plan['candidate']}")
        print(f"Publication: {plan['publication']}")
        print(f"Safe updates: {len(plan['safe_updates'])}")
        print(f"Preserved: {len(plan['preserved'])}")
        print(f"Review required: {len(plan['review_required'])}")
        if plan.get("applied"):
            print(f"Applied: {len(plan['applied'])}")
    if args.format in {"json", "both"}:
        print("---JSON---")
        print(json.dumps(plan, indent=2, ensure_ascii=False))
    return EXIT_REVIEW if plan["status"] != "PASS" else EXIT_SUCCESS


if __name__ == "__main__":
    raise SystemExit(main())
