from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools" / "core"))
from build_site import markdown_to_html  # noqa: E402
from display_config import validate_display  # noqa: E402
from external_dependency_scan import scan  # noqa: E402


ROOT = Path(__file__).resolve().parents[1]


class DisplayTests(unittest.TestCase):
    def test_generated_html_has_local_optional_display_controls(self) -> None:
        html = markdown_to_html("# Title\n\nReadable body.", "en", title="Title")
        self.assertIn('data-theme="light"', html)
        self.assertIn('data-text-size="standard"', html)
        self.assertIn('data-mode="standard"', html)
        self.assertIn("../assets/css/core.css", html)
        self.assertIn("../assets/js/display-preferences.js", html)
        self.assertIn("Readable body.", html)

    def test_core_display_assets_have_no_external_dependency(self) -> None:
        css = (ROOT / "site/assets/css/core.css").read_text(encoding="utf-8")
        script = (ROOT / "site/assets/js/display-preferences.js").read_text(encoding="utf-8")
        self.assertNotIn("http://", css + script)
        self.assertNotIn("https://", css + script)
        self.assertIn("prefers-reduced-motion", css)
        self.assertIn("prefers-color-scheme", script)
        self.assertIn("prefers-color-scheme", css)

    def test_display_config_rejects_external_or_required_javascript(self) -> None:
        errors = validate_display({"javascript": {"external": True, "required_for_content": True}})
        self.assertEqual(len(errors), 2)

    def test_external_dependency_scan_passes_publication_root(self) -> None:
        self.assertEqual(scan(ROOT / "site"), [])


if __name__ == "__main__":
    unittest.main()
