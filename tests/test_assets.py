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
        source = root / "AI/inbox/assets/generated/restaurant-hero.png"
        self.make_png(source)
        plan = root / "AI/state/plan.json"
        self.assertEqual(assets.scan_inbox(root, plan), 0)
        self.assertEqual(assets.import_plan(root, plan, approve=True), 0)
        master = root / "assets/images/master/restaurant-hero.png"
        web = root / "assets/images/web/restaurant-hero.jpg"
        self.assertTrue(master.is_file())
        self.assertTrue(web.is_file())
        self.assertEqual(web.suffix, ".jpg")
        with Image.open(web) as image:
            self.assertNotIn("provider_tracking_id", image.info)
            self.assertNotIn("comment", image.info)
        manifest = assets.load_manifest(root)
        self.assertEqual(manifest["images"][0]["status"], "approved")

    def test_generated_non_png_is_review_required_and_cannot_import(self) -> None:
        root, holder = self.make_root()
        self.addCleanup(holder.cleanup)
        source = root / "AI/inbox/assets/generated/invalid.jpg"
        Image.new("RGB", (8, 8), "white").save(source)
        plan = root / "AI/state/plan.json"
        assets.scan_inbox(root, plan)
        item = json.loads(plan.read_text(encoding="utf-8"))["items"][0]
        self.assertEqual(item["status"], "review_required")
        self.assertEqual(assets.import_plan(root, plan, approve=True), 2)

    def test_validate_rejects_master_hash_drift(self) -> None:
        root, holder = self.make_root()
        self.addCleanup(holder.cleanup)
        source = root / "AI/inbox/assets/generated/hero.png"
        self.make_png(source)
        plan = root / "AI/state/plan.json"
        assets.scan_inbox(root, plan)
        assets.import_plan(root, plan, approve=True)
        master = root / "assets/images/master/hero.png"
        master.write_bytes(master.read_bytes() + b"drift")
        self.assertEqual(assets.validate_assets(root), 1)

    def test_validate_rejects_web_reference_to_master(self) -> None:
        root, holder = self.make_root()
        self.addCleanup(holder.cleanup)
        manifest = {"schema_version": "0.1", "images": [{"image_id": "hero-01", "master": "assets/images/master/hero.png", "web": "assets/images/master/hero.png", "status": "approved"}]}
        assets.write_manifest(root, manifest)
        self.assertEqual(assets.validate_assets(root), 1)


if __name__ == "__main__":
    unittest.main()
