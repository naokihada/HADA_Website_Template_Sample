#!/usr/bin/env python3
"""Build translated content and Markdown to HTML — initial release minimal pipeline."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import Any, Optional, Tuple

try:
    import markdown
    import yaml
except ImportError:
    markdown = None  # type: ignore[assignment]
    yaml = None  # type: ignore[assignment]

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from term_dictionary import load_term_dictionary  # noqa: E402
from translation_provider import MockTranslationProvider, translate_with_dictionary  # noqa: E402

MASTER_LOCALE = "jp"
TARGET_LOCALE = "en"
TRANSLATION_STATUSES = {"NOT_TRANSLATED", "TRANSLATED", "REVIEW_REQUIRED", "OUTDATED"}
FRONT_MATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n?", re.DOTALL)


def dependency_error_message() -> str:
    missing = []
    if yaml is None:
        missing.append("PyYAML")
    if markdown is None:
        missing.append("markdown")
    return f"Missing dependencies: {', '.join(missing)}. Install with: pip install -r tools/core/requirements.txt"


def parse_front_matter(text: str) -> Tuple[dict[str, Any], str]:
    match = FRONT_MATTER_RE.match(text)
    if not match or yaml is None:
        return {}, text
    meta = yaml.safe_load(match.group(1)) or {}
    body = text[match.end() :]
    if not isinstance(meta, dict):
        meta = {}
    return meta, body


def format_front_matter(meta: dict[str, Any], body: str) -> str:
    if not meta:
        return body
    header = yaml.safe_dump(meta, allow_unicode=True, sort_keys=False).strip()
    return f"---\n{header}\n---\n\n{body.lstrip()}"


def markdown_to_html(body: str, lang: str, title: Optional[str] = None) -> str:
    if markdown is None:
        raise RuntimeError(dependency_error_message())
    rendered = markdown.markdown(body, extensions=["extra"])
    if not title:
        heading = re.search(r"<h1[^>]*>(.*?)</h1>", rendered, re.DOTALL)
        title = re.sub(r"<[^>]+>", "", heading.group(1)).strip() if heading else "Page"
    switch = ""
    if lang == "jp":
        switch = '<p><a href="../index.html">Language</a> | <a href="../en/index.html" hreflang="en">English</a></p>\n'
    else:
        switch = '<p><a href="../index.html">Language</a> | <a href="../jp/index.html" hreflang="ja">日本語</a></p>\n'
    return (
        f"<!DOCTYPE html>\n<html lang=\"{lang}\">\n<head>\n"
        f"  <meta charset=\"UTF-8\">\n"
        f"  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1.0\">\n"
        f"  <title>{title}</title>\n</head>\n<body>\n"
        f"{switch}{rendered}\n</body>\n</html>\n"
    )


def html_basename(md_name: str) -> str:
    return Path(md_name).with_suffix(".html").name


def should_preserve_en(existing_meta: dict[str, Any]) -> bool:
    if existing_meta.get("translation_status") == "REVIEW_REQUIRED":
        return True
    if existing_meta.get("en_only_terms"):
        return True
    return False


def translate_jp_file(
    jp_body: str,
    entries: list,
    provider: MockTranslationProvider,
) -> str:
    lines = jp_body.splitlines()
    translated_lines = [
        translate_with_dictionary(line, entries, provider, MASTER_LOCALE, TARGET_LOCALE) if line.strip() else line
        for line in lines
    ]
    trailing_newline = "\n" if jp_body.endswith("\n") else ""
    return "\n".join(translated_lines) + trailing_newline


def build_site(root: Path, provider: Optional[MockTranslationProvider] = None) -> None:
    if yaml is None or markdown is None:
        raise RuntimeError(dependency_error_message())

    provider = provider or MockTranslationProvider()
    dictionary_path = root / "config" / "term_dictionary.yaml"
    entries = load_term_dictionary(dictionary_path)

    jp_dir = root / "content" / MASTER_LOCALE
    en_dir = root / "content" / TARGET_LOCALE
    site_jp = root / "site" / MASTER_LOCALE
    site_en = root / "site" / TARGET_LOCALE
    site_jp.mkdir(parents=True, exist_ok=True)
    site_en.mkdir(parents=True, exist_ok=True)

    for jp_path in sorted(jp_dir.glob("*.md")):
        basename = jp_path.name
        en_path = en_dir / basename
        jp_text = jp_path.read_text(encoding="utf-8")
        jp_meta, jp_body = parse_front_matter(jp_text)

        existing_en_meta: dict[str, Any] = {}
        if en_path.is_file():
            existing_en_meta, _ = parse_front_matter(en_path.read_text(encoding="utf-8"))

        if should_preserve_en(existing_en_meta):
            en_text = en_path.read_text(encoding="utf-8")
        else:
            translated_body = translate_jp_file(jp_body, entries, provider)
            en_meta = {
                "translation_status": "TRANSLATED",
                "source_locale": MASTER_LOCALE,
                "target_locale": TARGET_LOCALE,
                "source_file": f"content/{MASTER_LOCALE}/{basename}",
            }
            en_text = format_front_matter(en_meta, translated_body)
            en_path.write_text(en_text, encoding="utf-8")

        _, current_en_body = parse_front_matter(en_text)
        site_jp.joinpath(html_basename(basename)).write_text(
            markdown_to_html(jp_body, "ja"),
            encoding="utf-8",
        )
        site_en.joinpath(html_basename(basename)).write_text(
            markdown_to_html(current_en_body, "en"),
            encoding="utf-8",
        )


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Build translated content and HTML")
    parser.add_argument("--root", default=".", help="Repository root")
    args = parser.parse_args(argv)

    if yaml is None or markdown is None:
        print(dependency_error_message(), file=sys.stderr)
        return 2

    root = Path(args.root).resolve()
    try:
        build_site(root)
    except (OSError, ValueError, RuntimeError) as exc:
        print(str(exc), file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
