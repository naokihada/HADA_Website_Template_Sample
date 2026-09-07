#!/usr/bin/env python3
"""Core framework validator — implements tools/core/SPEC.md v0.1."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

try:
    import yaml
except ImportError:
    yaml = None  # type: ignore[assignment]

VALIDATOR_NAME = "core-validator"
VALIDATOR_VERSION = "0.1"
SCHEMA_VERSION = "0.1"

PROJECT_MODES = {"NEW", "RECOVERY", "MIGRATION", "MAINTENANCE"}
LIFECYCLE_STATES = {
    "SPECIFIED",
    "INSTALLING",
    "INSTALLED",
    "ENABLED",
    "DISABLED",
    "UNINSTALLING",
    "UNINSTALLED",
    "FAILED",
}
RSS_STATES = {"FULL", "PARTIAL", "NO_CONTENT"}
FOUNDATION_LOCALES = {"en", "jp"}
CONTENT_IGNORE_NAMES = {".gitkeep"}
FORBIDDEN_SEGMENTS = {"Cursor", "content", "tools", "config", "references", "docs", ".cursor"}
SAFE_SECRET_VALUES = {
    "",
    "null",
    "none",
    "~",
    '""',
    "''",
    "<secret>",
    "redacted",
    "example",
}
AWS_KEY_PATTERN = re.compile(r"AKIA[0-9A-Z]{16}")
REF_ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9-]*$")
SEMVER_PATTERN = re.compile(r"^\d+\.\d+(\.\d+)?$")
SECRET_LINE_PATTERN = re.compile(
    r"^\s*(password|passwd|api_key)\s*:\s*(.+?)\s*(?:#.*)?$",
    re.IGNORECASE,
)
CREDENTIALS_URL_PATTERN = re.compile(r"url\s*:\s*['\"]?[^'\"]*://[^:@/]+:[^@/]+@", re.IGNORECASE)
PRIVATE_PATH_PATTERNS = (
    re.compile(r"C:\\Users\\", re.IGNORECASE),
    re.compile(r"D:\\_dev\\", re.IGNORECASE),
    re.compile(r"^/home/", re.IGNORECASE),
)


@dataclass
class Finding:
    rule_id: str
    severity: str
    message: str
    file: Optional[str] = None
    field: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "rule_id": self.rule_id,
            "severity": self.severity,
            "message": self.message,
            "file": self.file,
            "field": self.field,
        }


@dataclass
class ValidationContext:
    root: Path
    include_local: bool = False
    findings: List[Finding] = field(default_factory=list)
    checked_rules: Set[str] = field(default_factory=set)
    dedup_keys: Set[str] = field(default_factory=set)
    project_data: Optional[Dict[str, Any]] = None
    publication_root_value: Optional[str] = None

    def add(
        self,
        rule_id: str,
        severity: str,
        message: str,
        file: Optional[str] = None,
        field: Optional[str] = None,
        dedup: Optional[str] = None,
    ) -> None:
        self.checked_rules.add(rule_id)
        if dedup and dedup in self.dedup_keys:
            return
        if dedup:
            self.dedup_keys.add(dedup)
        self.findings.append(
            Finding(rule_id=rule_id, severity=severity, message=message, file=file, field=field)
        )

    def mark_checked(self, rule_id: str) -> None:
        self.checked_rules.add(rule_id)


def load_yaml_file(path: Path) -> tuple[Optional[Any], Optional[str]]:
    if yaml is None:
        return None, "PyYAML is not available"
    try:
        content = path.read_text(encoding="utf-8")
    except OSError as exc:
        return None, str(exc)
    try:
        data = yaml.safe_load(content)
        if data is None:
            return {}, None
        return data, None
    except yaml.YAMLError as exc:
        return None, str(exc)


def normalize_path(path_value: str) -> str:
    return path_value.replace("\\", "/")


def path_segments(path_value: str) -> List[str]:
    normalized = normalize_path(path_value)
    return [part for part in normalized.split("/") if part and part != "."]


def forbidden_segment(path_value: Optional[str]) -> Optional[str]:
    if not path_value or not isinstance(path_value, str):
        return None
    for segment in path_segments(path_value):
        if segment in FORBIDDEN_SEGMENTS:
            return segment
    return None


def resolve_repo_path(root: Path, path_value: Optional[str]) -> Optional[Path]:
    if not path_value or not isinstance(path_value, str):
        return None
    candidate = Path(path_value.replace("\\", "/"))
    if candidate.is_absolute():
        return candidate
    return (root / candidate).resolve()


def is_safe_secret_value(value: str) -> bool:
    cleaned = value.strip().strip("'\"")
    if not cleaned:
        return True
    return cleaned.lower() in SAFE_SECRET_VALUES


def git_tracked(root: Path, rel_path: str) -> bool:
    try:
        result = subprocess.run(
            ["git", "-C", str(root), "ls-files", "--error-unmatch", rel_path],
            capture_output=True,
            text=True,
            check=False,
        )
        return result.returncode == 0
    except OSError:
        return False


def scan_secrets_in_text(rel_file: str, text: str, ctx: ValidationContext) -> None:
    for line_no, line in enumerate(text.splitlines(), start=1):
        match = SECRET_LINE_PATTERN.match(line)
        if match:
            raw_value = match.group(2).strip()
            if not is_safe_secret_value(raw_value):
                ctx.add(
                    "SEC-001",
                    "ERROR",
                    "Secret-like assignment detected in committed configuration",
                    file=rel_file,
                    field=f"line {line_no}",
                    dedup=f"SEC-001:{rel_file}:{line_no}",
                )
        if AWS_KEY_PATTERN.search(line):
            ctx.add(
                "SEC-002",
                "ERROR",
                "AWS key pattern detected in committed configuration",
                file=rel_file,
                field=f"line {line_no}",
                dedup=f"SEC-002:{rel_file}:{line_no}",
            )
        for pattern in PRIVATE_PATH_PATTERNS:
            if pattern.search(line):
                ctx.add(
                    "SEC-003",
                    "WARNING",
                    "Private local absolute path detected in committed configuration",
                    file=rel_file,
                    field=f"line {line_no}",
                    dedup=f"SEC-003:{rel_file}:{line_no}",
                )
                break


def validate_structure(ctx: ValidationContext) -> None:
    root = ctx.root
    checks = [
        ("STRUCT-001", root / "AGENTS.md", False, "AGENTS.md"),
        ("STRUCT-002", root / "README.md", False, "README.md"),
        ("STRUCT-003", root / ".gitignore", False, ".gitignore"),
        ("STRUCT-004", root / "Cursor", True, "Cursor/"),
        ("STRUCT-005", root / "content" / "en", True, "content/en/"),
        ("STRUCT-006", root / "content" / "jp", True, "content/jp/"),
        ("STRUCT-007", root / "site", True, "site/"),
        ("STRUCT-008", root / "site" / "README.md", False, "site/README.md"),
        ("STRUCT-009", root / "site" / "en", True, "site/en/"),
        ("STRUCT-010", root / "site" / "jp", True, "site/jp/"),
        ("STRUCT-011", root / "site" / "assets", True, "site/assets/"),
        ("STRUCT-012", root / "references" / "registry", True, "references/registry/"),
        ("STRUCT-013", root / "references" / "cache", True, "references/cache/"),
        ("STRUCT-014", root / "references" / "reports", True, "references/reports/"),
        ("STRUCT-015", root / "environments", True, "environments/"),
        ("STRUCT-016", root / "tools" / "core", True, "tools/core/"),
        ("STRUCT-017", root / "tools" / "plugins", True, "tools/plugins/"),
        ("STRUCT-018", root / "tests", True, "tests/"),
        ("STRUCT-019", root / "docs", True, "docs/"),
        ("STRUCT-020", root / "config", True, "config/"),
        ("STRUCT-021", root / ".cursor" / "rules", True, ".cursor/rules/"),
    ]
    for rule_id, path, is_dir, rel in checks:
        ctx.mark_checked(rule_id)
        exists = path.is_dir() if is_dir else path.is_file()
        if not exists:
            ctx.add(rule_id, "ERROR", f"Required {'directory' if is_dir else 'file'} missing", file=rel)

    ctx.mark_checked("STRUCT-022")
    rules_dir = root / ".cursor" / "rules"
    if rules_dir.is_dir():
        rule_files = sorted(p for p in rules_dir.iterdir() if p.is_file())
        if len(rule_files) < 8:
            ctx.add("STRUCT-022", "WARNING", "Fewer than 8 files in .cursor/rules/", file=".cursor/rules/")


def validate_project_config(ctx: ValidationContext) -> None:
    root = ctx.root
    project_path = root / "config" / "project.yaml"
    site_example_path = root / "config" / "site.example.yaml"
    site_path = root / "config" / "site.yaml"

    ctx.mark_checked("CFG-001")
    if not project_path.is_file():
        ctx.add("CFG-001", "ERROR", "config/project.yaml missing", file="config/project.yaml")
        ctx.mark_checked("STRUCT-023")
        return

    project_data, error = load_yaml_file(project_path)
    if error:
        ctx.add("CFG-001", "ERROR", f"Invalid YAML: {error}", file="config/project.yaml")
        ctx.mark_checked("STRUCT-023")
        return

    ctx.project_data = project_data if isinstance(project_data, dict) else {}
    project = ctx.project_data.get("project", {})
    paths = ctx.project_data.get("paths", {})
    locales = ctx.project_data.get("locales", {})

    checks = [
        ("CFG-002", all(k in project for k in ("id", "name", "version", "mode")), "Missing required project fields", "project"),
        ("CFG-003", project.get("mode") in PROJECT_MODES, "project.mode must be NEW, RECOVERY, MIGRATION, or MAINTENANCE", "project.mode"),
        ("CFG-004", all(k in paths for k in ("publication_root", "content_master", "tools_core", "tools_plugins")), "Missing required paths fields", "paths"),
        ("CFG-005", locales.get("default") in locales.get("supported", []), "locales.default must appear in locales.supported", "locales.default"),
    ]
    for rule_id, ok, message, fld in checks:
        ctx.mark_checked(rule_id)
        if not ok:
            ctx.add(rule_id, "ERROR", message, file="config/project.yaml", field=fld)

    ctx.mark_checked("CFG-006")
    supported = locales.get("supported", [])
    if not isinstance(supported, list) or any(item not in FOUNDATION_LOCALES for item in supported):
        ctx.add("CFG-006", "ERROR", "Each locales.supported entry must be en or jp", file="config/project.yaml", field="locales.supported")

    pub_root = paths.get("publication_root")
    content_root = paths.get("content_master")
    ctx.publication_root_value = pub_root if isinstance(pub_root, str) else None

    publication_missing = False
    ctx.mark_checked("CFG-007")
    pub_resolved = resolve_repo_path(root, ctx.publication_root_value)
    if not pub_root or pub_resolved is None or not pub_resolved.is_dir():
        publication_missing = True
        ctx.add("CFG-007", "ERROR", "paths.publication_root does not resolve to an existing directory", file="config/project.yaml", field="paths.publication_root")

    ctx.mark_checked("CFG-008")
    content_resolved = resolve_repo_path(root, content_root if isinstance(content_root, str) else None)
    if not content_root or content_resolved is None or not content_resolved.is_dir():
        ctx.add("CFG-008", "ERROR", "paths.content_master does not resolve to an existing directory", file="config/project.yaml", field="paths.content_master")

    ctx.mark_checked("STRUCT-023")
    if publication_missing and not any(
        item.rule_id == "CFG-007" for item in ctx.findings
    ):
        ctx.add(
            "STRUCT-023",
            "ERROR",
            "Publication root directory from config/project.yaml missing",
            file=str(pub_root) if pub_root else "config/project.yaml",
            field="paths.publication_root",
        )

    ctx.mark_checked("CFG-009")
    if not site_example_path.is_file():
        ctx.add("CFG-009", "ERROR", "config/site.example.yaml missing", file="config/site.example.yaml")
    else:
        _, error = load_yaml_file(site_example_path)
        if error:
            ctx.add("CFG-009", "ERROR", f"Invalid YAML: {error}", file="config/site.example.yaml")

    ctx.mark_checked("CFG-010")
    if not site_path.is_file():
        ctx.add("CFG-010", "WARNING", "config/site.yaml missing", file="config/site.yaml")
    else:
        validate_site_config(ctx, site_path)


def validate_site_config(ctx: ValidationContext, site_path: Path) -> None:
    rel = "config/site.yaml"
    data, error = load_yaml_file(site_path)
    if error:
        ctx.add("CFG-011", "ERROR", f"Invalid YAML: {error}", file=rel)
        return

    site = data.get("site", {}) if isinstance(data, dict) else {}
    publication = data.get("publication", {}) if isinstance(data, dict) else {}
    plugins = data.get("plugins", {}) if isinstance(data, dict) else {}
    rss = data.get("rss", {}) if isinstance(data, dict) else {}
    project_pub = ctx.publication_root_value or "site"

    ctx.mark_checked("CFG-011")
    site_pub = site.get("publication_root")
    if site_pub and normalize_path(str(site_pub)) != normalize_path(str(project_pub)):
        ctx.add("CFG-011", "ERROR", "site.publication_root must match config/project.yaml paths.publication_root", file=rel, field="site.publication_root")

    deploy_target = publication.get("deploy_target")
    ctx.mark_checked("CFG-012")
    if deploy_target and normalize_path(str(deploy_target)) not in {normalize_path(str(project_pub)), "site", "site/"}:
        ctx.add("CFG-012", "ERROR", "publication.deploy_target must equal publication root", file=rel, field="publication.deploy_target")

    ctx.mark_checked("CFG-013")
    locale_paths = publication.get("locales", {})
    if isinstance(locale_paths, dict):
        for key, value in locale_paths.items():
            if not isinstance(value, str):
                continue
            segment = forbidden_segment(value)
            if segment:
                ctx.add("CFG-013", "ERROR", f"publication locale path contains forbidden segment '{segment}'", file=rel, field=f"publication.locales.{key}")
            elif project_pub and not normalize_path(value).startswith(normalize_path(str(project_pub))):
                ctx.add("CFG-013", "ERROR", "publication locale path must stay under publication root", file=rel, field=f"publication.locales.{key}")

    ctx.mark_checked("CFG-014")
    enabled = plugins.get("enabled", [])
    if isinstance(enabled, list):
        for index, item in enumerate(enabled):
            if isinstance(item, dict) and item.get("state") not in LIFECYCLE_STATES:
                ctx.add("CFG-014", "ERROR", "Invalid plugin lifecycle state", file=rel, field=f"plugins.enabled[{index}].state")

    ctx.mark_checked("CFG-015")
    default_state = rss.get("default_state")
    if default_state is not None and default_state not in RSS_STATES:
        ctx.add("CFG-015", "ERROR", "rss.default_state must be FULL, PARTIAL, or NO_CONTENT", file=rel, field="rss.default_state")

    check_publication_paths(ctx, rel, site_pub, deploy_target, publication.get("locales", {}))


def check_publication_paths(ctx: ValidationContext, rel_file: str, publication_root: Any, deploy_target: Any, locale_paths: Any) -> None:
    ctx.mark_checked("SEC-004")
    targets: list[tuple[str, str]] = []
    if publication_root:
        targets.append(("site.publication_root", str(publication_root)))
    if deploy_target:
        targets.append(("publication.deploy_target", str(deploy_target)))
    if isinstance(locale_paths, dict):
        for key, value in locale_paths.items():
            if isinstance(value, str):
                targets.append((f"publication.locales.{key}", value))
    for field_name, value in targets:
        segment = forbidden_segment(value)
        if segment:
            ctx.add("SEC-004", "ERROR", f"Path contains forbidden segment '{segment}'", file=rel_file, field=field_name, dedup=f"SEC-004:{rel_file}:{field_name}")


def validate_environment_file(ctx: ValidationContext, rel_file: str, path: Path) -> None:
    ctx.mark_checked("ENV-001")
    if not path.is_file():
        ctx.add("ENV-001", "ERROR", f"{rel_file} missing", file=rel_file)
        return

    text = path.read_text(encoding="utf-8")
    scan_secrets_in_text(rel_file, text, ctx)
    data, error = load_yaml_file(path)
    if error:
        ctx.add("ENV-001", "ERROR", f"Invalid YAML: {error}", file=rel_file)
        return

    environments = data.get("environments") if isinstance(data, dict) else None
    ctx.mark_checked("ENV-002")
    if not isinstance(environments, dict):
        ctx.add("ENV-002", "ERROR", "Top-level environments key missing", file=rel_file)
        return

    ctx.mark_checked("ENV-003")
    for name in ("LOCAL", "STAGING", "PRODUCTION"):
        if name not in environments:
            ctx.add("ENV-003", "ERROR", f"Missing environment definition: {name}", file=rel_file, field=f"environments.{name}")

    for env_name, env_cfg in environments.items():
        if not isinstance(env_cfg, dict):
            continue
        ctx.mark_checked("ENV-004")
        for key in ("description", "approval_required", "publication_root"):
            if key not in env_cfg:
                ctx.add("ENV-004", "ERROR", f"Missing required environment field: {key}", file=rel_file, field=f"environments.{env_name}.{key}")

        pub_root = env_cfg.get("publication_root")
        if isinstance(pub_root, str):
            ctx.mark_checked("ENV-008")
            resolved = resolve_repo_path(ctx.root, pub_root)
            if resolved is None or not str(resolved).startswith(str(ctx.root.resolve())):
                ctx.add("ENV-008", "ERROR", "Environment publication_root must stay inside repository", file=rel_file, field=f"environments.{env_name}.publication_root", dedup=f"ENV-008:{rel_file}:{env_name}:outside")
            segment = forbidden_segment(pub_root)
            if segment:
                ctx.add("ENV-008", "ERROR", f"Environment publication_root contains forbidden segment '{segment}'", file=rel_file, field=f"environments.{env_name}.publication_root", dedup=f"ENV-008:{rel_file}:{env_name}:{segment}")

        web = env_cfg.get("web", {})
        if isinstance(web, dict):
            ctx.mark_checked("ENV-009")
            if web.get("hostname") is None:
                ctx.add("ENV-009", "INFO", "web.hostname is null", file=rel_file, field=f"environments.{env_name}.web.hostname", dedup=f"ENV-009:{rel_file}:{env_name}")

    production = environments.get("PRODUCTION", {})
    ctx.mark_checked("ENV-005")
    if isinstance(production, dict) and production.get("approval_required") is not True:
        ctx.add("ENV-005", "ERROR", "PRODUCTION.approval_required must be true", file=rel_file, field="environments.PRODUCTION.approval_required")

    staging = environments.get("STAGING", {})
    ctx.mark_checked("ENV-006")
    if isinstance(staging, dict) and staging.get("approval_required") is not True:
        ctx.add("ENV-006", "ERROR", "STAGING.approval_required must be true", file=rel_file, field="environments.STAGING.approval_required")

    local = environments.get("LOCAL", {})
    ctx.mark_checked("ENV-007")
    if isinstance(local, dict) and local.get("approval_required") is not False:
        ctx.add("ENV-007", "WARNING", "LOCAL.approval_required should be false", file=rel_file, field="environments.LOCAL.approval_required")


def validate_references_registry(ctx: ValidationContext, rel_file: str, path: Path) -> None:
    ctx.mark_checked("REF-001")
    if not path.is_file():
        ctx.add("REF-001", "ERROR", f"{rel_file} missing", file=rel_file)
        return

    text = path.read_text(encoding="utf-8")
    scan_secrets_in_text(rel_file, text, ctx)
    data, error = load_yaml_file(path)
    if error:
        ctx.add("REF-001", "ERROR", f"Invalid YAML: {error}", file=rel_file)
        return

    ctx.mark_checked("REF-002")
    if "version" not in data:
        ctx.add("REF-002", "ERROR", "version field missing", file=rel_file, field="version")

    references = data.get("references") if isinstance(data, dict) else None
    ctx.mark_checked("REF-003")
    if not isinstance(references, list):
        ctx.add("REF-003", "ERROR", "references must be a list", file=rel_file, field="references")
        return

    seen_ids: Set[str] = set()
    for index, entry in enumerate(references):
        if not isinstance(entry, dict):
            continue
        ctx.mark_checked("REF-004")
        for key in ("id", "type", "description", "readonly"):
            if key not in entry:
                ctx.add("REF-004", "ERROR", f"Reference entry missing required field: {key}", file=rel_file, field=f"references[{index}].{key}")
        ref_id = entry.get("id")
        if isinstance(ref_id, str):
            ctx.mark_checked("REF-005")
            if ref_id in seen_ids:
                ctx.add("REF-005", "ERROR", f"Duplicate reference id: {ref_id}", file=rel_file, field=f"references[{index}].id")
            seen_ids.add(ref_id)
            ctx.mark_checked("REF-006")
            if not REF_ID_PATTERN.match(ref_id):
                ctx.add("REF-006", "ERROR", "Reference id has invalid format", file=rel_file, field=f"references[{index}].id")
        path_value = entry.get("path")
        if isinstance(path_value, str):
            ctx.mark_checked("REF-007")
            for pattern in PRIVATE_PATH_PATTERNS:
                if pattern.search(path_value):
                    ctx.add("REF-007", "WARNING", "Reference entry contains absolute private path", file=rel_file, field=f"references[{index}].path")
                    break
        url_value = entry.get("url")
        if isinstance(url_value, str):
            ctx.mark_checked("REF-008")
            if CREDENTIALS_URL_PATTERN.search(f"url: {url_value}"):
                ctx.add("REF-008", "WARNING", "Reference entry url contains embedded credentials", file=rel_file, field=f"references[{index}].url")
        ctx.mark_checked("REF-009")
        if entry.get("adapter") == "wordpress-com" and entry.get("type") != "external_content_source":
            ctx.add("REF-009", "ERROR", "wordpress-com adapter requires external_content_source type", file=rel_file, field=f"references[{index}].type")


def validate_plugin_manifest(ctx: ValidationContext, plugin_id: str, manifest_path: Path) -> None:
    rel = f"tools/plugins/{plugin_id}/manifest.yaml"
    data, error = load_yaml_file(manifest_path)
    ctx.mark_checked("PLUGIN-001")
    if error:
        ctx.add("PLUGIN-001", "ERROR", f"Invalid YAML: {error}", file=rel)
        return

    plugin = data.get("plugin", {}) if isinstance(data, dict) else {}
    status = plugin.get("status")
    spec_version = plugin.get("spec_version")
    checks = [
        ("PLUGIN-002", all(k in plugin for k in ("id", "version", "status", "spec_version")), "Missing required plugin manifest fields", "plugin"),
        ("PLUGIN-003", plugin.get("id") == plugin_id, "plugin.id must match directory name", "plugin.id"),
        ("PLUGIN-004", status in LIFECYCLE_STATES, "Invalid plugin lifecycle state", "plugin.status"),
        ("PLUGIN-005", isinstance(spec_version, str) and bool(SEMVER_PATTERN.match(spec_version)), "plugin.spec_version must be semver-like", "plugin.spec_version"),
        ("PLUGIN-010", plugin.get("id") != "core-validator", "plugin.id must not equal reserved name core-validator", "plugin.id"),
    ]
    for rule_id, ok, message, fld in checks:
        ctx.mark_checked(rule_id)
        if not ok:
            ctx.add(rule_id, "ERROR", message, file=rel, field=fld)

    ctx.mark_checked("PLUGIN-006")
    if status == "ENABLED" and "dependencies" not in data:
        ctx.add("PLUGIN-006", "WARNING", "dependencies missing for ENABLED plugin", file=rel, field="dependencies")

    ownership = data.get("ownership", {}) if isinstance(data, dict) else {}
    ctx.mark_checked("PLUGIN-007")
    if status in {"ENABLED", "INSTALLED"} and not ownership.get("maintainer"):
        ctx.add("PLUGIN-007", "ERROR", "ownership.maintainer required for ENABLED or INSTALLED plugin", file=rel, field="ownership.maintainer")

    ctx.mark_checked("PLUGIN-008")
    if status in {"INSTALLING", "INSTALLED"} and "changed_files" not in data:
        ctx.add("PLUGIN-008", "WARNING", "changed_files missing for INSTALLING or INSTALLED plugin", file=rel, field="changed_files")

    reversibility = data.get("reversibility", {}) if isinstance(data, dict) else {}
    ctx.mark_checked("PLUGIN-009")
    if isinstance(reversibility.get("uninstall_supported"), bool):
        ctx.add("PLUGIN-009", "INFO", "reversibility.uninstall_supported documented", file=rel, field="reversibility.uninstall_supported")


def validate_security(ctx: ValidationContext) -> None:
    root = ctx.root
    for directory in (root / "config", root / "environments", root / "references" / "registry"):
        if not directory.is_dir():
            continue
        for path in sorted(directory.glob("*.yaml")):
            rel = path.relative_to(root).as_posix()
            try:
                scan_secrets_in_text(rel, path.read_text(encoding="utf-8"), ctx)
            except OSError:
                continue

    ctx.mark_checked("SEC-005")
    for rel in (".env", "config/local.yaml"):
        if git_tracked(root, rel):
            ctx.add("SEC-005", "WARNING", f"{rel} is tracked by Git and should be gitignored", file=rel)

    ctx.mark_checked("SEC-006")
    if ctx.include_local and (root / "config" / "local.yaml").is_file():
        ctx.add("SEC-006", "INFO", "config/local.yaml exists locally", file="config/local.yaml")


def content_basenames(locale_dir: Path) -> Set[str]:
    if not locale_dir.is_dir():
        return set()
    return {
        path.name
        for path in locale_dir.iterdir()
        if path.is_file() and path.name not in CONTENT_IGNORE_NAMES and not path.name.startswith(".")
    }


def validate_i18n(ctx: ValidationContext) -> None:
    root = ctx.root
    locales_cfg = []
    if ctx.project_data and isinstance(ctx.project_data.get("locales"), dict):
        supported = ctx.project_data["locales"].get("supported", [])
        if isinstance(supported, list):
            locales_cfg = [item for item in supported if isinstance(item, str)]

    ctx.mark_checked("I18N-001")
    for locale in locales_cfg:
        locale_dir = root / "content" / locale
        if not locale_dir.is_dir():
            ctx.add(
                "I18N-001",
                "ERROR",
                f"Content Master directory missing for configured locale",
                file=f"content/{locale}/",
                field=f"locales.supported.{locale}",
            )

    en_dir = root / "content" / "en"
    jp_dir = root / "content" / "jp"
    en_files = content_basenames(en_dir)
    jp_files = content_basenames(jp_dir)

    ctx.mark_checked("I18N-002")
    for name in sorted(en_files - jp_files):
        ctx.add(
            "I18N-002",
            "WARNING",
            "Missing jp counterpart for en content file (basename match required)",
            file=f"content/jp/{name}",
            field="basename",
            dedup=f"I18N-002:{name}",
        )

    ctx.mark_checked("I18N-003")
    for name in sorted(jp_files - en_files):
        ctx.add(
            "I18N-003",
            "WARNING",
            "Missing en counterpart for jp content file (basename match required)",
            file=f"content/en/{name}",
            field="basename",
            dedup=f"I18N-003:{name}",
        )

    ctx.mark_checked("I18N-004")
    if not en_files and not jp_files:
        ctx.add(
            "I18N-004",
            "INFO",
            "No content master files in en or jp locales",
            file="content/",
            field="locales",
        )


def discover_plugin_manifests(root: Path) -> list[tuple[str, Path]]:
    plugins_root = root / "tools" / "plugins"
    manifests: list[tuple[str, Path]] = []
    if not plugins_root.is_dir():
        return manifests
    for child in sorted(plugins_root.iterdir()):
        if child.is_dir() and (child / "manifest.yaml").is_file():
            manifests.append((child.name, child / "manifest.yaml"))
    return manifests


def run_validation(root: Path, include_local: bool = False) -> ValidationContext:
    ctx = ValidationContext(root=root.resolve(), include_local=include_local)
    validate_structure(ctx)
    validate_project_config(ctx)
    validate_environment_file(ctx, "environments/environments.example.yaml", root / "environments" / "environments.example.yaml")
    env_active = root / "environments" / "environments.yaml"
    if env_active.is_file():
        validate_environment_file(ctx, "environments/environments.yaml", env_active)
    registry_dir = root / "references" / "registry"
    if registry_dir.is_dir():
        for path in sorted(registry_dir.glob("*.yaml")):
            validate_references_registry(ctx, path.relative_to(root).as_posix(), path)
    for plugin_id, manifest_path in discover_plugin_manifests(root):
        validate_plugin_manifest(ctx, plugin_id, manifest_path)
    validate_i18n(ctx)
    validate_security(ctx)
    return ctx


def sort_findings(findings: List[Finding]) -> List[Finding]:
    return sorted(findings, key=lambda item: (item.rule_id, item.file or "", item.field or ""))


def build_result(ctx: ValidationContext, task_id: Optional[str], strict: bool, duration_ms: int, validator_error: bool = False) -> Dict[str, Any]:
    findings = sort_findings(ctx.findings)
    errors = [item for item in findings if item.severity == "ERROR"]
    warnings = [item for item in findings if item.severity == "WARNING"]
    infos = [item for item in findings if item.severity == "INFO"]
    effective_errors = list(errors)
    if strict:
        effective_errors.extend(warnings)

    if validator_error:
        status = "ERROR"
        exit_code = 2
        next_action = "validator_error"
    elif effective_errors:
        status = "FAIL"
        exit_code = 1
        next_action = "fix_errors" if errors else "review_warnings"
    else:
        status = "PASS"
        exit_code = 0
        next_action = "none"

    return {
        "schema_version": SCHEMA_VERSION,
        "task_id": task_id,
        "validator": VALIDATOR_NAME,
        "validator_version": VALIDATOR_VERSION,
        "timestamp": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "root": str(ctx.root),
        "status": status,
        "exit_code": exit_code,
        "summary": {
            "checked": len(ctx.checked_rules),
            "failed_checks": len(errors),
            "errors": len(errors),
            "warnings": len(warnings),
            "info": len(infos),
        },
        "findings": [item.to_dict() for item in findings],
        "errors": [item.to_dict() for item in errors],
        "warnings": [item.to_dict() for item in warnings],
        "next_action": next_action,
        "duration_ms": duration_ms,
    }


def build_dependency_error_result(
    root: str,
    task_id: Optional[str],
    duration_ms: int = 0,
) -> Dict[str, Any]:
    message = (
        "PyYAML is required. Install dependencies before running core-validator "
        "(pip install -r tools/core/requirements.txt)."
    )
    finding = {
        "rule_id": "VALIDATOR-DEP",
        "severity": "ERROR",
        "message": message,
        "file": "tools/core/requirements.txt",
        "field": None,
    }
    return {
        "schema_version": SCHEMA_VERSION,
        "task_id": task_id,
        "validator": VALIDATOR_NAME,
        "validator_version": VALIDATOR_VERSION,
        "timestamp": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "root": root,
        "status": "ERROR",
        "exit_code": 2,
        "summary": {
            "checked": 0,
            "failed_checks": 1,
            "errors": 1,
            "warnings": 0,
            "info": 0,
        },
        "findings": [finding],
        "errors": [finding],
        "warnings": [],
        "next_action": "validator_error",
        "duration_ms": duration_ms,
    }


def format_text(result: Dict[str, Any]) -> str:
    summary = result["summary"]
    lines = [
        f"Validator: {result['validator']} v{result['validator_version']}",
        f"Root: {result['root']}",
        f"Status: {result['status']}",
        f"Checked: {summary['checked']}  Failed: {summary['failed_checks']}  Errors: {summary['errors']}  Warnings: {summary['warnings']}  Info: {summary['info']}",
        "",
    ]
    for item in result["findings"]:
        lines.append(f"[{item['severity']}] {item['rule_id']}  {item['message']}")
        if item.get("file"):
            lines.append(f"  file: {item['file']}")
        if item.get("field"):
            lines.append(f"  field: {item['field']}")
        lines.append("")
    if result["next_action"] == "fix_errors":
        lines.append("Next action: Fix reported ERROR items before release or plugin install.")
    elif result["next_action"] == "review_warnings":
        lines.append("Next action: Review WARNING items.")
    elif result["next_action"] == "validator_error":
        lines.append("Next action: Validator internal error.")
    else:
        lines.append("Next action: none.")
    return "\n".join(lines).rstrip() + "\n"


def emit_result(result: Dict[str, Any], output_format: str) -> None:
    if output_format == "text":
        print(format_text(result), end="")
    elif output_format == "json":
        print(json.dumps(result, indent=2))
    else:
        print(format_text(result), end="")
        print("---JSON---")
        print(json.dumps(result, indent=2))


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="HADA core-validator")
    parser.add_argument("--root", default=".")
    parser.add_argument("--format", choices=["text", "json", "both"], default="both")
    parser.add_argument("--task-id", default=None)
    parser.add_argument("--include-local", action="store_true")
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args(argv)

    start = time.perf_counter()

    if yaml is None:
        try:
            root_display = str(Path(args.root).resolve())
        except OSError:
            root_display = args.root
        result = build_dependency_error_result(root_display, args.task_id, 0)
        emit_result(result, args.format)
        return 2

    try:
        root = Path(args.root).resolve()
    except OSError:
        result = build_result(ValidationContext(root=Path(args.root)), args.task_id, args.strict, 0, validator_error=True)
        emit_result(result, args.format)
        return 2

    if not root.is_dir() or not (root / "AGENTS.md").is_file():
        ctx = ValidationContext(root=root)
        ctx.add("STRUCT-001", "ERROR", "Repository root is unreadable or missing AGENTS.md", file="AGENTS.md")
        result = build_result(ctx, args.task_id, args.strict, int((time.perf_counter() - start) * 1000), validator_error=True)
        emit_result(result, args.format)
        return 2

    ctx = run_validation(root, include_local=args.include_local)
    result = build_result(ctx, args.task_id, args.strict, int((time.perf_counter() - start) * 1000))
    emit_result(result, args.format)
    return int(result["exit_code"])


if __name__ == "__main__":
    sys.exit(main())
