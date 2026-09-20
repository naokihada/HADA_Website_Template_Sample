#!/usr/bin/env python3
"""Template upgrade from GitHub stable Release — SPEC.md §1.7, docs/UPGRADE_ARCHITECTURE.md."""

from __future__ import annotations

import argparse
import fnmatch
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import uuid
import urllib.error
import urllib.request
import zipfile
import template_base
import file_transaction as tx
from site_audit import audit as audit_site, compare as compare_site  # noqa: E402
from site_contract import publication_path  # noqa: E402
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from io import BytesIO
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Optional, Set, Tuple

try:
    import yaml
except ImportError:
    yaml = None  # type: ignore[assignment]

ENGINE_NAME = "upgrade-from-release"
ENGINE_VERSION = "0.1.2"
SCHEMA_VERSION = "0.1"
DEFAULT_REPO = "naokihada/HADA_Website_Template"
GITHUB_API = "https://api.github.com"

EXIT_SUCCESS = 0
EXIT_REVIEW = 1
EXIT_BLOCKED = 2
EXIT_FAILED = 3

SKIP_DIR_NAMES = {".git", "__pycache__", ".venv", "venv", "node_modules"}
CLONE_META = ".hada-upgrade-clone.yaml"

# v0.1.1 Public Release fingerprint (SHA-256 of file contents at tag v0.1.1)
FINGERPRINT_CATALOG: Dict[str, Dict[str, str]] = {
    "0.1.1": {
        # SHA-256 at Public tag v0.1.1 (naokihada/HADA_Website_Template)
        "tools/core/validate_framework.py": "004fe86b18d745476f46322f92b42edd8ee690c4e0954aad2b834f3a460e006c",
        "tools/core/build_site.py": "2a9d606ac053993af69fef0b52832794c8d24ce8280f8b41878fc2765858d042",
        "tools/core/term_dictionary.py": "12ed23b6792bc6a72a6addacfaa9aa75794eb5ce5ab8247d0f4d6931ccbcb0e9",
        "tools/core/translation_provider.py": "d947e8c08c676948ec07a4ed0a117dcf33c7dee6629832120ec7743ef6e60ffe",
    }
}
FINGERPRINT_MIN_MATCHES = 3


class Action(str, Enum):
    SKIP = "SKIP"
    AUTO = "AUTO"
    PRESERVE = "PRESERVE"
    REVIEW = "REVIEW_REQUIRED"
    ADD = "ADD"
    REMOVE = "REMOVE"


@dataclass
class Finding:
    rule_id: str
    severity: str
    message: str
    file: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {"rule_id": self.rule_id, "severity": self.severity, "message": self.message, "file": self.file}


@dataclass
class PlanItem:
    rel_path: str
    action: Action
    reason: str


@dataclass
class UpgradeResult:
    status: str
    exit_code: int
    root: str
    current_version: Optional[str]
    current_detection: str
    target_version: str
    target_tag: str
    temp_clone: Optional[str]
    plan: List[PlanItem] = field(default_factory=list)
    findings: List[Finding] = field(default_factory=list)
    applied: List[str] = field(default_factory=list)
    duration_ms: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "schema_version": SCHEMA_VERSION,
            "engine": ENGINE_NAME,
            "engine_version": ENGINE_VERSION,
            "status": self.status,
            "exit_code": self.exit_code,
            "root": self.root,
            "current_version": self.current_version,
            "current_detection": self.current_detection,
            "target_version": self.target_version,
            "target_tag": self.target_tag,
            "temp_clone": self.temp_clone,
            "plan": [{"path": i.rel_path, "action": i.action.value, "reason": i.reason} for i in self.plan],
            "findings": [f.to_dict() for f in self.findings],
            "applied": self.applied,
            "duration_ms": self.duration_ms,
        }


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).strftime("%Y-%m-%dT%H:%M:%SZ")


def normalize_version(version: str) -> str:
    version = version.strip()
    if version.lower().startswith("v"):
        version = version[1:]
    return version


def normalize_tag(version: str) -> str:
    version = normalize_version(version)
    return f"v{version}"


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def read_file_text(path: Path) -> Optional[str]:
    if not path.is_file():
        return None
    return path.read_text(encoding="utf-8")


def read_file_bytes(path: Path) -> Optional[bytes]:
    if not path.is_file():
        return None
    return path.read_bytes()


def safe_resolve(root: Path, rel: str) -> Optional[Path]:
    try:
        return tx.safe(root, rel)
    except ValueError:
        return None


def iter_repo_files(root: Path) -> Iterable[str]:
    root = root.resolve()
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        rel_parts = path.relative_to(root).parts
        if any(part in SKIP_DIR_NAMES for part in rel_parts):
            continue
        if path.name == CLONE_META:
            continue
        yield path.relative_to(root).as_posix()


def match_glob(rel_path: str, pattern: str) -> bool:
    rel_path = rel_path.replace("\\", "/").lstrip("./")
    pattern = pattern.replace("\\", "/")
    if pattern.endswith("/**"):
        prefix = pattern[:-3]
        return rel_path == prefix or rel_path.startswith(prefix + "/")
    if pattern.endswith("/*"):
        prefix = pattern[:-2]
        if not rel_path.startswith(prefix + "/"):
            return False
        rest = rel_path[len(prefix) + 1 :]
        return "/" not in rest
    return fnmatch.fnmatch(rel_path, pattern)


def matches_any(rel_path: str, patterns: List[str]) -> bool:
    return any(match_glob(rel_path, p) for p in patterns)


def load_yaml(path: Path) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    if yaml is None:
        return None, "PyYAML not installed"
    if not path.is_file():
        return None, f"Missing file: {path}"
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        return None, str(exc)
    if not isinstance(data, dict):
        return None, "YAML root must be a mapping"
    return data, None


def ownership_lists(manifest: Dict[str, Any]) -> Tuple[List[str], List[str], List[str]]:
    own = manifest.get("ownership") or {}
    template = own.get("template") or own.get("template_owned") or []
    user = own.get("user") or own.get("user_owned") or []
    generated = own.get("generated") or []
    return list(template), list(user), list(generated)


def classify_path(rel_path: str, template: List[str], user: List[str], generated: List[str]) -> str:
    # Content Master paths are always user-owned even when also listed under generated.
    if rel_path.startswith("content/") and matches_any(rel_path, user):
        return "user"
    if matches_any(rel_path, generated):
        return "generated"
    if matches_any(rel_path, user):
        return "user"
    if matches_any(rel_path, template):
        return "template"
    return "other"


def detect_version(site_root: Path, assume_version: Optional[str] = None) -> Tuple[str, Optional[str]]:
    try:
        base = template_base.check(site_root)
        if base is not None:
            if assume_version and normalize_version(assume_version) != base['Version']:
                return 'unknown', None
            return 'detected', base['Version']
    except (ValueError, KeyError, TypeError, OSError):
        return 'unknown', None
    if assume_version:
        return "assumed", normalize_version(assume_version)

    manifest_path = site_root / "config" / "template.manifest.yaml"
    data, err = load_yaml(manifest_path)
    if data and not err:
        template = data.get("template") or {}
        version = template.get("version")
        if isinstance(version, str) and version.strip():
            return "detected", normalize_version(version)

    catalog = FINGERPRINT_CATALOG.get("0.1.1", {})
    matches = 0
    for rel, expected in catalog.items():
        fp = site_root / rel.replace("/", os.sep)
        if fp.is_file() and sha256_file(fp).lower() == expected.lower():
            matches += 1
    if matches >= FINGERPRINT_MIN_MATCHES:
        return "legacy-identified", "0.1.1"

    return "unknown", None


def migration_allowed(manifest: Dict[str, Any], from_ver: str, to_ver: str) -> bool:
    migrations = manifest.get("migrations") or {}
    entry = migrations.get(from_ver) or migrations.get(normalize_version(from_ver))
    if not entry:
        return False
    targets = entry.get("to") or []
    return normalize_version(to_ver) in [normalize_version(str(t)) for t in targets]


def three_way_action(p: Optional[bytes], c: Optional[bytes], n: Optional[bytes]) -> Action:
    exists_p, exists_c, exists_n = p is not None, c is not None, n is not None
    if exists_n and not exists_p:
        if exists_c:
            return Action.SKIP if c == n else Action.REVIEW
        return Action.ADD
    if exists_p and not exists_n:
        if exists_c and c == p:
            return Action.REMOVE
        if exists_c and c != p:
            return Action.REVIEW
        return Action.SKIP
    if not exists_p and not exists_c and exists_n:
        return Action.ADD
    if exists_p and exists_c and exists_n:
        if p == c and p != n:
            return Action.AUTO
        if p != c and p == n:
            return Action.PRESERVE
        if p == c == n:
            return Action.SKIP
        if p != c and p != n and c == n:
            return Action.PRESERVE
        if p != c and p != n and c != n:
            return Action.REVIEW
    if exists_c and exists_n and not exists_p:
        return Action.ADD
    return Action.REVIEW


def yaml_merge_project(
    p_text: Optional[str], c_text: Optional[str], n_text: Optional[str], preserve_keys: List[str]
) -> Tuple[Optional[str], Optional[str]]:
    if yaml is None:
        return None, "PyYAML not installed"
    try:
        p_data = yaml.safe_load(p_text or "") or {}
        c_data = yaml.safe_load(c_text or "") or {}
        n_data = yaml.safe_load(n_text or "") or {}
    except yaml.YAMLError as exc:
        return None, str(exc)
    if not isinstance(n_data, dict) or not isinstance(c_data, dict):
        return None, "project.yaml must be mapping"

    def get_nested(d: Dict[str, Any], dotted: str) -> Any:
        parts = dotted.split(".")
        cur: Any = d
        for part in parts:
            if not isinstance(cur, dict) or part not in cur:
                return None
            cur = cur[part]
        return cur

    def set_nested(d: Dict[str, Any], dotted: str, value: Any) -> None:
        parts = dotted.split(".")
        cur = d
        for part in parts[:-1]:
            if part not in cur or not isinstance(cur[part], dict):
                cur[part] = {}
            cur = cur[part]
        cur[parts[-1]] = value

    merged = yaml.safe_load(yaml.dump(n_data)) or {}
    for key in preserve_keys:
        val = get_nested(c_data, key)
        if val is not None:
            existing = get_nested(n_data, key)
            if existing is not None and type(existing) != type(val):
                return None, f"type conflict on {key}"
            set_nested(merged, key, val)

    for key, val in c_data.items():
        if key not in merged:
            merged[key] = val
        elif isinstance(val, dict) and isinstance(merged.get(key), dict):
            for sub_key, sub_val in val.items():
                if sub_key not in merged[key]:
                    merged[key][sub_key] = sub_val

    return yaml.dump(merged, sort_keys=False, allow_unicode=True), None


def build_plan(
    site_root: Path,
    prev_root: Optional[Path],
    new_root: Path,
    manifest: Dict[str, Any],
) -> Tuple[List[PlanItem], List[Finding]]:
    template_globs, user_globs, generated_globs = ownership_lists(manifest)
    merge_policies = manifest.get("merge_policies") or manifest.get("merge") or {}

    paths: Set[str] = set()
    for root in (prev_root, site_root, new_root):
        if root is None:
            continue
        for rel in iter_repo_files(root):
            paths.add(rel)

    plan: List[PlanItem] = []
    findings: List[Finding] = []

    for rel in sorted(paths):
        if rel == 'TEMPLATE_BASE.md':
            continue  # Adoption metadata is finalized only after verification.
        kind = classify_path(rel, template_globs, user_globs, generated_globs)
        if kind == "user":
            continue
        if kind == "other":
            continue

        p_path = safe_resolve(prev_root, rel) if prev_root else None
        c_path = safe_resolve(site_root, rel)
        n_path = safe_resolve(new_root, rel)

        p_bytes = read_file_bytes(p_path) if p_path else None
        c_bytes = read_file_bytes(c_path) if c_path else None
        n_bytes = read_file_bytes(n_path) if n_path else None

        policy = None
        for pat, cfg in merge_policies.items():
            if match_glob(rel, pat):
                policy = cfg
                break

        if policy and (policy.get("strategy") == "yaml_merge_preserve_user_keys"):
            if p_bytes == c_bytes and p_bytes != n_bytes and c_bytes is not None:
                merged, err = yaml_merge_project(
                    p_bytes.decode("utf-8") if p_bytes else None,
                    c_bytes.decode("utf-8") if c_bytes else None,
                    n_bytes.decode("utf-8") if n_bytes else None,
                    list(policy.get("preserve_keys") or []),
                )
                if err:
                    plan.append(PlanItem(rel, Action.REVIEW, f"yaml merge: {err}"))
                else:
                    plan.append(PlanItem(rel, Action.AUTO, "safe yaml merge"))
            elif p_bytes != c_bytes and p_bytes == n_bytes:
                plan.append(PlanItem(rel, Action.PRESERVE, "user yaml changes"))
            elif p_bytes == c_bytes == n_bytes:
                plan.append(PlanItem(rel, Action.SKIP, "unchanged"))
            else:
                plan.append(PlanItem(rel, Action.REVIEW, "yaml three-way conflict"))
            continue

        if policy and policy.get("strategy") == "preserve_if_modified":
            action = three_way_action(p_bytes, c_bytes, n_bytes)
            if action == Action.AUTO and p_bytes != c_bytes:
                action = Action.PRESERVE
            plan.append(PlanItem(rel, action, "preserve_if_modified policy"))
            continue

        action = three_way_action(p_bytes, c_bytes, n_bytes)
        if kind == "generated" and p_bytes is not None and c_bytes is not None and p_bytes != c_bytes:
            if action == Action.AUTO:
                action = Action.REVIEW
                findings.append(
                    Finding("UPG-030", "WARNING", "Generated file manually modified", file=rel)
                )
        plan.append(PlanItem(rel, action, f"{kind} three-way"))

    return plan, findings


def apply_plan(site_root: Path, new_root: Path, plan: List[PlanItem], dry_run: bool) -> List[str]:
    applied: List[str] = []
    for item in plan:
        if item.action not in (Action.AUTO, Action.ADD, Action.REMOVE):
            continue
        c_path = safe_resolve(site_root, item.rel_path)
        n_path = safe_resolve(new_root, item.rel_path)
        if item.action == Action.REMOVE:
            if c_path and c_path.is_file():
                if not dry_run:
                    c_path.unlink()
                applied.append(item.rel_path)
            continue
        if n_path is None or not n_path.is_file():
            continue
        content = n_path.read_bytes()
        if item.rel_path == "config/project.yaml" and "yaml merge" in item.reason:
            merged, err = yaml_merge_project(
                None,
                read_file_text(c_path) if c_path else "",
                n_path.read_text(encoding="utf-8"),
                ["project", "paths"],
            )
            if err:
                continue
            content = (merged or "").encode("utf-8")
        if not dry_run:
            assert c_path is not None or item.action == Action.ADD
            dest = safe_resolve(site_root, item.rel_path)
            if dest is None:
                continue
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(content)
        applied.append(item.rel_path)
    return applied


def http_get_json(url: str, timeout: int = 30) -> Dict[str, Any]:
    req = urllib.request.Request(url, headers={"Accept": "application/vnd.github+json", "User-Agent": "hada-upgrade-engine"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def network_preflight(repo: str) -> Tuple[bool, Optional[str]]:
    try:
        urllib.request.urlopen("https://api.github.com/rate_limit", timeout=15)
        http_get_json(f"{GITHUB_API}/repos/{repo}/releases/latest", timeout=15)
        return True, None
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, json.JSONDecodeError) as exc:
        return False, str(exc)


def resolve_release(repo: str, version: Optional[str]) -> Tuple[Optional[str], Optional[str], Optional[Dict[str, Any]]]:
    try:
        if version:
            tag = normalize_tag(version)
            data = http_get_json(f"{GITHUB_API}/repos/{repo}/releases/tags/{tag}")
        else:
            data = http_get_json(f"{GITHUB_API}/repos/{repo}/releases/latest")
            if data.get("prerelease") or data.get("draft"):
                releases = http_get_json(f"{GITHUB_API}/repos/{repo}/releases")
                stable = [r for r in releases if not r.get("prerelease") and not r.get("draft")]
                if not stable:
                    return None, None, None
                data = stable[0]
        tag = data.get("tag_name")
        if not tag or data.get("prerelease") or data.get("draft"):
            return None, None, data
        ver = normalize_version(tag)
        return ver, tag, data
    except (urllib.error.URLError, urllib.error.HTTPError, json.JSONDecodeError):
        return None, None, None


def fetch_release_archive(release: Dict[str, Any], dest: Path) -> None:
    url = release.get("zipball_url")
    if not url:
        raise RuntimeError("Release has no zipball_url")
    req = urllib.request.Request(url, headers={"User-Agent": "hada-upgrade-engine"})
    with urllib.request.urlopen(req, timeout=120) as resp:
        data = resp.read()
    dest.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(BytesIO(data)) as zf:
        members = [m for m in zf.namelist() if not m.endswith("/")]
        if not members:
            raise RuntimeError("Empty release archive")
        top_prefix = members[0].split("/")[0] + "/"
        for member in members:
            rel = member[len(top_prefix) :] if member.startswith(top_prefix) else member
            if not rel:
                continue
            target = safe_resolve(dest, rel)
            if target is None:
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(zf.read(member))


def git_clone_release(repo: str, tag: str, dest: Path) -> bool:
    url = f"https://github.com/{repo}.git"
    try:
        subprocess.run(
            ["git", "clone", "--depth", "1", "--branch", tag, url, str(dest)],
            check=True,
            capture_output=True,
            text=True,
        )
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False


def write_clone_metadata(dest: Path, repo: str, tag: str) -> None:
    meta = {
        "acquired_at": utc_now_iso(),
        "tag": tag,
        "repository": repo,
        "purpose": "template-upgrade-source",
        "retain": True,
    }
    if yaml is not None:
        dest.joinpath(CLONE_META).write_text(yaml.dump(meta, sort_keys=False), encoding="utf-8")


def fetch_template_to_temp(
    repo: str,
    tag: str,
    release: Optional[Dict[str, Any]],
    local_root: Optional[Path],
) -> Path:
    if local_root is not None:
        return local_root.resolve()
    temp_base = Path(tempfile.gettempdir()) / f"hada-template-upgrade-{uuid.uuid4().hex}"
    temp_base.mkdir(parents=True, exist_ok=True)
    if git_clone_release(repo, tag, temp_base):
        write_clone_metadata(temp_base, repo, tag)
        return temp_base
    if release:
        fetch_release_archive(release, temp_base)
        write_clone_metadata(temp_base, repo, tag)
        return temp_base
    raise RuntimeError("Failed to fetch template release")


def validate_manifest_version(manifest: Dict[str, Any], target_version: str) -> Optional[str]:
    template = manifest.get("template") or {}
    mv = template.get("version")
    if mv and normalize_version(str(mv)) != normalize_version(target_version):
        return f"manifest template.version {mv} != target {target_version}"
    return None


def run_upgrade(
    root: Path,
    version: Optional[str] = None,
    assume_version: Optional[str] = None,
    dry_run: bool = False,
    skip_network: bool = False,
    local_new_template: Optional[Path] = None,
    local_previous_template: Optional[Path] = None,
    network_check: Optional[Callable[[str], Tuple[bool, Optional[str]]]] = None,
    release_resolver: Optional[Callable[[str, Optional[str]], Tuple[Optional[str], Optional[str], Optional[Dict[str, Any]]]]] = None,
) -> UpgradeResult:
    start = time.time()
    findings: List[Finding] = []
    repo = DEFAULT_REPO

    if not (root / "AGENTS.md").is_file():
        return UpgradeResult(
            "BLOCKED", EXIT_BLOCKED, str(root.resolve()), None, "unknown", "", "", None,
            findings=[Finding("UPG-001", "ERROR", "Not a framework project root (missing AGENTS.md)")],
            duration_ms=int((time.time() - start) * 1000),
        )

    detection, current_ver = detect_version(root, assume_version)
    if detection == "unknown":
        return UpgradeResult(
            "BLOCKED", EXIT_BLOCKED, str(root.resolve()), None, "unknown", "", "", None,
            findings=[Finding("UPG-004", "ERROR", "Current template version unknown")],
            duration_ms=int((time.time() - start) * 1000),
        )

    check_fn = network_check or network_preflight
    resolve_fn = release_resolver or resolve_release

    if local_new_template is None and not skip_network:
        ok, err = check_fn(repo)
        if not ok:
            return UpgradeResult(
                "BLOCKED", EXIT_BLOCKED, str(root.resolve()), current_ver, detection, "", "", None,
                findings=[Finding("UPG-001", "ERROR", f"Network preflight failed: {err}")],
                duration_ms=int((time.time() - start) * 1000),
            )

    target_ver: Optional[str] = None
    target_tag: Optional[str] = None
    release_data: Optional[Dict[str, Any]] = None

    if local_new_template is not None:
        if version:
            target_ver = normalize_version(version)
            target_tag = normalize_tag(version)
        else:
            local_manifest, _ = load_yaml(local_new_template / "config" / "template.manifest.yaml")
            if local_manifest:
                tv = (local_manifest.get("template") or {}).get("version")
                if isinstance(tv, str) and tv.strip():
                    target_ver = normalize_version(tv)
                    target_tag = normalize_tag(tv)
        if target_ver:
            release_data = {"prerelease": False, "draft": False}
    elif skip_network:
        return UpgradeResult(
            "BLOCKED", EXIT_BLOCKED, str(root.resolve()), current_ver, detection, "", "", None,
            findings=[Finding("UPG-001", "ERROR", "Network skipped without --local-new-template")],
            duration_ms=int((time.time() - start) * 1000),
        )
    else:
        target_ver, target_tag, release_data = resolve_fn(repo, version)

    if not target_ver or not target_tag:
        return UpgradeResult(
            "BLOCKED", EXIT_BLOCKED, str(root.resolve()), current_ver, detection, "", "", None,
            findings=[Finding("UPG-002", "ERROR", "Release not found or not stable")],
            duration_ms=int((time.time() - start) * 1000),
        )

    if release_data and (release_data.get("prerelease") or release_data.get("draft")):
        return UpgradeResult(
            "BLOCKED", EXIT_BLOCKED, str(root.resolve()), current_ver, detection, target_ver, target_tag, None,
            findings=[Finding("UPG-003", "ERROR", "Target release is prerelease or draft")],
            duration_ms=int((time.time() - start) * 1000),
        )

    try:
        new_root = fetch_template_to_temp(repo, target_tag, release_data, local_new_template)
    except Exception as exc:
        return UpgradeResult(
            "FAILED", EXIT_FAILED, str(root.resolve()), current_ver, detection, target_ver, target_tag, None,
            findings=[Finding("UPG-050", "ERROR", f"Template fetch failed: {exc}")],
            duration_ms=int((time.time() - start) * 1000),
        )

    temp_path = str(new_root.resolve()) if local_new_template is None else None

    manifest_path = new_root / "config" / "template.manifest.yaml"
    manifest, err = load_yaml(manifest_path)
    if not manifest:
        return UpgradeResult(
            "BLOCKED", EXIT_BLOCKED, str(root.resolve()), current_ver, detection, target_ver, target_tag, temp_path,
            findings=[Finding("UPG-005", "ERROR", f"New template manifest missing or invalid: {err}")],
            duration_ms=int((time.time() - start) * 1000),
        )

    mismatch = validate_manifest_version(manifest, target_ver)
    if mismatch:
        findings.append(Finding("UPG-011", "ERROR", mismatch))

    if current_ver and not migration_allowed(manifest, current_ver, target_ver):
        findings.append(
            Finding("UPG-005", "ERROR", f"No migration path {current_ver} -> {target_ver}")
        )

    prev_root: Optional[Path] = local_previous_template
    if prev_root is None and current_ver and local_new_template is None:
        prev_tag = normalize_tag(current_ver)
        try:
            prev_root = fetch_template_to_temp(repo, prev_tag, None, None)
        except Exception:
            prev_root = None

    if findings and any(f.severity == "ERROR" for f in findings):
        return UpgradeResult(
            "BLOCKED", EXIT_BLOCKED, str(root.resolve()), current_ver, detection, target_ver, target_tag, temp_path,
            findings=findings, duration_ms=int((time.time() - start) * 1000),
        )

    plan, plan_findings = build_plan(root, prev_root, new_root, manifest)
    findings.extend(plan_findings)

    has_review = any(item.action == Action.REVIEW for item in plan)
    applied: List[str] = []
    if not has_review:
        if dry_run:
            applied = []
        else:
            if prev_root is None:
                return UpgradeResult('BLOCKED', EXIT_BLOCKED, str(root.resolve()), current_ver,
                    detection, target_ver, target_tag, temp_path,
                    findings=[Finding('UPG-053', 'ERROR', 'Previous template is required for safe apply')])
            # Missing verification is a failure, never implicit adoption success.
            required = root / 'tools/core/validate_framework.py'
            if not required.is_file():
                return UpgradeResult('BLOCKED', EXIT_BLOCKED, str(root.resolve()), current_ver,
                    detection, target_ver, target_tag, temp_path, plan=plan,
                    findings=[Finding('UPG-051', 'ERROR', 'Required framework validator missing')])
            if any((root / name).exists() for name in ('.cursor', 'Cursor')):
                return UpgradeResult('REVIEW_REQUIRED', EXIT_REVIEW, str(root.resolve()), current_ver,
                    detection, target_ver, target_tag, temp_path, plan=plan,
                    findings=[Finding('UPG-052', 'WARNING', 'Legacy workspace requires classified, backed-up migration before apply')])
            # Verify candidate in isolation; never rebuild styled output in the consumer.
            candidate = Path(tempfile.mkdtemp(prefix='hada-upgrade-verify-'))
            snapshots = {i.rel_path: tx.digest(tx.safe(root, i.rel_path)) for i in plan
                if i.action in (Action.AUTO, Action.ADD, Action.REMOVE)}
            snapshots['TEMPLATE_BASE.md'] = tx.digest(tx.safe(root, 'TEMPLATE_BASE.md'))
            shutil.copytree(root, candidate, dirs_exist_ok=True,
                ignore=shutil.ignore_patterns('.git', 'AI', '__pycache__', '.venv', 'node_modules'))
            (candidate / 'AI').mkdir(exist_ok=True)
            apply_plan(candidate, new_root, plan, dry_run=False)
            (candidate / 'TEMPLATE_BASE.md').write_text(template_base.render(template_base.from_manifest(manifest)), encoding='utf-8')
            commands = [[sys.executable, str(candidate / 'tools/core/validate_framework.py'), '--root', str(candidate)]]
            commands += [[sys.executable, str(p)] for p in sorted((candidate / 'tests').glob('test_*.py'))]
            commands += [[sys.executable, str(candidate / 'tools/core/build_site.py'), '--root', str(candidate)]]
            for command in commands:
                checked = subprocess.run(command, cwd=candidate, capture_output=True)
                if checked.returncode:
                    return UpgradeResult('FAILED', EXIT_FAILED, str(root.resolve()), current_ver,
                        detection, target_ver, target_tag, str(candidate), plan=plan,
                        findings=[Finding('UPG-051', 'ERROR', 'Candidate verification failed: ' + Path(command[1]).name)])
            before_publication = publication_path(root)
            after_publication = publication_path(candidate)
            semantic_before = audit_site(before_publication)
            semantic_after = audit_site(after_publication)
            semantic_diff = compare_site(semantic_before, semantic_after)
            semantic_report = candidate / 'build' / 'upgrade-semantic-diff.json'
            semantic_report.parent.mkdir(parents=True, exist_ok=True)
            semantic_report.write_text(json.dumps({
                'before': semantic_before,
                'after': semantic_after,
                'diff': semantic_diff,
            }, indent=2, ensure_ascii=False) + '\n', encoding='utf-8', newline='\r\n')
            if semantic_diff['status'] != 'PASS':
                findings.append(Finding('UPG-060', 'WARNING', 'Candidate semantic site diff requires review', file='build/upgrade-semantic-diff.json'))
            # Candidate build output is verification only, never copied over styled output.
            operations = []
            for item in plan:
                if item.action not in (Action.AUTO, Action.ADD, Action.REMOVE): continue
                data = None if item.action == Action.REMOVE else tx.safe(new_root, item.rel_path).read_bytes()
                if item.rel_path == 'config/project.yaml' and 'yaml merge' in item.reason:
                    merged, error = yaml_merge_project(None, read_file_text(root / item.rel_path), data.decode(), ['project', 'paths'])
                    if error: raise ValueError(error)
                    data = merged.encode()
                operation = tx.entry(root, item.rel_path, data)
                operation['before'] = snapshots[item.rel_path]
                operations.append(operation)
            base_operation = tx.entry(root, 'TEMPLATE_BASE.md', template_base.render(template_base.from_manifest(manifest)).encode())
            base_operation['before'] = snapshots['TEMPLATE_BASE.md']
            operations.append(base_operation)
            operations.sort(key=lambda e: e['path'] in ('config/template.manifest.yaml', 'TEMPLATE_BASE.md'))
            try:
                applied = tx.apply(root, operations, root / 'AI/history' / ('upgrade-' + uuid.uuid4().hex))
            except (ValueError, OSError) as exc:
                return UpgradeResult('REVIEW_REQUIRED', EXIT_REVIEW, str(root.resolve()), current_ver,
                    detection, target_ver, target_tag, str(candidate), plan=plan,
                    findings=[Finding('UPG-054', 'ERROR', str(exc))])
    else:
        findings.append(Finding("UPG-020", "WARNING", "Migration plan contains REVIEW_REQUIRED items"))

    if has_review:
        status, code = "REVIEW_REQUIRED", EXIT_REVIEW
    else:
        status, code = "SUCCESS", EXIT_SUCCESS

    return UpgradeResult(
        status, code, str(root.resolve()), current_ver, detection, target_ver, target_tag, temp_path,
        plan=plan, findings=findings, applied=applied,
        duration_ms=int((time.time() - start) * 1000),
    )


def format_text(result: UpgradeResult) -> str:
    lines = [
        f"Upgrade: {ENGINE_NAME} v{ENGINE_VERSION}",
        f"Root: {result.root}",
        f"Status: {result.status}",
        f"Current: {result.current_version or 'unknown'} ({result.current_detection})",
        f"Target: {result.target_version} ({result.target_tag})",
    ]
    if result.temp_clone:
        lines.append(f"Temp clone: {result.temp_clone} (retained)")
    if result.findings:
        lines.append("")
        for f in result.findings:
            lines.append(f"[{f.severity}] {f.rule_id}  {f.message}" + (f"  ({f.file})" if f.file else ""))
    review = [p for p in result.plan if p.action == Action.REVIEW]
    if review:
        lines.append("")
        lines.append(f"Review required: {len(review)} path(s)")
    if result.applied:
        lines.append("")
        lines.append(f"Applied: {len(result.applied)} path(s)")
    return "\n".join(lines)


def main(argv: Optional[List[str]] = None) -> int:
    if yaml is None:
        print("ERROR: PyYAML required (pip install -r tools/core/requirements.txt)", file=sys.stderr)
        return EXIT_FAILED

    parser = argparse.ArgumentParser(description="Upgrade site from HADA Website Template GitHub Release")
    parser.add_argument("--root", default=".", help="Site project root")
    parser.add_argument("--version", help="Target version e.g. v0.1.2 (default: latest stable Release)")
    parser.add_argument("--assume-version", help="Explicit current template version when detection is unknown")
    parser.add_argument("--dry-run", action="store_true", help="Plan only; do not write files")
    parser.add_argument("--skip-network", action="store_true", help="Dev/test: skip network preflight")
    parser.add_argument("--local-new-template", help="Dev/test: local path as new template (skip fetch)")
    parser.add_argument("--local-previous-template", help="Dev/test: local path as previous template")
    parser.add_argument("--format", choices=["text", "json", "both"], default="both")
    args = parser.parse_args(argv)

    root = Path(args.root).resolve()
    local_new = Path(args.local_new_template).resolve() if args.local_new_template else None
    local_prev = Path(args.local_previous_template).resolve() if args.local_previous_template else None

    result = run_upgrade(
        root,
        version=args.version,
        assume_version=args.assume_version,
        dry_run=args.dry_run,
        skip_network=args.skip_network,
        local_new_template=local_new,
        local_previous_template=local_prev,
    )

    if args.format in ("text", "both"):
        print(format_text(result))
    if args.format in ("json", "both"):
        if args.format == "both":
            print("---JSON---")
        print(json.dumps(result.to_dict(), indent=2, ensure_ascii=False))

    return result.exit_code


if __name__ == "__main__":
    sys.exit(main())
