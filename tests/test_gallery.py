#!/usr/bin/env python3
"""Regression tests for manifest-driven gallery generation."""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools" / "core"))
from build_site import build_gallery  # noqa: E402


class GalleryTests(unittest.TestCase):
    def test_generates_index_and_detail_without_exposing_master(self) -> None:
        import yaml

        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            (root / "config").mkdir()
            (root / "site").mkdir()
            (root / "assets/images/web").mkdir(parents=True)
            (root / "assets/images/thumbnails").mkdir(parents=True)
            (root / "assets/images/master").mkdir(parents=True)
            (root / "assets/metadata/images/hero").mkdir(parents=True)
            for path in (
                root / "assets/images/web/hero.jpg",
                root / "assets/images/thumbnails/hero.jpg",
            ):
                Image.new("RGB", (20, 20), "red").save(path, format="JPEG")
            (root / "assets/images/master/hero.png").write_bytes(b"master")
            (root / "assets/metadata/images/hero/PROVENANCE.yaml").write_text("image_id: hero\n", encoding="utf-8")
            manifest = {
                "schema_version": "0.1",
                "images": [{
                    "image_id": "hero",
                    "master": "assets/images/master/hero.png",
                    "web": "assets/images/web/hero.jpg",
                    "thumbnail": "assets/images/thumbnails/hero.jpg",
                    "usage": ["gallery"],
                    "status": "approved",
                }],
            }
            (root / "config/media.manifest.yaml").write_text(yaml.safe_dump(manifest), encoding="utf-8")
            build_gallery(root, root / "site", ["jp", "en"])
            index = (root / "site/jp/gallery/index.html").read_text(encoding="utf-8")
            detail = (root / "site/jp/gallery/hero.html").read_text(encoding="utf-8")
            self.assertIn("thumbnails/hero.jpg", index)
            self.assertIn("assets/images/hero.jpg", detail)
            self.assertNotIn("master/hero.png", detail)


if __name__ == "__main__":
    unittest.main()
