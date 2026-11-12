"""Media routes use the shared site frame and same-tab work viewer."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools" / "core"))

from media_library import build_media_library  # noqa: E402


class SharedShellMediaRouteTests(unittest.TestCase):
    def test_configured_route_shared_shell_and_same_tab_viewer(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "config").mkdir()
            (root / "config/project.toml").write_text(
                '[paths]\nmedia_route = "portfolio/photos"\n', encoding="utf-8"
            )
            image = root / "assets/media/web/work.jpg"
            thumbnail = root / "assets/media/thumbnails/work.jpg"
            image.parent.mkdir(parents=True)
            thumbnail.parent.mkdir(parents=True)
            image.write_bytes(b"image")
            thumbnail.write_bytes(b"thumb")
            catalog = {
                "schema_version": "0.3",
                "media": [{
                    "media_id": "work-1", "type": "image", "public_file": "assets/media/web/work.jpg",
                    "thumbnail": "assets/media/thumbnails/work.jpg", "status": "approved",
                    "title": {"en": "Work", "jp": "作品"}, "alt": {"en": "A sample work", "jp": "作品の画像"},
                }],
                "collections": [{
                    "collection_id": "library", "route": "",
                    "title": {"en": "Media", "jp": "メディア"}, "presentation": "gallery",
                    "listing": {"enabled": True}, "media_ids": [], "children": [{
                        "collection_id": "album", "route": "album",
                        "title": {"en": "Album", "jp": "アルバム"}, "presentation": "gallery",
                        "listing": {"enabled": True}, "media_ids": ["work-1"],
                    }],
                }],
                "page_bindings": [], "processing": {},
            }
            (root / "config/media.catalog.json").write_text(json.dumps(catalog), encoding="utf-8")

            output = root / "site"
            build_media_library(root, output, ["en", "jp"])

            library = (output / "en/portfolio/photos/index.html").read_text(encoding="utf-8")
            album = (output / "en/portfolio/photos/album/index.html").read_text(encoding="utf-8")
            self.assertIn('data-ui-profile="shared-shell"', library)
            self.assertIn('data-site-header', library)
            self.assertIn('class="site-main"', library)
            self.assertIn('data-display-controls', library)
            self.assertIn('data-site-footer', library)
            self.assertIn('href="/assets/css/core.css"', library)
            self.assertIn('href="/jp/portfolio/photos/"', library)
            self.assertIn('href="/en/portfolio/photos/album/"', library)
            self.assertIn('data-ui-profile="shared-shell"', album)
            self.assertIn('class="media-viewer"', album)
            self.assertIn('href="/assets/media/web/work.jpg"', album)
            self.assertNotIn('target="_blank"', album)


if __name__ == "__main__":
    unittest.main()
