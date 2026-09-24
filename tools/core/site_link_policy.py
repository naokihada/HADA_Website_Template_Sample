#!/usr/bin/env python3
"""Validate durable site links and same-site host aliases.

The default publication contract uses root-relative URLs.  The apex host and
its ``www`` alias are treated as one site, while other subdomains remain
external unless explicitly configured.
"""

from __future__ import annotations

import argparse
import json
from html.parser import HTMLParser
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

try:
    import yaml
except ImportError:  # pragma: no cover - dependency check handles this
    yaml = None  # type: ignore[assignment]


DEFAULT_ATTRIBUTES = ("href", "src", "action")
DEFAULT_EXTERNAL_REL = ("noopener", "noreferrer")
DEFAULT_POLICY: dict[str, Any] = {
    "enabled": True,
    "roots": [],
    "attributes": list(DEFAULT_ATTRIBUTES),
    "internal_hosts": [],
    "base_path": "/",
    "external_links": {
        "require_new_tab": True,
        "required_rel": list(DEFAULT_EXTERNAL_REL),
    },
}
IGNORED_SCHEMES = {"data", "javascript", "mailto", "tel", "blob"}


def _read_config(root: Path) -> dict[str, Any]:
    if yaml is None:
        return {}
    for path in (root / "config" / "site.yaml", root / "config" / "site.example.yaml"):
        if not path.is_file():
            continue
        try:
            data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        except (OSError, yaml.YAMLError):
            return {}
        return data if isinstance(data, dict) else {}
    return {}


def _as_host(value: Any) -> str | None:
    text = str(value or "").strip()
    if not text:
        return None
    parsed = urlsplit(text if "://" in text else f"//{text}")
    host = parsed.hostname
    return host.lower().rstrip(".") if host else None


def _configured_url_hosts(data: dict[str, Any]) -> set[str]:
    site = data.get("site") if isinstance(data.get("site"), dict) else {}
    hosts: set[str] = set()
    urls = site.get("urls") if isinstance(site.get("urls"), dict) else {}
    for value in urls.values():
        host = _as_host(value)
        if host:
            hosts.add(host)
    for key in ("public_url", "canonical_url", "test_url", "local_url"):
        host = _as_host(site.get(key))
        if host:
            hosts.add(host)
    environments = data.get("environments") if isinstance(data.get("environments"), dict) else {}
    for item in environments.values():
        if isinstance(item, dict):
            host = _as_host(item.get("url"))
            if host:
                hosts.add(host)
    return hosts


def same_site_hosts(hosts: list[str] | set[str] | tuple[str, ...]) -> set[str]:
    """Normalize configured hosts and pair an apex host with its ``www`` alias.

    ``hada.org`` and ``www.hada.org`` therefore classify as one site.  A host
    such as ``gallery.hada.org`` is not broadened into the same-site set.
    """

    result: set[str] = set()
    for value in hosts:
        host = _as_host(value)
        if not host:
            continue
        result.add(host)
        if host.startswith("www."):
            result.add(host[4:])
        elif "." in host:
            result.add(f"www.{host}")
    return result


def _join_hosts(data: dict[str, Any], configured: Any) -> set[str]:
    values: list[str] = []
    if isinstance(configured, (list, tuple, set)):
        values.extend(str(value) for value in configured if isinstance(value, str))
    values.extend(_configured_url_hosts(data))
    return same_site_hosts(values)


def _publication_root(data: dict[str, Any]) -> str:
    site = data.get("site") if isinstance(data.get("site"), dict) else {}
    paths = data.get("paths") if isinstance(data.get("paths"), dict) else {}
    return str(site.get("publication_root") or paths.get("publication_root") or "site").strip("/")


def _normalize_base_path(value: Any) -> str:
    text = str(value or "/").replace("\\", "/").strip()
    if not text or text == ".":
        return "/"
    if not text.startswith("/"):
        text = f"/{text}"
    text = "/".join(part for part in text.split("/") if part)
    return f"/{text}/" if text != "/" else "/"


def load_policy(root: Path) -> dict[str, Any]:
    """Load and normalize the site link policy from project configuration."""

    data = _read_config(root)
    configured = data.get("link_policy") if isinstance(data.get("link_policy"), dict) else {}
    site = data.get("site") if isinstance(data.get("site"), dict) else {}
    urls = site.get("urls") if isinstance(site.get("urls"), dict) else {}
    policy = dict(DEFAULT_POLICY)
    policy.update(configured)

    roots = policy.get("roots")
    if not isinstance(roots, list) or not roots:
        roots = ["content/pages", _publication_root(data)]
    policy["roots"] = [str(value) for value in roots if isinstance(value, str)]

    base_path = policy.get("base_path") or site.get("base_path") or urls.get("base_path") or "/"
    policy["base_path"] = _normalize_base_path(base_path)
    policy["internal_hosts"] = sorted(_join_hosts(data, policy.get("internal_hosts")))

    external = policy.get("external_links")
    if not isinstance(external, dict):
        external = {}
    normalized_external = {"require_new_tab": True, "required_rel": list(DEFAULT_EXTERNAL_REL)}
    normalized_external.update(external)
    required_rel = normalized_external.get("required_rel")
    normalized_external["required_rel"] = [
        str(value).lower() for value in required_rel if isinstance(value, str)
    ] if isinstance(required_rel, list) else list(DEFAULT_EXTERNAL_REL)
    policy["external_links"] = normalized_external
    return policy


def site_url(path: str, policy: dict[str, Any] | None = None) -> str:
    """Return a configured root-relative URL for a site path."""

    value = str(path or "").replace("\\", "/")
    parsed = urlsplit(value)
    if parsed.scheme or parsed.netloc:
        raise ValueError("site_url accepts a path, not an absolute URL")
    path_part = parsed.path or "/"
    if not path_part.startswith("/"):
        path_part = f"/{path_part}"
    active = policy or DEFAULT_POLICY
    base = _normalize_base_path(active.get("base_path", "/"))
    if base == "/":
        result = path_part
    elif path_part == "/":
        result = base
    else:
        result = f"{base.rstrip('/')}{path_part}"
    return f"{result}?{parsed.query}" if parsed.query else result


def _is_internal_host(host: str | None, internal_hosts: set[str]) -> bool:
    return bool(host and host.lower().rstrip(".") in internal_hosts)


def _ignored_url(value: str) -> bool:
    parsed = urlsplit(value.strip())
    return not parsed.path and (bool(parsed.query) or bool(parsed.fragment)) or parsed.scheme.lower() in IGNORED_SCHEMES


def classify_url(value: str, internal_hosts: set[str]) -> dict[str, str] | None:
    """Return a ``LINK-002`` violation for a non-root-relative site URL."""

    url = value.strip()
    if not url or url.startswith("#") or _ignored_url(url):
        return None
    parsed = urlsplit(url)
    if parsed.scheme or parsed.netloc:
        if _is_internal_host(parsed.hostname, internal_hosts):
            return {"reason": "same-site URL must use a root-relative path"}
        return None
    path = parsed.path.replace("\\", "/")
    segments = [segment for segment in path.split("/") if segment]
    if ".." in segments or path.startswith("./") or path == ".":
        return {"reason": "parent-directory or dot-relative links are forbidden"}
    if path.startswith("/"):
        return None
    return {"reason": "site URL must start with `/`"}


def _is_external_url(value: str, internal_hosts: set[str]) -> bool:
    parsed = urlsplit(value.strip())
    return parsed.scheme.lower() in {"http", "https"} and not _is_internal_host(parsed.hostname, internal_hosts)


class _HTMLLinkParser(HTMLParser):
    def __init__(self, attributes: set[str], internal_hosts: set[str], external_policy: dict[str, Any]) -> None:
        super().__init__(convert_charrefs=True)
        self.attributes = attributes
        self.internal_hosts = internal_hosts
        self.external_policy = external_policy
        self.violations: list[dict[str, Any]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        line, _ = self.getpos()
        values = {name.lower(): value for name, value in attrs if value is not None}
        for name, value in values.items():
            if name not in self.attributes:
                continue
            issue = classify_url(value, self.internal_hosts)
            if issue:
                self.violations.append(
                    {
                        "rule_id": "LINK-002",
                        "line": line,
                        "tag": tag,
                        "attribute": name,
                        "value": value,
                        **issue,
                        "template_feedback": True,
                    }
                )
        href = values.get("href")
        if tag.lower() != "a" or not href or not _is_external_url(href, self.internal_hosts):
            return
        required_target = self.external_policy.get("require_new_tab", True)
        required_rel = set(self.external_policy.get("required_rel", DEFAULT_EXTERNAL_REL))
        rel = {item.lower() for item in str(values.get("rel", "")).split()}
        if (required_target and values.get("target") != "_blank") or not required_rel.issubset(rel):
            self.violations.append(
                {
                    "rule_id": "LINK-003",
                    "line": line,
                    "tag": tag,
                    "attribute": "href",
                    "value": href,
                    "reason": "external links require target=\"_blank\" and rel=\"noopener noreferrer\"",
                    "template_feedback": True,
                }
            )


def _configured_paths(root: Path, policy: dict[str, Any]) -> list[Path]:
    paths: list[Path] = []
    root_resolved = root.resolve()
    for value in policy.get("roots", []):
        if not isinstance(value, str):
            continue
        candidate = Path(value.replace("/", "\\"))
        if candidate.is_absolute() or ".." in candidate.parts:
            continue
        resolved = (root / candidate).resolve()
        if (candidate == Path(".") or resolved != root_resolved) and resolved.is_relative_to(root_resolved):
            paths.append(resolved)
    return paths


def scan(root: Path, policy: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    """Scan configured HTML roots and return policy violations."""

    active = policy if policy is not None else load_policy(root)
    if active.get("enabled", True) is False:
        return []
    attributes = {
        str(value).lower()
        for value in (active.get("attributes") or DEFAULT_ATTRIBUTES)
        if isinstance(value, str)
    }
    internal_hosts = set(str(value).lower().rstrip(".") for value in active.get("internal_hosts", []))
    external_policy = active.get("external_links") if isinstance(active.get("external_links"), dict) else {}
    violations: list[dict[str, Any]] = []
    seen: set[Path] = set()
    for scan_root in _configured_paths(root, active):
        if not scan_root.is_dir():
            continue
        for path in sorted(scan_root.rglob("*.html")):
            if path in seen:
                continue
            seen.add(path)
            parser = _HTMLLinkParser(attributes, internal_hosts, external_policy)
            try:
                parser.feed(path.read_text(encoding="utf-8"))
            except (OSError, UnicodeError) as exc:
                parser.violations.append(
                    {
                        "rule_id": "LINK-002",
                        "line": 1,
                        "tag": "",
                        "attribute": "",
                        "value": "",
                        "reason": f"could not read HTML: {exc}",
                        "template_feedback": True,
                    }
                )
            for item in parser.violations:
                violations.append({"file": path.relative_to(root).as_posix(), **item})
    return violations


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=".")
    parser.add_argument("--format", choices=("text", "json"), default="text")
    args = parser.parse_args(argv)
    root = Path(args.root).resolve()
    violations = scan(root)
    result = {
        "schema_version": "0.1",
        "policy": "root-relative-site-links",
        "status": "PASS" if not violations else "FAIL",
        "template_feedback_required": bool(violations),
        "same_site_aliases": sorted(load_policy(root).get("internal_hosts", [])),
        "violations": violations,
    }
    if args.format == "json":
        print(json.dumps(result, ensure_ascii=False, indent=2))
    elif violations:
        print("Site link policy: FAIL")
        for item in violations:
            print(f"{item['file']}:{item['line']} {item['attribute']}={item['value']!r}: {item['reason']}")
        print("Template feedback: REQUIRED")
    else:
        print("Site link policy: PASS")
    return 1 if violations else 0


if __name__ == "__main__":
    raise SystemExit(main())
