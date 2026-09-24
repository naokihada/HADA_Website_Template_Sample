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
from i18n_pipeline import master_files, parse_blocks, select_locale_content, snapshot_path, source_hash, translate_blocks  # noqa: E402
from assets import load_manifest, safe_relative, validate_assets  # noqa: E402
from display_config import display_runtime_settings  # noqa: E402
from external_javascript_policy import load_policy as load_external_javascript_policy, scan as scan_external_javascript  # noqa: E402
from gallery_contract import gallery_card_href, load_gallery_settings  # noqa: E402
from page_registry import build_html_masters  # noqa: E402
from media_library import build_media_library, inject_inline_media, page_media  # noqa: E402
from site_link_policy import load_policy as load_link_policy, scan as scan_site_links, site_url  # noqa: E402

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
    ui_profile: str = "shared-shell",
    locale: Optional[str] = None,
    link_policy: Optional[dict[str, Any]] = None,
    page_visuals: Optional[dict[str, Any]] = None,
) -> str:
    if markdown is None:
        raise RuntimeError(dependency_error_message())
    page_visuals = page_visuals or {"background": None, "header": "", "illustrations": {}}
    body = select_locale_content(body, str(locale or lang))
    rendered = markdown.markdown(body, extensions=["extra", "toc"] if page_visuals.get("illustrations") else ["extra"])
    rendered = inject_inline_media(rendered, page_visuals.get("illustrations", {}))
    if not title:
        heading = re.search(r"<h1[^>]*>(.*?)</h1>", rendered, re.DOTALL)
        title = re.sub(r"<[^>]+>", "", heading.group(1)).strip() if heading else "Page"
    active_locale = str(locale or ("jp" if lang.lower() in {"jp", "ja"} else lang))
    switch = ""
    if active_locale.lower() in {"jp", "ja"}:
        switch = (
            f'<p><a href="{html.escape(site_url("/index.html", link_policy), quote=True)}">Language</a> | '
            f'<a href="{html.escape(site_url("/en/index.html", link_policy), quote=True)}" hreflang="en">English</a></p>\n'
        )
    else:
        switch = (
            f'<p><a href="{html.escape(site_url("/index.html", link_policy), quote=True)}">Language</a> | '
            f'<a href="{html.escape(site_url("/jp/index.html", link_policy), quote=True)}" hreflang="ja">日本語</a></p>\n'
        )
    visual = ""
    visual_css = ""
    background_image = page_visuals.get("background") or background_image
    if background_image:
        background_url = background_image if str(background_image).startswith("/") else f"/assets/images/{background_image}"
        visual_css = (
            "  .background-fade{position:fixed;inset:0;z-index:-1;pointer-events:none;"
            "background-image:linear-gradient(135deg,transparent 0%,"
            "var(--site-fade-overlay) 55%,var(--site-fade-solid) 100%),"
            f"url('{html.escape(site_url(background_url, link_policy), quote=True)}');background-position:right top;"
            "background-repeat:no-repeat;background-size:cover;opacity:.72;}\n"
            "  @media (max-width: 700px){.background-fade{opacity:.32;background-size:72% auto;}}\n"
        )
        visual = '<div class="background-fade" aria-hidden="true"></div>\n'
    media_css = (
        "  .page-header-visual img{display:block;width:100%;height:auto;}"
        "  .page-illustration{max-width:min(40%,28rem);margin:1rem 0;}"
        "  .page-illustration.align-right{float:right;margin-left:1.5rem;}"
        "  .page-illustration.align-left{float:left;margin-right:1.5rem;}"
        "  .page-illustration img{display:block;width:100%;height:auto;}"
        "  .page-illustration figcaption{font-size:.9em;}\n"
    ) if page_visuals.get("header") or page_visuals.get("illustrations") else ""
    inline_styles = f"<style>\n{visual_css}{media_css}</style>\n" if visual_css or media_css else ""
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
    profile = ui_profile if ui_profile in {"shared-shell", "standalone", "pwa"} else "review_required"
    title = html.escape(str(title), quote=True)
    if profile == "shared-shell":
        shell_start = f'<header class="site-header" data-site-header><nav aria-label="Language navigation">{switch}</nav></header>\n<main class="site-main" data-site-main>'
        shell_end = '</main>\n<footer class="site-footer" data-site-footer><small>HADA Website Template</small></footer>\n'
    else:
        shell_start = f'<main class="site-main" data-site-main>\n{switch}'
        shell_end = '</main>\n'
    return (
        f"<!DOCTYPE html>\n<html lang=\"{lang}\">\n<head>\n"
        f"  <meta charset=\"UTF-8\">\n"
        f"  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1.0\">\n"
        f"  <link rel=\"stylesheet\" href=\"{html.escape(site_url('/assets/css/core.css', link_policy), quote=True)}\">\n"
        f"  <title>{title}</title>\n{inline_styles}</head>\n<body data-ui-profile=\"{profile}\" data-theme=\"light\" data-text-size=\"standard\" data-mode=\"standard\" data-display-persistence=\"{persistence}\" data-display-storage-key=\"{storage_key}\">\n"
        f"{visual}{shell_start}{controls if profile == 'shared-shell' else ''}{page_visuals.get('header', '')}{rendered}\n{shell_end}"
        f'<script src="{html.escape(site_url("/assets/js/display-preferences.js", link_policy), quote=True)}" defer></script>\n'
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


def build_master_pages(
    root: Path,
    provider: MockTranslationProvider,
    publication_override: Optional[Path] = None,
    link_policy: Optional[dict[str, Any]] = None,
) -> None:
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
            target_path.write_text(format_front_matter(metadata, body), encoding="utf-8", newline="\r\n")
            site_dir = output_root / locale
            site_dir.mkdir(parents=True, exist_ok=True)
            html_name = master_path.name[: -len("_master.md")] + ".html"
            site_dir.joinpath(html_name).write_text(
                markdown_to_html(
                    body,
                    locale,
                    background_image=background_visual(root, master_meta),
                    display_settings=display_settings,
                    ui_profile=str(master_meta.get("ui_profile", "shared-shell")),
                    locale=locale,
                    link_policy=link_policy,
                    page_visuals=page_media(root, str(master_meta.get("page_id", master_path.name.removesuffix("_master.md"))), locale),
                ),
                encoding="utf-8",
                newline="\r\n",
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
    gallery_settings = load_gallery_settings(root)
    link_policy = load_link_policy(root)
    if gallery_settings.get("enabled", True) is False:
        return
    entries = gallery_entries(root)
    for locale in locales:
        route = str(gallery_settings.get("route", "gallery")).strip("/") or "gallery"
        gallery_root = output / locale / route
        cards: list[str] = []
        for item in entries:
            image_id = str(item["image_id"])
            title = html.escape(localized(item.get("title"), locale, image_id))
            alt = html.escape(localized(item.get("alt"), locale, title))
            caption = html.escape(localized(item.get("caption"), locale, ""))
            thumbnail = Path(str(item["thumbnail"])).name
            card_href = html.escape(
                gallery_card_href(
                    gallery_settings,
                    image_id,
                    Path(str(item["web"])).name,
                    locale=locale,
                    link_policy=link_policy,
                ),
                quote=True,
            )
            cards.append(
                f'<figure><a href="{card_href}">'
                f'<img src="{html.escape(site_url(f"/assets/images/thumbnails/{thumbnail}", link_policy), quote=True)}" alt="{alt}" loading="lazy">'
                f'</a><figcaption><strong>{title}</strong><br>{caption}</figcaption></figure>'
            )
            detail = (
                "<!DOCTYPE html>\n<html lang=\"{lang}\"><head><meta charset=\"UTF-8\">"
                "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1.0\">"
                "<title>{title}</title><link rel=\"stylesheet\" href=\"{stylesheet}\"><style>body{{max-width:960px;margin:2rem auto;padding:0 1rem;"
                "font-family:system-ui,sans-serif}}img{{max-width:100%;height:auto}}"
                "a{{color:inherit}}</style></head><body data-ui-profile=\"standalone\"><p><a href=\"{back_href}\">"
                "{back}</a></p><main><h1>{title}</h1><img src=\"{web_href}\" alt=\"{alt}\">"
                "<p>{caption}</p>{credit}</main></body></html>\n"
            ).format(
                lang=html.escape(locale),
                title=title,
                back="Back to gallery" if locale != "jp" else "ギャラリーへ戻る",
                stylesheet=html.escape(site_url("/assets/css/core.css", link_policy), quote=True),
                back_href=html.escape(site_url(f"/{locale}/{route}/", link_policy), quote=True),
                web_href=html.escape(site_url(f"/assets/images/{Path(str(item['web'])).name}", link_policy), quote=True),
                alt=alt,
                caption=caption,
                credit=(f"<p>{html.escape(localized(item.get('credit'), locale, ''))}</p>" if item.get("credit") else ""),
            )
            write_generated_html(gallery_root / f"{image_id}.html", detail)
        title_value = localized((gallery_settings.get("title") or {}), locale, "Gallery")
        index = (
            "<!DOCTYPE html>\n<html lang=\"{lang}\"><head><meta charset=\"UTF-8\">"
            "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1.0\">"
            "<title>{title}</title><link rel=\"stylesheet\" href=\"{stylesheet}\"><style>body{{max-width:1100px;margin:2rem auto;padding:0 1rem;"
            "font-family:system-ui,sans-serif}}.gallery{{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:1rem}}"
            "figure{{margin:0}}img{{width:100%;aspect-ratio:1;object-fit:cover}}a{{color:inherit}}</style></head>"
            "<body data-ui-profile=\"standalone\"><p><a href=\"{home_href}\">{home}</a></p><main><h1>{title}</h1><div class=\"gallery\">{cards}</div>"
            "</main></body></html>\n"
        ).format(
            lang=html.escape(locale),
            title=html.escape(title_value),
            stylesheet=html.escape(site_url("/assets/css/core.css", link_policy), quote=True),
            home_href=html.escape(site_url(f"/{locale}/index.html", link_policy), quote=True),
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
    if candidate_root:
        publication_source = (root / publication).resolve()
        if output == publication_source or output.is_relative_to(publication_source) or publication_source.is_relative_to(output):
            raise ValueError('candidate root must be separate from publication root')
        if output.exists() and any(output.iterdir()):
            raise ValueError('candidate root must be empty before a safe build')
        output.mkdir(parents=True, exist_ok=True)
        if publication_source.is_dir():
            shutil.copytree(publication_source, output, dirs_exist_ok=True)
    link_policy = load_link_policy(root)
    build_master_pages(root, provider, publication_override=candidate_root, link_policy=link_policy)
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
            en_path.write_text(en_text, encoding="utf-8", newline="\r\n")

        _, current_en_body = parse_front_matter(en_text)
        site_jp.joinpath(html_basename(basename)).write_text(
            markdown_to_html(
                jp_body,
                "ja",
                background_image=background_visual(root, jp_meta),
                display_settings=display_settings,
                locale=MASTER_LOCALE,
                link_policy=link_policy,
                page_visuals=page_media(root, str(jp_meta.get("page_id", Path(basename).stem)), MASTER_LOCALE),
            ),
            encoding="utf-8",
        )
        site_en.joinpath(html_basename(basename)).write_text(
            markdown_to_html(
                current_en_body,
                "en",
                background_image=background_visual(root, jp_meta),
                display_settings=display_settings,
                ui_profile=str(jp_meta.get("ui_profile", "shared-shell")),
                locale=TARGET_LOCALE,
                link_policy=link_policy,
                page_visuals=page_media(root, str(jp_meta.get("page_id", Path(basename).stem)), TARGET_LOCALE),
            ),
            encoding="utf-8",
            newline="\r\n",
        )
    build_gallery(root, output, supported_locales)
    build_media_library(root, output, supported_locales)
    candidate_link_policy = dict(link_policy)
    candidate_link_policy["roots"] = ["."]
    violations = scan_site_links(output, candidate_link_policy)
    if violations:
        details = "; ".join(
            f"{item.get('file')}:{item.get('line')} {item.get('value')!r}: {item.get('reason')}"
            for item in violations
        )
        raise ValueError(f"Site link policy violation; template feedback required: {details}")
    javascript_policy = dict(load_external_javascript_policy(root))
    javascript_policy["roots"] = ["."]
    javascript_findings = scan_external_javascript(output, javascript_policy)
    if javascript_findings:
        details = "; ".join(
            f"{item.get('file')}:{item.get('line')} {item.get('url')!r}: {item.get('reason')}"
            for item in javascript_findings
        )
        raise ValueError(f"External JavaScript policy violation; template feedback required: {details}")


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
