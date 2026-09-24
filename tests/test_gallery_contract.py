#!/usr/bin/env python3
"""Tests for the generated gallery card link contract."""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools" / "core"))
from build_site import build_gallery  # noqa: E402
from gallery_contract import validate_gallery_settings  # noqa: E402


class GalleryContractTests(unittest.TestCase):
    def _root(self, settings: str) -> tuple[Path, tempfile.TemporaryDirectory[str]]:
        holder = tempfile.TemporaryDirectory()
        root = Path(holder.name)
        (root / "config").mkdir()
        (root / "site").mkdir()
        (root / "assets/images/web").mkdir(parents=True)
        (root / "assets/images/thumbnails").mkdir(parents=True)
        Image.new("RGB", (20, 20), "red").save(root / "assets/images/web/hero.jpg", format="JPEG")
        Image.new("RGB", (20, 20), "red").save(root / "assets/images/thumbnails/hero.jpg", format="JPEG")
        (root / "config/media.manifest.yaml").write_text(
            "schema_version: '0.1'\nimages:\n"
            "  - image_id: hero\n"
            "    web: assets/images/web/hero.jpg\n"
            "    thumbnail: assets/images/thumbnails/hero.jpg\n"
            "    usage: [gallery]\n"
            "    status: approved\n",
            encoding="utf-8",
        )
        (root / "config/gallery.yaml").write_text(settings, encoding="utf-8")
        return root, holder

    def test_default_gallery_cards_open_html_detail_pages(self) -> None:
        root, holder = self._root("gallery:\n  enabled: true\n")
        self.addCleanup(holder.cleanup)
        build_gallery(root, root / "site", ["en"])
        index = (root / "site/en/gallery/index.html").read_text(encoding="utf-8")
        self.assertIn('href="/en/gallery/hero.html"', index)
        self.assertIn('src="/assets/images/thumbnails/hero.jpg"', index)
        self.assertNotIn('href="/assets/images/hero.jpg"', index)

    def test_direct_image_links_require_explicit_opt_in(self) -> None:
        root, holder = self._root(
            "gallery:\n  enabled: true\n  card_link_type: direct_image\n  direct_image_links: true\n"
        )
        self.addCleanup(holder.cleanup)
        build_gallery(root, root / "site", ["en"])
        index = (root / "site/en/gallery/index.html").read_text(encoding="utf-8")
        self.assertIn('href="/assets/images/hero.jpg"', index)

    def test_inconsistent_direct_link_configuration_is_rejected(self) -> None:
        errors = validate_gallery_settings({"card_link_type": "html_detail", "direct_image_links": True})
        self.assertIn("direct_image_links must be false", errors[0])


if __name__ == "__main__":
    unittest.main()
