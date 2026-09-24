#!/usr/bin/env python3
"""Enforce the Template Core external-JavaScript policy."""

from __future__ import annotations

import argparse
import json
import re
from html.parser import HTMLParser
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError:  # pragma: no cover - dependency check handles this
    yaml = None  # type: ignore[assignment]


EXTERNAL_URL_RE = re.compile(r"^https?://", re.IGNORECASE)
INLINE_JS_RE = re.compile(
    r"(?:import\s*\(\s*|import\s+|from\s+|\.src\s*=\s*|setAttribute\(\s*['\"]src['\"]\s*,\s*)['\"]?(https?://[^'\"\s,)]+)['\"]?",
    re.IGNORECASE,
)


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


def _publication_root(data: dict[str, Any]) -> str:
    site = data.get("site") if isinstance(data.get("site"), dict) else {}
    paths = data.get("paths") if isinstance(data.get("paths"), dict) else {}
    return str(site.get("publication_root") or paths.get("publication_root") or "site").strip("/")


def load_policy(root: Path) -> dict[str, Any]:
    data = _read_config(root)
    configured = data.get("external_javascript") if isinstance(data.get("external_javascript"), dict) else {}
    link_policy = data.get("link_policy") if isinstance(data.get("link_policy"), dict) else {}
    policy = {
        "policy": "forbidden",
        "roots": list(link_policy.get("roots") or ["content/pages", _publication_root(data)]),
        "declarations": [],
    }
    policy.update(configured)
    if not isinstance(policy.get("roots"), list):
        policy["roots"] = ["content/pages", _publication_root(data)]
    if not isinstance(policy.get("declarations"), list):
        policy["declarations"] = []
    return policy


def _configured_paths(root: Path, policy: dict[str, Any]) -> list[Path]:
    resolved_root = root.resolve()
    paths: list[Path] = []
    for value in policy.get("roots", []):
        if not isinstance(value, str):
            continue
        candidate = Path(value.replace("/", "\\"))
        if candidate.is_absolute() or ".." in candidate.parts:
            continue
        resolved = (root / candidate).resolve()
        if (candidate == Path(".") or resolved != resolved_root) and resolved.is_relative_to(resolved_root):
            paths.append(resolved)
    return paths


def _declaration_map(policy: dict[str, Any]) -> tuple[set[str], list[dict[str, Any]]]:
    allowed: set[str] = set()
    invalid: list[dict[str, Any]] = []
    for item in policy.get("declarations", []):
        if isinstance(item, str):
            allowed.add(item)
            continue
        if not isinstance(item, dict) or not isinstance(item.get("url"), str):
            invalid.append({"reason": "external JavaScript declaration must contain a url"})
            continue
        if item.get("required_for_content") is True:
            invalid.append(
                {
                    "reason": "external JavaScript must remain optional and must not be required for content",
                    "url": item.get("url"),
                }
            )
            continue
        allowed.add(str(item["url"]))
    return allowed, invalid


def _is_external_js(url: str) -> bool:
    return bool(EXTERNAL_URL_RE.match(url.strip()))


class _ScriptParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.in_script = False
        self.script_line = 1
        self.findings: list[dict[str, Any]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() != "script":
            return
        self.in_script = True
        self.script_line, _ = self.getpos()
        values = {name.lower(): value for name, value in attrs if value is not None}
        src = values.get("src")
        if src and _is_external_js(src):
            self.findings.append({"line": self.script_line, "url": src, "reason": "external script src"})

    def handle_data(self, data: str) -> None:
        if not self.in_script:
            return
        for match in INLINE_JS_RE.finditer(data):
            self.findings.append(
                {
                    "line": self.script_line + data[: match.start()].count("\n"),
                    "url": match.group(1),
                    "reason": "external JavaScript loaded by inline script",
                }
            )

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() == "script":
            self.in_script = False


def scan(root: Path, policy: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    """Return undeclared external-JavaScript findings under configured roots."""

    active = policy if policy is not None else load_policy(root)
    allowed, invalid = _declaration_map(active)
    declared_mode = str(active.get("policy", "forbidden")).lower() == "declared_client_only"
    findings: list[dict[str, Any]] = [
        {
            "rule_id": "JS-002",
            "file": "config/site.yaml",
            "line": 1,
            "url": item.get("url", ""),
            "reason": item["reason"],
            "template_feedback": True,
        }
        for item in invalid
    ]
    seen: set[Path] = set()
    for scan_root in _configured_paths(root, active):
        if not scan_root.is_dir():
            continue
        for path in sorted(scan_root.rglob("*")):
            if not path.is_file() or path in seen or path.suffix.lower() not in {".html", ".js"}:
                continue
            seen.add(path)
            text = path.read_text(encoding="utf-8", errors="replace")
            candidates: list[dict[str, Any]] = []
            if path.suffix.lower() == ".html":
                parser = _ScriptParser()
                parser.feed(text)
                candidates.extend(parser.findings)
            else:
                for match in INLINE_JS_RE.finditer(text):
                    candidates.append(
                        {
                            "line": text[: match.start()].count("\n") + 1,
                            "url": match.group(1),
                            "reason": "external JavaScript loaded by local script",
                        }
                    )
            for candidate in candidates:
                url = str(candidate.get("url", ""))
                if not _is_external_js(url):
                    continue
                if declared_mode and url in allowed:
                    continue
                findings.append(
                    {
                        "rule_id": "JS-001",
                        "file": path.relative_to(root).as_posix(),
                        "line": int(candidate.get("line", 1)),
                        "url": url,
                        "reason": (
                            "external JavaScript is forbidden by Template Core"
                            if not declared_mode
                            else "external JavaScript is not declared as an optional client-only dependency"
                        ),
                        "template_feedback": True,
                    }
                )
    return findings


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=".")
    parser.add_argument("--format", choices=("text", "json"), default="text")
    args = parser.parse_args(argv)
    root = Path(args.root).resolve()
    findings = scan(root)
    result = {
        "schema_version": "0.1",
        "policy": "external-javascript-forbidden",
        "status": "PASS" if not findings else "FAIL",
        "template_feedback_required": bool(findings),
        "findings": findings,
    }
    if args.format == "json":
        print(json.dumps(result, ensure_ascii=False, indent=2))
    elif findings:
        print("External JavaScript policy: FAIL")
        for item in findings:
            print(f"{item['file']}:{item['line']} {item.get('url', '')}: {item['reason']}")
        print("Template feedback: REQUIRED")
    else:
        print("External JavaScript policy: PASS")
    return 1 if findings else 0


if __name__ == "__main__":
    raise SystemExit(main())
