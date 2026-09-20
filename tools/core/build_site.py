#!/usr/bin/env python3
"""Build translated content and Markdown to HTML — initial release minimal pipeline."""

from __future__ import annotations

import argparse
import html
import re
import shutil
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
from i18n_pipeline import master_files, parse_blocks, snapshot_path, source_hash, translate_blocks  # noqa: E402
from assets import load_manifest, safe_relative, validate_assets  # noqa: E402
from display_config import display_runtime_settings  # noqa: E402
from page_registry import build_html_masters  # noqa: E402

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


def background_visual(root: Path, metadata: dict[str, Any]) -> Optional[str]:
    visual = metadata.get("visual") or {}
    fade = visual.get("background_fade") if isinstance(visual, dict) else None
    image_id = fade.get("image_id") if isinstance(fade, dict) else None
    if not isinstance(image_id, str):
        return None
    try:
        manifest = load_manifest(root)
    except (OSError, ValueError, RuntimeError):
        return None
    for item in manifest.get("images", []):
        if not isinstance(item, dict) or item.get("image_id") != image_id or item.get("status") != "approved":
            continue
        web = str(item.get("web", ""))
        if web.startswith("assets/images/web/"):
            return Path(web).name
    return None


def markdown_to_html(
    body: str,
    lang: str,
    title: Optional[str] = None,
    background_image: Optional[str] = None,
    display_settings: Optional[dict[str, Any]] = None,
) -> str:
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
    visual = ""
    visual_css = ""
    if background_image:
        visual_css = (
            "  .background-fade{position:fixed;inset:0;z-index:-1;pointer-events:none;"
            "background-image:linear-gradient(135deg,rgba(255,255,255,0) 0%,"
            "rgba(255,255,255,.72) 55%,rgba(255,255,255,1) 100%),"
            f"url('../assets/images/{background_image}');background-position:right top;"
            "background-repeat:no-repeat;background-size:cover;opacity:.72;}\n"
            "  @media (max-width: 700px){.background-fade{opacity:.32;background-size:72% auto;}}\n"
        )
        visual = '<div class="background-fade" aria-hidden="true"></div>\n'
    controls = (
        '<div class="display-controls" data-display-controls hidden aria-label="Display settings">'
        '<span>Theme:</span>'
        '<button type="button" data-set-theme="light" aria-pressed="true">Light</button>'
        '<button type="button" data-set-theme="dark" aria-pressed="false">Dark</button>'
        '<span>Text size:</span>'
        '<button type="button" data-set-text-size="standard" aria-pressed="true">Standard</button>'
        '<button type="button" data-set-text-size="large" aria-pressed="false">Large</button>'
        '<button type="button" data-set-text-size="xlarge" aria-pressed="false">Extra large</button>'
        '</div>\n'
    )
    display_settings = display_settings or {
        "persistence_enabled": True,
        "storage": "local_storage",
        "storage_key": "hada.display.v1",
    }
    persistence = "true" if display_settings.get("persistence_enabled") else "false"
    storage_key = html.escape(str(display_settings.get("storage_key", "hada.display.v1")), quote=True)
    return (
        f"<!DOCTYPE html>\n<html lang=\"{lang}\">\n<head>\n"
        f"  <meta charset=\"UTF-8\">\n"
        f"  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1.0\">\n"
        f"  <link rel=\"stylesheet\" href=\"../assets/css/core.css\">\n"
        f"  <title>{title}</title>\n{visual_css}</head>\n<body data-theme=\"light\" data-text-size=\"standard\" data-mode=\"standard\" data-display-persistence=\"{persistence}\" data-display-storage-key=\"{storage_key}\">\n"
        f"{visual}{switch}{controls}{rendered}\n"
        '<script src="../assets/js/display-preferences.js" defer></script>\n'
        "</body>\n</html>\n"
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


def build_master_pages(root: Path, provider: MockTranslationProvider, publication_override: Optional[Path] = None) -> None:
    """Build locale snapshots and minimal HTML from *_master.md sources."""
    if yaml is None or markdown is None:
        raise RuntimeError(dependency_error_message())

    project_path = root / "config" / "project.yaml"
    config = yaml.safe_load(project_path.read_text(encoding="utf-8")) if project_path.is_file() else {}
    locales_cfg = ((config or {}).get("locales") or {}).get("supported") or ["jp", "en"]
    locales = [str(locale) for locale in locales_cfg]
    publication = ((config or {}).get("paths") or {}).get("publication_root", "site")
    pages_root = root / "content" / "pages"
    if not pages_root.is_dir() or not master_files(root):
        return
    output_root = publication_override.resolve() if publication_override else (root / publication).resolve()
    if output_root == root.resolve() or not output_root.is_relative_to(root.resolve()):
        raise ValueError("Publication root must be inside the project")
    entries = load_term_dictionary(root / "config" / "term_dictionary.yaml")
    display_settings = display_runtime_settings(root)
    generated_snapshot_root = None
    if publication_override:
        # Keep candidate-only snapshots inside the isolated candidate tree.
        # Never write a candidate build back into the project's source tree.
        generated_snapshot_root = (publication_override / ".generated" / "content" / "pages").resolve()

    for master_path in master_files(root):
        master_text = master_path.read_text(encoding="utf-8")
        master_meta, master_body = parse_front_matter(master_text)
        digest = source_hash(master_text)

        def translate(text: str, target: str) -> str:
            return translate_with_dictionary(
                text,
                entries,
                provider,
                str(master_meta.get("source_locale", "mixed")),
                target,
            )

        for locale in locales:
            target_path = snapshot_path(master_path, locale)
            if generated_snapshot_root:
                target_path = generated_snapshot_root / target_path.name
            existing = target_path.read_text(encoding="utf-8") if target_path.is_file() else ""
            existing_meta, existing_body = parse_front_matter(existing) if existing else ({}, "")
            if locale.lower() in {"jp", "ja"}:
                body = master_body
                status = "SOURCE"
            elif existing_meta.get("source_hash") == digest and existing_body:
                body = existing_body
                status = existing_meta.get("translation_status", "REVIEWED")
            else:
                body = translate_blocks(parse_blocks(master_body), lambda value: translate(value, locale))
                status = "TRANSLATED"

            metadata = dict(master_meta)
            metadata.update(
                {
                    "source_file": str(master_path.relative_to(root)).replace("\\", "/"),
                    "source_hash": digest,
                    "source_locale": master_meta.get("source_locale", "mixed"),
                    "target_locale": locale.upper(),
                    "translation_status": status,
                }
            )
            target_path.parent.mkdir(parents=True, exist_ok=True)
            target_path.write_text(format_front_matter(metadata, body), encoding="utf-8")
            site_dir = output_root / locale
            site_dir.mkdir(parents=True, exist_ok=True)
            html_name = master_path.name[: -len("_master.md")] + ".html"
            site_dir.joinpath(html_name).write_text(
                markdown_to_html(
                    body,
                    locale,
                    background_image=background_visual(root, master_meta),
                    display_settings=display_settings,
                ),
                encoding="utf-8",
            )


def publish_web_assets(root: Path, output: Path) -> None:
    """Copy only approved JPEG derivatives into the configured publication root."""
    manifest_path = root / "config" / "media.manifest.yaml"
    if not manifest_path.is_file():
        return
    if validate_assets(root) != 0:
        raise ValueError("Image asset validation failed")
    manifest = load_manifest(root)
    for item in manifest.get("images", []):
        if not isinstance(item, dict) or item.get("status") != "approved":
            continue
        source = root / safe_relative(root, str(item.get("web", "")))
        if source.suffix.lower() != ".jpg" or not source.is_file():
            raise ValueError(f"Invalid approved web derivative: {item.get('image_id', '')}")
        target = output / "assets" / "images" / source.name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
        thumbnail = root / safe_relative(root, str(item.get("thumbnail", "")))
        if thumbnail.suffix.lower() != ".jpg" or not thumbnail.is_file():
            raise ValueError(f"Invalid approved thumbnail: {item.get('image_id', '')}")
        thumbnail_target = output / "assets" / "images" / "thumbnails" / thumbnail.name
        thumbnail_target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(thumbnail, thumbnail_target)


def localized(value: Any, locale: str, fallback: str = "") -> str:
    if isinstance(value, dict):
        return str(value.get(locale) or value.get("en") or value.get("jp") or next(iter(value.values()), fallback))
    return str(value) if value is not None else fallback


def gallery_entries(root: Path) -> list[dict[str, Any]]:
    manifest = load_manifest(root)
    entries: list[dict[str, Any]] = []
    for item in manifest.get("images", []):
        if not isinstance(item, dict) or item.get("status") != "approved":
            continue
        usage = item.get("usage", [])
        usages = {str(usage)} if isinstance(usage, str) else {str(value) for value in usage}
        gallery = item.get("gallery") or {}
        if "gallery" in usages or (isinstance(gallery, dict) and gallery.get("visible") is True):
            entries.append(item)
    return entries


def write_generated_html(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8", newline="\r\n")


def build_gallery(root: Path, output: Path, locales: list[str]) -> None:
    """Generate locale gallery indexes and details from approved media entries."""
    manifest_path = root / "config" / "media.manifest.yaml"
    if not manifest_path.is_file():
        return
    config_path = root / "config" / "gallery.yaml"
    gallery_config: dict[str, Any] = {}
    if config_path.is_file() and yaml is not None:
        loaded = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
        gallery_config = loaded if isinstance(loaded, dict) else {}
    gallery_settings = gallery_config.get("gallery") or {}
    if gallery_settings.get("enabled", True) is False:
        return
    entries = gallery_entries(root)
    for locale in locales:
        gallery_root = output / locale / str(gallery_settings.get("route", "gallery"))
        cards: list[str] = []
        for item in entries:
            image_id = str(item["image_id"])
            title = html.escape(localized(item.get("title"), locale, image_id))
            alt = html.escape(localized(item.get("alt"), locale, title))
            caption = html.escape(localized(item.get("caption"), locale, ""))
            thumbnail = Path(str(item["thumbnail"])).name
            cards.append(
                f'<figure><a href="./{html.escape(image_id)}.html">'
                f'<img src="../../assets/images/thumbnails/{html.escape(thumbnail)}" alt="{alt}" loading="lazy">'
                f'</a><figcaption><strong>{title}</strong><br>{caption}</figcaption></figure>'
            )
            detail = (
                "<!DOCTYPE html>\n<html lang=\"{lang}\"><head><meta charset=\"UTF-8\">"
                "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1.0\">"
                "<title>{title}</title><style>body{{max-width:960px;margin:2rem auto;padding:0 1rem;"
                "font-family:system-ui,sans-serif}}img{{max-width:100%;height:auto}}"
                "a{{color:inherit}}</style></head><body><p><a href=\"./index.html\">"
                "{back}</a></p><main><h1>{title}</h1><img src=\"../../assets/images/{web}\" alt=\"{alt}\">"
                "<p>{caption}</p>{credit}</main></body></html>\n"
            ).format(
                lang=html.escape(locale),
                title=title,
                back="Back to gallery" if locale != "jp" else "ギャラリーへ戻る",
                web=html.escape(Path(str(item["web"])).name),
                alt=alt,
                caption=caption,
                credit=(f"<p>{html.escape(localized(item.get('credit'), locale, ''))}</p>" if item.get("credit") else ""),
            )
            write_generated_html(gallery_root / f"{image_id}.html", detail)
        title_value = localized((gallery_settings.get("title") or {}), locale, "Gallery")
        index = (
            "<!DOCTYPE html>\n<html lang=\"{lang}\"><head><meta charset=\"UTF-8\">"
            "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1.0\">"
            "<title>{title}</title><style>body{{max-width:1100px;margin:2rem auto;padding:0 1rem;"
            "font-family:system-ui,sans-serif}}.gallery{{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:1rem}}"
            "figure{{margin:0}}img{{width:100%;aspect-ratio:1;object-fit:cover}}a{{color:inherit}}</style></head>"
            "<body><p><a href=\"../index.html\">{home}</a></p><main><h1>{title}</h1><div class=\"gallery\">{cards}</div>"
            "</main></body></html>\n"
        ).format(
            lang=html.escape(locale),
            title=html.escape(title_value),
            home="Home" if locale != "jp" else "ホーム",
            cards="\n".join(cards),
        )
        write_generated_html(gallery_root / "index.html", index)


def build_site(root: Path, provider: Optional[MockTranslationProvider] = None, candidate_root: Optional[Path] = None, mode: str = "build-content") -> None:
    if mode not in {"build-content", "build-html-master", "build-safe", "build-force"}:
        raise ValueError(f"Unsupported build mode: {mode}")
    if mode in {"build-safe", "build-force"} and candidate_root is None:
        raise ValueError(f"{mode} requires --candidate-root; publication is never written directly")
    if yaml is None or markdown is None:
        raise RuntimeError(dependency_error_message())

    provider = provider or MockTranslationProvider()
    display_settings = display_runtime_settings(root)
    build_master_pages(root, provider, publication_override=candidate_root)
    dictionary_path = root / "config" / "term_dictionary.yaml"
    entries = load_term_dictionary(dictionary_path)

    jp_dir = root / "content" / MASTER_LOCALE
    en_dir = root / "content" / TARGET_LOCALE
    config_path = root / 'config/project.yaml'
    config = yaml.safe_load(config_path.read_text(encoding='utf-8')) if config_path.exists() else {}
    publication = (config or {}).get('paths', {}).get('publication_root', 'site')
    from validate_framework import forbidden_segment
    if not isinstance(publication, str) or forbidden_segment(publication):
        raise ValueError('Unsafe publication root')
    output = candidate_root.resolve() if candidate_root else (root / publication).resolve()
    if output == root.resolve() or not output.is_relative_to(root.resolve()):
        raise ValueError('Publication root must be inside the project')
    publish_web_assets(root, output)
    site_jp = output / MASTER_LOCALE
    site_en = output / TARGET_LOCALE
    site_jp.mkdir(parents=True, exist_ok=True)
    site_en.mkdir(parents=True, exist_ok=True)
    build_html_masters(root, output)
    supported_locales = [str(value) for value in ((config or {}).get("locales") or {}).get("supported", ["jp", "en"])]

    for jp_path in sorted(jp_dir.glob("*.md")):
        basename = jp_path.name
        en_path = en_dir / basename
        jp_text = jp_path.read_text(encoding="utf-8")
        jp_meta, jp_body = parse_front_matter(jp_text)

        existing_en_meta: dict[str, Any] = {}
        if en_path.is_file():
            existing_en_meta, _ = parse_front_matter(en_path.read_text(encoding="utf-8"))

        if en_path.is_file():
            # Existing locale content is maintained content. Never regenerate
            # or overwrite it during a normal build; translate only when the
            # locale file is missing.
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
            markdown_to_html(
                jp_body,
                "ja",
                background_image=background_visual(root, jp_meta),
                display_settings=display_settings,
            ),
            encoding="utf-8",
        )
        site_en.joinpath(html_basename(basename)).write_text(
            markdown_to_html(
                current_en_body,
                "en",
                background_image=background_visual(root, jp_meta),
                display_settings=display_settings,
            ),
            encoding="utf-8",
        )
    build_gallery(root, output, supported_locales)


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Build translated content and HTML")
    parser.add_argument("--root", default=".", help="Repository root")
    parser.add_argument("--candidate-root", help="Clean candidate output directory; publication root is not written")
    parser.add_argument("--mode", choices=["build-content", "build-html-master", "build-safe", "build-force"], default="build-content")
    args = parser.parse_args(argv)

    if yaml is None or markdown is None:
        print(dependency_error_message(), file=sys.stderr)
        return 2

    root = Path(args.root).resolve()
    try:
        candidate = Path(args.candidate_root).resolve() if args.candidate_root else None
        build_site(root, candidate_root=candidate, mode=args.mode)
    except (OSError, ValueError, RuntimeError) as exc:
        print(str(exc), file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
