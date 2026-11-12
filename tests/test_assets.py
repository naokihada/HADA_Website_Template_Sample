#!/usr/bin/env python3
"""Regression tests for the reviewable image asset pipeline."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

from PIL import Image, PngImagePlugin

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools" / "core"))
import assets  # noqa: E402


class AssetPipelineTests(unittest.TestCase):
    def make_root(self) -> tuple[Path, tempfile.TemporaryDirectory[str]]:
        holder = tempfile.TemporaryDirectory()
        root = Path(holder.name)
        (root / "config").mkdir()
        (root / "AI/inbox/assets/generated").mkdir(parents=True)
        (root / "AI/inbox/assets/manual").mkdir(parents=True)
        return root, holder

    def make_png(self, path: Path) -> None:
        metadata = PngImagePlugin.PngInfo()
        metadata.add_text("provider_tracking_id", "must-not-reach-web")
        Image.new("RGBA", (32, 32), (180, 20, 20, 255)).save(path, pnginfo=metadata)

    def test_scan_and_approved_import_retains_png_and_creates_jpeg(self) -> None:
        root, holder = self.make_root()
        self.addCleanup(holder.cleanup)
        source = root / "AI/inbox/assets/generated/fixture-hero.png"
        self.make_png(source)
        plan = root / "AI/state/plan.json"
        self.assertEqual(assets.scan_inbox(root, plan), 0)
        self.assertEqual(assets.import_plan(root, plan, approve=True), 0)
        master = root / "assets/media/master/fixture-hero.png"
        web = root / "assets/media/web/fixture-hero.jpg"
        thumbnail = root / "assets/media/thumbnails/fixture-hero.jpg"
        self.assertTrue(master.is_file())
        self.assertTrue(web.is_file())
        self.assertTrue(thumbnail.is_file())
        self.assertEqual(web.suffix, ".jpg")
        with Image.open(web) as image:
            self.assertNotIn("provider_tracking_id", image.info)
            self.assertNotIn("comment", image.info)
        manifest = json.loads((root / "config/media.catalog.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["media"][0]["status"], "approved")
        record = manifest["media"][0]
        self.assertTrue(record["source"]["sha256"].startswith("sha256:"))
        self.assertTrue(record["public_sha256"].startswith("sha256:"))
        self.assertTrue(record["thumbnail_sha256"].startswith("sha256:"))
        self.assertNotIn("master_sha256", record)
        self.assertNotIn("web_sha256", record)
        self.assertEqual(assets.validate_assets(root), 0)
        provenance = root / "assets/metadata/media/fixture-hero/PROVENANCE.json"
        self.assertTrue(provenance.is_file())
        self.assertNotIn("AI", provenance.parts)
        self.assertIn("chatgpt_image", provenance.read_text(encoding="utf-8"))

    def test_new_image_id_preserves_previous_page_asset_for_revert(self) -> None:
        root, holder = self.make_root()
        self.addCleanup(holder.cleanup)
        first = root / "AI/inbox/assets/generated/page-background-001.png"
        second = root / "AI/inbox/assets/generated/page-background-002.png"
        self.make_png(first)
        self.make_png(second)
        plan = root / "AI/state/plan.json"
        assets.scan_inbox(root, plan)
        self.assertEqual(assets.import_plan(root, plan, approve=True), 0)
        manifest = json.loads((root / "config/media.catalog.json").read_text(encoding="utf-8"))
        ids = {item["media_id"] for item in manifest["media"]}
        self.assertEqual(ids, {"page-background-001", "page-background-002"})
        self.assertTrue((root / "assets/media/master/page-background-001.png").is_file())
        self.assertTrue((root / "assets/media/master/page-background-002.png").is_file())

    def test_generated_non_png_is_review_required_and_cannot_import(self) -> None:
        root, holder = self.make_root()
        self.addCleanup(holder.cleanup)
        source = root / "AI/inbox/assets/generated/invalid.jpg"
        Image.new("RGB", (8, 8), "white").save(source)
        plan = root / "AI/state/plan.json"
        assets.scan_inbox(root, plan)
        item = json.loads(plan.read_text(encoding="utf-8"))["items"][0]
        self.assertEqual(item["status"], "review_required")
        self.assertEqual(assets.import_plan(root, plan, approve=True), 1)

    def test_validate_rejects_master_hash_drift(self) -> None:
        root, holder = self.make_root()
        self.addCleanup(holder.cleanup)
        source = root / "AI/inbox/assets/generated/hero.png"
        self.make_png(source)
        plan = root / "AI/state/plan.json"
        assets.scan_inbox(root, plan)
        assets.import_plan(root, plan, approve=True)
        master = root / "assets/media/master/hero.png"
        master.write_bytes(master.read_bytes() + b"drift")
        self.assertEqual(assets.validate_assets(root), 1)

    def test_validate_requires_persistent_provenance_for_approved_asset(self) -> None:
        root, holder = self.make_root()
        self.addCleanup(holder.cleanup)
        source = root / "AI/inbox/assets/generated/hero.png"
        self.make_png(source)
        plan = root / "AI/state/plan.json"
        assets.scan_inbox(root, plan)
        assets.import_plan(root, plan, approve=True)
        (root / "assets/metadata/media/hero/PROVENANCE.json").unlink()
        self.assertEqual(assets.validate_assets(root), 1)

    def test_legacy_provenance_migration_preserves_source(self) -> None:
        root, holder = self.make_root()
        self.addCleanup(holder.cleanup)
        source = root / "AI/history/assets/hero/PROVENANCE.json"
        source.parent.mkdir(parents=True)
        source.write_text('{"image_id": "hero"}\n', encoding="utf-8")
        self.assertEqual(assets.migrate_legacy_provenance(root, apply=True), 0)
        self.assertTrue(source.is_file())
        self.assertTrue((root / "assets/metadata/media/hero/PROVENANCE.json").is_file())

    def test_validate_rejects_web_reference_to_master(self) -> None:
        root, holder = self.make_root()
        self.addCleanup(holder.cleanup)
        manifest = {"schema_version": "0.3", "media": [{"media_id": "hero-01", "type": "image", "source": {"file": "assets/media/master/hero.png", "visibility": "private"}, "public_file": "assets/media/master/hero.png", "status": "approved"}], "collections": [], "page_bindings": [], "processing": {}}
        (root / "config/media.catalog.json").write_text(json.dumps(manifest), encoding="utf-8")
        self.assertEqual(assets.validate_assets(root), 1)

    def test_domain_overlay_is_applied_to_web_only(self) -> None:
        root, holder = self.make_root()
        self.addCleanup(holder.cleanup)
        (root / "config").mkdir(exist_ok=True)
        (root / "config/image-generation.toml").write_text(
            '[web_overlay]\nenabled = true\ntype = "text_logo"\ntext_source = "domain"\ndomain = "www.hada.tv"\nposition = "bottom-left"\n',
            encoding="utf-8",
        )
        source = root / "AI/inbox/assets/generated/hero.png"
        self.make_png(source)
        plan = root / "AI/state/plan.json"
        assets.scan_inbox(root, plan)
        self.assertEqual(assets.import_plan(root, plan, approve=True), 0)
        master = root / "assets/media/master/hero.png"
        web = root / "assets/media/web/hero.jpg"
        with Image.open(master) as master_image, Image.open(web) as web_image:
            self.assertEqual(master_image.size, web_image.size)
            self.assertNotEqual(master_image.convert("RGB").tobytes(), web_image.convert("RGB").tobytes())
        manifest = json.loads((root / "config/media.catalog.json").read_text(encoding="utf-8"))
        self.assertTrue(manifest["media"][0].get("web_overlay_fingerprint"))

    def test_overlay_configuration_change_requires_sync(self) -> None:
        root, holder = self.make_root()
        self.addCleanup(holder.cleanup)
        (root / "config").mkdir(exist_ok=True)
        source = root / "AI/inbox/assets/generated/hero.png"
        self.make_png(source)
        plan = root / "AI/state/plan.json"
        assets.scan_inbox(root, plan)
        assets.import_plan(root, plan, approve=True)
        (root / "config/image-generation.toml").write_text(
            '[web_overlay]\nenabled = true\ntype = "text_logo"\ntext_source = "text"\ntext = "HADA.TV"\n',
            encoding="utf-8",
        )
        self.assertEqual(assets.sync_assets(root, apply=False), 1)
        self.assertEqual(assets.sync_assets(root, apply=True), 0)
        manifest = json.loads((root / "config/media.catalog.json").read_text(encoding="utf-8"))
        self.assertTrue(manifest["media"][0].get("web_overlay_fingerprint"))


if __name__ == "__main__":
    unittest.main()
