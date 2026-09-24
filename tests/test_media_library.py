"""Regression coverage for the v0.4 media catalog and static sequence pages."""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

import yaml
from PIL import Image as PILImage
from pypdf import PdfReader, PdfWriter

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools" / "core"))

from media_library import build_media_library, effective_processing, fill_html_master_slots, migration_plan, page_media, validate_catalog  # noqa: E402
from build_site import markdown_to_html  # noqa: E402
from media_assets import _pdf_derivative, import_plan, scan_inbox, sync_media  # noqa: E402


class MediaLibraryTests(unittest.TestCase):
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
        (directory / "config/media.manifest.yaml").write_text(yaml.safe_dump({"schema_version": "0.2", "media": media, "collections": collections}, sort_keys=False), encoding="utf-8", newline="\r\n")
        return directory

    def test_four_level_collections_render_spreads_and_keep_sources_private(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = self.make_root(Path(temp))
            self.assertEqual(validate_catalog(root), [])
            output = root / "build"
            build_media_library(root, output, ["jp", "en"])
            page = (output / "jp/library/series/volume-01/chapter-01/page-00001.html").read_text(encoding="utf-8")
            next_page = (output / "jp/library/series/volume-01/chapter-01/page-00002.html").read_text(encoding="utf-8")
            series_index = (output / "en/library/series/index.html").read_text(encoding="utf-8")
            index = (output / "jp/library/series/volume-01/chapter-01/index.html").read_text(encoding="utf-8")
            self.assertIn("class=\"spread\"", page)
            self.assertIn('<main dir="rtl">', page)
            self.assertIn("Next", page)
            self.assertIn("Prev", next_page)
            self.assertIn("Open collection", index)
            self.assertIn("page-00001.html", index)
            self.assertIn('href="/en/library/series/volume-01/"', series_index)
            self.assertIn(">volume</a>", series_index)
            self.assertNotIn("assets/media/master/secret.png", page)
            self.assertTrue((output / "assets/media/web/00001.jpg").is_file())

    def test_left_first_spread_and_ltr_are_collection_overrides(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = self.make_root(Path(temp))
            manifest = root / "config/media.manifest.yaml"
            data = yaml.safe_load(manifest.read_text(encoding="utf-8"))
            chapter = data["collections"][0]["children"][0]["children"][0]
            chapter["sequence"]["first_page_side"] = "left"
            chapter["sequence"]["reading_direction"] = "ltr"
            manifest.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
            output = root / "build"
            build_media_library(root, output, ["en"])
            page = (output / "en/library/series/volume-01/chapter-01/page-00001.html").read_text(encoding="utf-8")
            self.assertIn('<main dir="ltr">', page)
            first_position = page.index("/assets/media/web/00001.jpg")
            second_position = page.index("/assets/media/web/00002.jpg")
            self.assertLess(first_position, second_position)

    def test_video_and_pdf_have_native_fallback_links(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = self.make_root(Path(temp))
            output = root / "build"
            build_media_library(root, output, ["en"])
            page = (output / "en/gallery/index.html").read_text(encoding="utf-8")
            self.assertIn("<video controls", page)
            self.assertIn("application/pdf", page)
            self.assertIn("Open or download PDF", page)

    def test_rejects_public_master_path_and_unsupported_audio_runtime(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = self.make_root(Path(temp))
            data = yaml.safe_load((root / "config/media.manifest.yaml").read_text(encoding="utf-8"))
            data["media"][0]["public_file"] = "assets/media/master/private.png"
            data["media"][1]["type"] = "audio"
            (root / "config/media.manifest.yaml").write_text(yaml.safe_dump(data), encoding="utf-8")
            errors = validate_catalog(root)
            self.assertTrue(any("private source/master" in item for item in errors))
            self.assertTrue(any("unsupported media type" in item for item in errors))

    def test_legacy_migration_is_additive_and_keeps_asset_ids(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "config").mkdir()
            old = {"schema_version": "0.1", "images": [{"image_id": "old-hero", "master": "assets/images/master/old.png", "web": "assets/images/web/old.jpg", "thumbnail": "assets/images/thumbnails/old.jpg", "status": "approved", "usage": ["gallery", "background_fade"]}]}
            (root / "config/media.manifest.yaml").write_text(yaml.safe_dump(old), encoding="utf-8")
            migrated = migration_plan(root)
            self.assertEqual(migrated["media"][0]["media_id"], "old-hero")
            self.assertEqual(migrated["media"][0]["source"]["visibility"], "private")
            self.assertIn("old-hero", migrated["collections"][0]["media_ids"])
            self.assertTrue((root / "config/media.manifest.yaml").is_file())

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
            manifest = root / "config/media.manifest.yaml"
            data = yaml.safe_load(manifest.read_text(encoding="utf-8"))
            data["page_bindings"] = [
                {"page_id": "about", "role": "page_header", "media_ids": ["page-00001"]},
                {"page_id": "about", "role": "background", "media_id": "page-00001"},
                {"page_id": "about", "role": "illustration", "heading_id": "preparation", "align": "left", "media_ids": ["page-00001", "page-00002"]},
            ]
            manifest.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
            visuals = page_media(root, "about", "jp")
            self.assertIn("page-header-visual", visuals["header"])
            self.assertEqual(visuals["background"], "/assets/media/web/00001.jpg")
            self.assertEqual(visuals["illustrations"]["preparation"].count("<figure"), 2)
            generated = markdown_to_html("# About\n\n## Preparation\n\nText.", "jp", page_visuals=visuals, locale="jp")
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
            (config / "media.manifest.yaml").write_text(yaml.safe_dump({
                "schema_version": "0.2", "media": [], "collections": [],
                "processing": {"domain": "sample.example", "defaults": {"metadata_strip": True, "embedded_signal_transform": False, "domain_mark": True}},
            }), encoding="utf-8")
            (config / "illustration-generation.example.yaml").write_text(yaml.safe_dump({
                "provider": {"default": "chatgpt_image"},
                "prompt_profile": {"name": "test", "common_prompt": "Create a square illustration"},
            }), encoding="utf-8")
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
            record = yaml.safe_load((config / "media.manifest.yaml").read_text(encoding="utf-8"))["media"][0]
            self.assertEqual(record["source"]["visibility"], "private")
            self.assertEqual(record["processing"]["metadata_result"], "stripped:new image derivative")
            self.assertEqual(record["provider"], "chatgpt_image")
            provenance = yaml.safe_load((root / "assets/metadata/media/story-art/PROVENANCE.yaml").read_text(encoding="utf-8"))
            self.assertIn("square illustration", provenance["prompt"])
            previous_derivative = public.read_bytes()
            PILImage.new("RGB", (640, 640), (180, 40, 80)).save(master)
            self.assertEqual(sync_media(root, apply=False), 1)
            self.assertEqual(public.read_bytes(), previous_derivative)
            self.assertEqual(sync_media(root, apply=True), 0)
            self.assertNotEqual(public.read_bytes(), previous_derivative)

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
