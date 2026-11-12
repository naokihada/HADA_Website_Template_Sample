"""Regression coverage for the v0.4 media catalog and static sequence pages."""

from __future__ import annotations

import sys
import json
import tempfile
import unittest
from pathlib import Path

from PIL import Image as PILImage
from pypdf import PdfReader, PdfWriter

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools" / "core"))

from media_library import build_media_library, build_spread_plan, effective_processing, fill_html_master_slots, page_media, valid_collection_route, validate_catalog  # noqa: E402
from build_site import markdown_to_html  # noqa: E402
from media_assets import _pdf_derivative, import_plan, scan_inbox, sync_media  # noqa: E402
import assets  # noqa: E402


class MediaLibraryTests(unittest.TestCase):
    def test_spread_plan_covers_each_page_once_and_keeps_earlier_rtl_page_right(self) -> None:
        for count in range(1, 9):
            for side in ("right", "left"):
                frames = build_spread_plan(count, side, "rtl")
                flattened = [page for frame in frames for page in (frame["right"], frame["left"]) if page is not None]
                self.assertEqual(flattened, list(range(count)), (count, side, frames))
                for frame in frames:
                    if frame["right"] is not None and frame["left"] is not None:
                        self.assertLess(frame["right"], frame["left"])
                self.assertEqual(frames[0][side], 0)
        left_first = build_spread_plan(5, "left", "rtl")
        self.assertEqual(left_first[0], {"right": None, "left": 0})
        self.assertEqual(left_first[1], {"right": 1, "left": 2})

    def test_spread_plan_mirrors_page_order_for_ltr(self) -> None:
        for side in ("left", "right"):
            frames = build_spread_plan(6, side, "ltr")
            flattened = [page for frame in frames for page in (frame["left"], frame["right"]) if page is not None]
            self.assertEqual(flattened, list(range(6)))
            for frame in frames:
                if frame["left"] is not None and frame["right"] is not None:
                    self.assertLess(frame["left"], frame["right"])

    def test_gallery_manga_mode_builds_both_no_javascript_opening_routes(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = self.make_root(Path(temp))
            catalog_path = root / "config/media.catalog.json"
            catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
            catalog["collections"].append({
                "collection_id": "manga", "route": "manga", "presentation": "gallery",
                "title": {"en": "Manga"}, "media_ids": ["page-00001", "page-00002", "page-00003"],
                "viewer": {"enabled": True, "modes": ["single", "manga"], "default_mode": "single"},
                "sequence": {"reading_direction": "rtl", "first_page_side": "right",
                             "first_page_side_options": ["right", "left"]},
            })
            catalog_path.write_text(json.dumps(catalog), encoding="utf-8", newline="\r\n")
            self.assertEqual(validate_catalog(root), [])
            output = root / "site"
            build_media_library(root, output, ["en", "jp"])
            index = (output / "en/media/manga/index.html").read_text(encoding="utf-8")
            self.assertEqual(index.count("<figure>"), 3)
            self.assertIn('data-viewer-modes="single,manga"', index)
            self.assertIn("/en/media/manga/manga/right/page-00001.html", index)
            self.assertIn("/en/media/manga/manga/left/page-00001.html", index)
            right_first = (output / "en/media/manga/manga/right/page-00001.html").read_text(encoding="utf-8")
            left_first = (output / "en/media/manga/manga/left/page-00001.html").read_text(encoding="utf-8")
            left_next = (output / "en/media/manga/manga/left/page-00002.html").read_text(encoding="utf-8")
            self.assertIn("00001.jpg", right_first)
            self.assertIn("00002.jpg", right_first)
            self.assertEqual(left_first.count("<figure"), 1)
            self.assertIn("00001.jpg", left_first)
            self.assertIn("00002.jpg", left_next)
            self.assertIn("00003.jpg", left_next)

    def test_open_on_load_manga_suppresses_gallery_and_side_route_trees(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = self.make_root(Path(temp))
            catalog_path = root / "config/media.catalog.json"
            catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
            catalog["collections"].append({
                "collection_id": "spoiler-free-manga", "route": "manga", "presentation": "gallery",
                "title": {"en": "Manga"}, "media_ids": ["page-00001", "page-00002", "page-00003"],
                "listing": {"enabled": False},
                "viewer": {"enabled": True, "modes": ["single", "manga"], "default_mode": "manga",
                           "mobile_default_mode": "single", "open_on_load": True},
                "sequence": {"reading_direction": "rtl", "first_page_side": "right",
                             "first_page_side_options": ["right", "left"]},
            })
            catalog_path.write_text(json.dumps(catalog), encoding="utf-8", newline="\r\n")
            output = root / "site"
            build_media_library(root, output, ["en", "jp"])
            index = (output / "en/media/manga/index.html").read_text(encoding="utf-8")
            self.assertIn('data-viewer-modes="single,manga"', index)
            self.assertIn('data-viewer-default-mode="manga"', index)
            self.assertIn('data-viewer-mobile-default-mode="single"', index)
            self.assertIn('data-viewer-open-on-load="true"', index)
            self.assertIn('data-viewer-reopen', index)
            self.assertIn('class="media-viewer__page-index" hidden', index)
            self.assertNotIn('<div class="items">', index)
            self.assertIn('/assets/media/web/00001.jpg', index)
            self.assertFalse((output / "en/media/manga/manga").exists())
            japanese = (output / "jp/media/manga/index.html").read_text(encoding="utf-8")
            self.assertIn('class="media-viewer__mode-label" data-viewer-mode="manga"', japanese)
            self.assertIn('data-viewer-action="previous" aria-label="戻る">戻る</button>', japanese)
            self.assertIn('data-viewer-action="next" aria-label="次へ">次へ</button>', japanese)
            viewer_css = (ROOT / "tools/core/media-viewer.css").read_text(encoding="utf-8")
            self.assertIn(".media-viewer__mode-label{min-height:0", viewer_css)

    def test_viewer_mode_contract_reserves_comic_and_validates_mobile_default(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = self.make_root(Path(temp))
            catalog_path = root / "config/media.catalog.json"
            catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
            catalog["collections"].append({
                "collection_id": "mode-contract", "route": "mode-contract", "presentation": "gallery",
                "title": {"en": "Mode contract"}, "media_ids": ["page-00001"],
                "viewer": {"enabled": True, "modes": ["comic"], "default_mode": "comic"},
            })
            catalog_path.write_text(json.dumps(catalog), encoding="utf-8", newline="\r\n")
            self.assertTrue(any("single/manga" in error for error in validate_catalog(root)))
            catalog["collections"][-1]["viewer"] = {
                "enabled": True, "modes": ["single", "manga"],
                "default_mode": "manga", "mobile_default_mode": "comic",
            }
            catalog_path.write_text(json.dumps(catalog), encoding="utf-8", newline="\r\n")
            self.assertTrue(any("viewer.mobile_default_mode" in error for error in validate_catalog(root)))
            catalog["collections"][-1]["viewer"]["mobile_default_mode"] = "single"
            catalog["collections"][-1]["sequence"] = {"reading_direction": "ltr"}
            catalog_path.write_text(json.dumps(catalog), encoding="utf-8", newline="\r\n")
            self.assertTrue(any("requires right-to-left reading" in error for error in validate_catalog(root)))

    def test_catalog_rejects_old_yaml_schema_and_parallel_image_list(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = self.make_root(Path(temp))
            catalog_path = root / "config/media.catalog.json"
            catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
            catalog["schema_version"] = "0.2"
            catalog_path.write_text(json.dumps(catalog), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "expected 0.3 JSON"):
                validate_catalog(root)
            catalog["schema_version"] = "0.3"
            catalog["images"] = []
            catalog_path.write_text(json.dumps(catalog), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "parallel images list"):
                validate_catalog(root)

    def test_duplicate_media_references_fail_validation(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = self.make_root(Path(temp))
            catalog_path = root / "config/media.catalog.json"
            catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
            catalog["collections"][0]["media_ids"] = ["page-00001", "page-00001"]
            catalog_path.write_text(json.dumps(catalog), encoding="utf-8")
            self.assertTrue(any("duplicate media_id in collection series" in error for error in validate_catalog(root)))

    def test_collection_routes_are_portable_output_paths(self) -> None:
        for route in ("library/series-a", "作品/第一巻"):
            self.assertTrue(valid_collection_route(route), route)
        for route in ("../outside", "CON/chapters", "series/part.", "bad:name", "bad\\route", "bad?query"):
            self.assertFalse(valid_collection_route(route), route)

    def test_collection_library_uses_first_image_as_cover_and_emits_sort_keys(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = self.make_root(Path(temp))
            catalog_path = root / "config/media.catalog.json"
            catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
            catalog["collections"] = [{
                "collection_id": "library", "route": "library", "presentation": "gallery",
                "title": {"en": "Library", "jp": "本棚"}, "listing": {"enabled": True},
                "children": [
                    {"collection_id": "zeta", "route": "library/zeta", "presentation": "gallery",
                     "title": {"en": "Zephyr"}, "media_ids": ["page-00001"],
                     "publication_date": "2022-04-03", "updated_date": "2024-01-02"},
                    {"collection_id": "alpha", "route": "library/alpha", "presentation": "gallery",
                     "title": {"en": "Amber"}, "media_ids": ["page-00002"],
                     "publication_date": "2024-02-01", "updated_date": "2023-03-01"},
                    {"collection_id": "beta", "route": "library/beta", "presentation": "gallery",
                     "title": {"en": "Beta"}, "media_ids": [], "children": [
                         {"collection_id": "beta-chapter", "route": "library/beta/chapter",
                          "presentation": "sequence", "media_ids": ["page-00003"]}]},
                ],
            }]
            catalog_path.write_text(json.dumps(catalog), encoding="utf-8")
            self.assertEqual(validate_catalog(root), [])
            output = root / "site"
            build_media_library(root, output, ["en"])
            page = (output / "en/media/library/index.html").read_text(encoding="utf-8")
            self.assertIn('src="/assets/media/thumbnails/00001.jpg"', page)
            self.assertIn('data-sort-publication-date="2022-04-03"', page)
            self.assertIn('data-sort-updated-date="2023-03-01"', page)
            self.assertIn('<option value="publication_date">Publication date</option>', page)
            self.assertIn('<option value="updated_date">Updated date</option>', page)
            self.assertIn('src="/assets/js/media-library.js"', page)
            self.assertIn("collection-library__cover", page.split('data-sort-name="Beta"', 1)[1].split("</li>", 1)[0])
            names = [page.index(f'data-sort-name="{name}"') for name in ("Amber", "Beta", "Zephyr")]
            self.assertEqual(names, sorted(names))

    def test_collection_dates_must_be_real_iso_calendar_dates(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = self.make_root(Path(temp))
            catalog_path = root / "config/media.catalog.json"
            catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
            catalog["collections"][0]["publication_date"] = "2026-02-30"
            catalog_path.write_text(json.dumps(catalog), encoding="utf-8")
            self.assertTrue(any("publication_date must be a valid YYYY-MM-DD date" in error
                                for error in validate_catalog(root)))

    def make_root(self, directory: Path) -> Path:
        (directory / "config").mkdir(parents=True)
        for rel in (
            "assets/media/web/00001.jpg",
            "assets/media/web/00002.jpg",
            "assets/media/web/00003.jpg",
            "assets/media/web/sample.mp4",
            "assets/media/web/menu.pdf",
            "assets/media/thumbnails/00001.jpg",
        ):
            path = directory / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b"test-media")
        media = [
            {"media_id": "page-00001", "type": "image", "public_file": "assets/media/web/00001.jpg", "thumbnail": "assets/media/thumbnails/00001.jpg", "source": {"file": "assets/media/master/secret.png", "visibility": "private"}, "title": {"en": "Page 1", "jp": "Page 1"}, "alt": {"en": "First page", "jp": "First page"}, "status": "approved"},
            {"media_id": "page-00002", "type": "image", "public_file": "assets/media/web/00002.jpg", "source": {"visibility": "private"}, "status": "approved"},
            {"media_id": "page-00003", "type": "image", "public_file": "assets/media/web/00003.jpg", "source": {"visibility": "private"}, "status": "approved"},
            {"media_id": "video-1", "type": "video", "public_file": "assets/media/web/sample.mp4", "thumbnail": "assets/media/thumbnails/00001.jpg", "source": {"visibility": "private"}, "status": "approved"},
            {"media_id": "pdf-1", "type": "document", "format": "pdf", "public_file": "assets/media/web/menu.pdf", "source": {"visibility": "private"}, "status": "approved"},
        ]
        collections = [{
            "collection_id": "series", "route": "library/series", "presentation": "sequence", "listing": {"enabled": True},
            "children": [{
                "collection_id": "volume", "route": "library/series/volume-01", "presentation": "sequence",
                "children": [{
                    "collection_id": "chapter", "route": "library/series/volume-01/chapter-01", "presentation": "sequence",
                    "listing": {"enabled": False}, "media_ids": ["page-00002", "page-00001", "page-00003"],
                    "sequence": {"order": "filename", "reading_direction": "rtl", "first_page_side": "right", "view": "spread", "spread_enabled": True, "labels": {"next": "Next", "previous": "Prev", "locales": {"jp": {"next": "Next", "previous": "Prev"}}}},
                }],
            }],
        }, {
            "collection_id": "gallery", "route": "gallery", "presentation": "gallery", "listing": {"enabled": True}, "media_ids": ["video-1", "pdf-1"],
        }]
        (directory / "config/media.catalog.json").write_text(json.dumps({"schema_version": "0.3", "media": media, "collections": collections, "processing": {"domain": "example.test"}}), encoding="utf-8", newline="\r\n")
        return directory

    def test_four_level_collections_render_spreads_and_keep_sources_private(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = self.make_root(Path(temp))
            (root / "config" / "display.toml").write_text(
                '[display.persistence]\nenabled = true\nstorage = "local_storage"\nkey = "test.display.v2"\n',
                encoding="utf-8", newline="\r\n")
            self.assertEqual(validate_catalog(root), [])
            output = root / "build"
            build_media_library(root, output, ["jp", "en"])
            page = (output / "jp/media/library/series/volume-01/chapter-01/page-00001.html").read_text(encoding="utf-8")
            next_page = (output / "jp/media/library/series/volume-01/chapter-01/page-00002.html").read_text(encoding="utf-8")
            series_index = (output / "en/media/library/series/index.html").read_text(encoding="utf-8")
            index = (output / "jp/media/library/series/volume-01/chapter-01/index.html").read_text(encoding="utf-8")
            self.assertIn("class=\"spread\"", page)
            self.assertIn('data-display-persistence="true"', page)
            self.assertIn('data-display-storage-key="test.display.v2"', page)
            self.assertIn('data-display-persistence="true"', index)
            self.assertIn('data-display-storage-key="test.display.v2"', index)
            self.assertIn('<main class="site-main" data-site-main dir="rtl">', page)
            self.assertIn("Next", page)
            self.assertIn("Prev", next_page)
            self.assertIn("コレクションを開く", index)
            self.assertIn("page-00001.html", index)
            self.assertIn('href="/en/media/library/series/volume-01/"', series_index)
            self.assertIn('data-sort-name="volume"', series_index)
            self.assertNotIn("assets/media/master/secret.png", page)
            self.assertTrue((output / "assets/media/web/00001.jpg").is_file())
            self.assertIn('<dialog class="media-viewer"', page)
            self.assertIn('data-viewer-position="1 / 3"', page)
            self.assertNotIn('data-viewer-action="zoom-in"', page)
            self.assertNotIn('data-viewer-action="zoom-out"', page)
            self.assertIn('class="media-protected-image" draggable="false"', page)
            self.assertIn('href="/assets/media/web/00001.jpg"', page)
            self.assertLess(page.index('id="media-item-00001"'), page.index('id="media-item-00002"'))
            self.assertIn('href="/jp/media/library/series/">series</a>', page)
            self.assertIn('href="/jp/media/library/series/volume-01/">volume</a>', page)
            self.assertTrue((output / "assets/js/media-viewer.js").is_file())
            self.assertTrue((output / "assets/css/media-viewer.css").is_file())

    def test_gallery_card_shows_one_thumbnail_and_sequence_labels_localize(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = self.make_root(Path(temp))
            manifest = root / "config/media.catalog.json"
            data = json.loads(manifest.read_text(encoding="utf-8"))
            data["collections"][1]["media_ids"] = ["page-00001", "page-00002"]
            manifest.write_text(json.dumps(data), encoding="utf-8")
            output = root / "build"
            build_media_library(root, output, ["jp", "en"])
            gallery = (output / "jp/media/gallery/index.html").read_text(encoding="utf-8")
            sequence = (output / "en/media/library/series/volume-01/chapter-01/page-00001.html").read_text(encoding="utf-8")
            self.assertEqual(gallery.count("<figure>"), 2)
            self.assertEqual(gallery.count('class="media-viewer-trigger"'), 2)
            self.assertNotIn('<img src="/assets/media/web/00001.jpg"', gallery)
            self.assertIn('src="/assets/media/thumbnails/00001.jpg"', gallery)
            self.assertIn("Next", (output / "jp/media/library/series/volume-01/chapter-01/page-00001.html").read_text(encoding="utf-8"))
            self.assertIn("Next", sequence)

    def test_image_deterrence_is_loaded_when_modal_viewer_is_disabled(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = self.make_root(Path(temp))
            manifest = root / "config/media.catalog.json"
            data = json.loads(manifest.read_text(encoding="utf-8"))
            data["collections"][0]["children"][0]["children"][0]["viewer"] = {"enabled": False}
            manifest.write_text(json.dumps(data), encoding="utf-8")
            output = root / "build"
            build_media_library(root, output, ["en"])
            page_path = output / "en/media/library/series/volume-01/chapter-01/page-00001.html"
            page = page_path.read_text(encoding="utf-8")
            self.assertNotIn('<dialog class="media-viewer"', page)
            self.assertNotIn("media-viewer.css", page)
            self.assertIn('src="/assets/js/media-viewer.js"', page)
            self.assertIn('class="media-protected-image" draggable="false"', page)

    def test_left_first_spread_and_ltr_are_collection_overrides(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = self.make_root(Path(temp))
            manifest = root / "config/media.catalog.json"
            data = json.loads(manifest.read_text(encoding="utf-8"))
            chapter = data["collections"][0]["children"][0]["children"][0]
            chapter["sequence"]["first_page_side"] = "left"
            chapter["sequence"]["reading_direction"] = "ltr"
            manifest.write_text(json.dumps(data), encoding="utf-8")
            output = root / "build"
            build_media_library(root, output, ["en"])
            page = (output / "en/media/library/series/volume-01/chapter-01/page-00001.html").read_text(encoding="utf-8")
            self.assertIn('<main class="site-main" data-site-main dir="ltr">', page)
            first_position = page.index("/assets/media/web/00001.jpg")
            second_position = page.index("/assets/media/web/00002.jpg")
            self.assertLess(first_position, second_position)

    def test_video_and_pdf_have_native_fallback_links(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = self.make_root(Path(temp))
            output = root / "build"
            build_media_library(root, output, ["en"])
            page = (output / "en/media/gallery/index.html").read_text(encoding="utf-8")
            self.assertIn("<video controls", page)
            self.assertIn("application/pdf", page)
            self.assertIn("Open or download PDF", page)

    def test_rejects_public_master_path_and_unsupported_audio_runtime(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = self.make_root(Path(temp))
            data = json.loads((root / "config/media.catalog.json").read_text(encoding="utf-8"))
            data["media"][0]["public_file"] = "assets/media/master/private.png"
            data["media"][1]["type"] = "audio"
            (root / "config/media.catalog.json").write_text(json.dumps(data), encoding="utf-8")
            errors = validate_catalog(root)
            self.assertTrue(any("private source/master" in item for item in errors))
            self.assertTrue(any("unsupported media type" in item for item in errors))

    def test_processing_policy_is_layered_and_metadata_removal_defaults_on(self) -> None:
        catalog = {"processing": {"defaults": {"metadata_strip": True, "embedded_signal_transform": False, "domain_mark": True}, "by_type": {"video": {"domain_mark": False}}}}
        video = {"type": "video", "processing": {"domain_mark": True}}
        collection = {"processing": {"metadata_strip": False}}
        self.assertEqual(effective_processing(catalog, video, collection), {"metadata_strip": False, "embedded_signal_transform": False, "domain_mark": True})
        image = effective_processing(catalog, {"type": "image"})
        self.assertTrue(image["metadata_strip"])
        self.assertTrue(image["domain_mark"])
        self.assertFalse(image["embedded_signal_transform"])

    def test_markdown_page_bindings_and_explicit_html_master_slots(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = self.make_root(Path(temp))
            manifest = root / "config/media.catalog.json"
            data = json.loads(manifest.read_text(encoding="utf-8"))
            data["page_bindings"] = [
                {"page_id": "about", "role": "page_header", "media_ids": ["page-00001"]},
                {"page_id": "about", "role": "background", "media_id": "page-00001"},
                {"page_id": "about", "role": "illustration", "heading_id": "preparation", "align": "left", "media_ids": ["page-00001", "page-00002"]},
            ]
            manifest.write_text(json.dumps(data), encoding="utf-8")
            visuals = page_media(root, "about", "jp")
            self.assertIn("page-header-visual", visuals["header"])
            self.assertEqual(visuals["background"], "/assets/media/web/00001.jpg")
            self.assertEqual(visuals["illustrations"]["preparation"].count("<figure"), 2)
            generated = markdown_to_html("# About\r\n\r\n## Preparation\r\n\r\nText.", "jp", page_visuals=visuals, locale="jp")
            self.assertIn("page-header-visual", generated)
            self.assertIn("align-left", generated)
            html_master = '<h1>About</h1><!-- HADA:MEDIA-SLOT page-header --><p>Master body</p>'
            updated = fill_html_master_slots(root, "about", "jp", html_master)
            self.assertIn("page-header-visual", updated)
            self.assertIn("Master body", updated)
            self.assertNotIn("HADA:MEDIA-SLOT page-header", updated)

    def test_generated_png_intake_keeps_private_master_and_creates_marked_jpeg(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            inbox = root / "AI/inbox/media/generated"
            inbox.mkdir(parents=True)
            source = inbox / "story-art.png"
            PILImage.new("RGB", (640, 640), (80, 120, 160)).save(source)
            config = root / "config"
            config.mkdir()
            (config / "media.catalog.json").write_text(json.dumps({
                "schema_version": "0.3", "media": [], "collections": [],
                "processing": {"domain": "sample.example", "defaults": {"metadata_strip": True, "embedded_signal_transform": False, "domain_mark": True}},
            }), encoding="utf-8")
            (config / "illustration-generation.example.toml").write_text('[provider]\ndefault = "chatgpt_image"\n\n[prompt_profile]\nname = "test"\ncommon_prompt = "Create a square illustration"\n', encoding="utf-8")
            plan = root / "AI/state/media-import-plan.json"
            scan_inbox(root, plan)
            self.assertEqual(import_plan(root, plan, approve=True), 0)
            master = root / "assets/media/master/story-art.png"
            public = root / "assets/media/web/story-art.jpg"
            thumb = root / "assets/media/thumbnails/story-art.jpg"
            self.assertTrue(master.is_file())
            self.assertTrue(public.is_file())
            self.assertTrue(thumb.is_file())
            self.assertEqual(master.read_bytes(), source.read_bytes())
            self.assertNotEqual(public.read_bytes(), source.read_bytes())
            record = json.loads((config / "media.catalog.json").read_text(encoding="utf-8"))["media"][0]
            self.assertEqual(record["source"]["visibility"], "private")
            self.assertTrue(record["source"]["sha256"].startswith("sha256:"))
            self.assertTrue(record["public_sha256"].startswith("sha256:"))
            self.assertTrue(record["thumbnail_sha256"].startswith("sha256:"))
            self.assertEqual(record["processing_result"], "stripped:new image derivative")
            self.assertEqual(assets.validate_assets(root), 0)
            self.assertEqual(record["provider"], "chatgpt_image")
            provenance = json.loads((root / "assets/metadata/media/story-art/PROVENANCE.json").read_text(encoding="utf-8"))
            self.assertIn("square illustration", provenance["prompt"])
            previous_derivative = public.read_bytes()
            PILImage.new("RGB", (640, 640), (180, 40, 80)).save(master)
            self.assertEqual(sync_media(root, apply=False), 1)
            self.assertEqual(public.read_bytes(), previous_derivative)
            self.assertEqual(sync_media(root, apply=True), 0)
            self.assertNotEqual(public.read_bytes(), previous_derivative)

    def test_recursive_image_set_intake_is_reviewable_additive_and_rename_safe(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            config = root / "config"
            config.mkdir()
            (config / "media.catalog.json").write_text(json.dumps({
                "schema_version": "0.3", "media": [], "collections": [],
                "processing": {"domain": "sample.example", "defaults": {
                    "metadata_strip": True, "embedded_signal_transform": False, "domain_mark": False}},
            }), encoding="utf-8")
            source_set = root / "AI/inbox/media/manual/Series A"
            (source_set / "chapter-1").mkdir(parents=True)
            PILImage.new("RGB", (16, 16), (20, 40, 60)).save(source_set / "00002.jpg")
            PILImage.new("RGB", (16, 16), (60, 40, 20)).save(source_set / "chapter-1/00001.png")
            plan_path = root / "AI/state/media-plan.json"

            scan_inbox(root, plan_path)
            plan = json.loads(plan_path.read_text(encoding="utf-8"))
            set_plan = plan["sets"][0]
            self.assertEqual(set_plan["set_id"], "series-a")
            self.assertEqual(set_plan["preview"]["image_count"], 2)
            self.assertEqual([item["position"] for item in set_plan["preview"]["ordered_items"]], [1, 2])
            self.assertIn("assets/media/web/series-a/00002.jpg", plan["items"][0]["planned_public"])
            set_plan["collection"]["title"]["en"] = "Series A — reviewed"
            set_plan["collection"]["route"] = "library/series-a"
            plan_path.write_text(json.dumps(plan, ensure_ascii=False), encoding="utf-8")

            import_plan(root, plan_path, approve=True)
            manifest_path = config / "media.catalog.json"
            imported = json.loads(manifest_path.read_text(encoding="utf-8"))
            self.assertEqual(len(imported["media"]), 2)
            self.assertEqual(imported["collections"][0]["route"], "library/series-a")
            self.assertEqual(imported["collections"][0]["title"]["en"], "Series A — reviewed")
            original_files = {item["media_id"]: (root / item["public_file"]).read_bytes() for item in imported["media"]}

            PILImage.new("RGB", (16, 16), (1, 2, 3)).save(source_set / "chapter-1/00003.webp")
            scan_inbox(root, plan_path)
            extension_plan = json.loads(plan_path.read_text(encoding="utf-8"))
            self.assertEqual(extension_plan["sets"][0]["action"], "extend")
            self.assertEqual(extension_plan["sets"][0]["collection"]["route"], "library/series-a")
            self.assertEqual(sum(item["status"] == "pending_approval" for item in extension_plan["items"]), 1)
            import_plan(root, plan_path, approve=True)
            imported = json.loads(manifest_path.read_text(encoding="utf-8"))
            self.assertEqual(len(imported["collections"]), 1)
            self.assertEqual(len(imported["media"]), 3)
            for item in imported["media"]:
                if item["media_id"] in original_files:
                    self.assertEqual((root / item["public_file"]).read_bytes(), original_files[item["media_id"]])

            renamed = source_set.with_name("Series A Renamed")
            source_set.rename(renamed)
            scan_inbox(root, plan_path)
            renamed_plan = json.loads(plan_path.read_text(encoding="utf-8"))
            self.assertEqual(renamed_plan["sets"][0]["set_id"], "series-a-renamed")
            self.assertEqual(renamed_plan["sets"][0]["action"], "create")
            import_plan(root, plan_path, approve=True)
            imported = json.loads(manifest_path.read_text(encoding="utf-8"))
            self.assertEqual({entry["collection_id"] for entry in imported["collections"]}, {"series-a", "series-a-renamed"})

    def test_image_set_id_collisions_are_review_required_and_import_preflight_is_safe(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            config = root / "config"
            config.mkdir()
            manifest = config / "media.catalog.json"
            manifest.write_text(json.dumps({"schema_version": "0.3", "media": [], "collections": [],
                                                "processing": {"domain": "sample.example"}}), encoding="utf-8")
            inbox = root / "AI/inbox/media/manual"
            for folder in ("My Set", "my-set"):
                target = inbox / folder
                target.mkdir(parents=True)
                PILImage.new("RGB", (8, 8)).save(target / "00001.jpg")
            plan_path = root / "AI/state/media-plan.json"
            scan_inbox(root, plan_path)
            plan = json.loads(plan_path.read_text(encoding="utf-8"))
            self.assertTrue(all(entry["status"] == "review_required" for entry in plan["sets"]))
            self.assertTrue(all(entry["status"] == "review_required" for entry in plan["items"]))
            original_manifest = manifest.read_bytes()
            self.assertEqual(import_plan(root, plan_path, approve=True), 0)
            self.assertEqual(json.loads(manifest.read_text(encoding="utf-8"))["media"], [])
            self.assertEqual(manifest.read_bytes(), original_manifest)
            self.assertFalse((root / "assets/media/master").exists())

    def test_invalid_image_in_set_fails_before_any_asset_or_manifest_change(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            config = root / "config"
            config.mkdir()
            manifest = config / "media.catalog.json"
            manifest.write_text(json.dumps({"schema_version": "0.3", "media": [], "collections": [],
                                                "processing": {"domain": "sample.example"}}), encoding="utf-8")
            original_manifest = manifest.read_bytes()
            source_set = root / "AI/inbox/media/manual/Invalid Set"
            source_set.mkdir(parents=True)
            PILImage.new("RGB", (8, 8)).save(source_set / "00001.jpg")
            (source_set / "00002.jpg").write_bytes(b"not an image")
            plan_path = root / "AI/state/media-plan.json"
            scan_inbox(root, plan_path)
            with self.assertRaisesRegex(ValueError, "cannot be decoded"):
                import_plan(root, plan_path, approve=True)
            self.assertEqual(manifest.read_bytes(), original_manifest)
            self.assertFalse((root / "assets/media/master").exists())
            self.assertFalse((root / "assets/media/web").exists())

    def test_pdf_metadata_stage_removes_document_info_when_supported(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / "source.pdf"
            target = root / "web.pdf"
            writer = PdfWriter()
            writer.add_blank_page(width=100, height=100)
            writer.add_metadata({"/Title": "Private title"})
            with source.open("wb") as handle:
                writer.write(handle)
            result = _pdf_derivative(source, target, True)
            self.assertIn("best_effort", result)
            self.assertTrue(target.is_file())
            self.assertNotEqual(PdfReader(str(target)).metadata.title, "Private title")


if __name__ == "__main__":
    unittest.main()
