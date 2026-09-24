from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools" / "core"))
from build_site import markdown_to_html  # noqa: E402
from display_config import display_runtime_settings, validate_display  # noqa: E402
from external_dependency_scan import scan  # noqa: E402


ROOT = Path(__file__).resolve().parents[1]


class DisplayTests(unittest.TestCase):
    def test_generated_html_has_local_optional_display_controls(self) -> None:
        html = markdown_to_html("# Title\n\nReadable body.", "en", title="Title")
        self.assertIn('data-theme="light"', html)
        self.assertIn('data-text-size="standard"', html)
        self.assertIn('data-mode="standard"', html)
        self.assertIn('data-display-persistence="true"', html)
        self.assertIn('data-display-storage-key="hada.display.v1"', html)
        self.assertIn("/assets/css/core.css", html)
        self.assertIn("/assets/js/display-preferences.js", html)
        self.assertIn("Readable body.", html)

    def test_core_display_assets_have_no_external_dependency(self) -> None:
        css = (ROOT / "site/assets/css/core.css").read_text(encoding="utf-8")
        script = (ROOT / "site/assets/js/display-preferences.js").read_text(encoding="utf-8")
        self.assertNotIn("http://", css + script)
        self.assertNotIn("https://", css + script)
        self.assertIn("prefers-reduced-motion", css)
        self.assertIn("prefers-color-scheme", script)
        self.assertIn("prefers-color-scheme", css)

    def test_display_state_persistence_contract(self) -> None:
        settings = display_runtime_settings(ROOT)
        self.assertTrue(settings["persistence_enabled"])
        self.assertEqual(settings["storage"], "local_storage")
        self.assertEqual(settings["storage_key"], "hada.display.v1")
        script = (ROOT / "site/assets/js/display-preferences.js").read_text(encoding="utf-8")
        self.assertIn("localStorage", script)
        self.assertIn("schema_version", script)
        self.assertIn("try", script)

    def test_display_config_rejects_external_or_required_javascript(self) -> None:
        errors = validate_display({"javascript": {"external": True, "required_for_content": True}})
        self.assertEqual(len(errors), 2)

    def test_display_config_rejects_unsafe_persistence(self) -> None:
        errors = validate_display({"display": {"persistence": {"enabled": True, "storage": "remote"}}})
        self.assertIn("display.persistence.storage must be none or local_storage", errors)
        self.assertIn("display.persistence.enabled requires local_storage", errors)

    def test_accessibility_policy_preserves_background_and_requires_foreground_first(self) -> None:
        errors = validate_display(
            {
                "display": {
                    "accessibility": {
                        "preserve_background_treatment": True,
                        "minimum_font_size": "1rem",
                        "foreground_adjustment_order": ["color", "font_weight", "font_size", "font_family"],
                    }
                }
            }
        )
        self.assertEqual(errors, [])

    def test_external_dependency_scan_passes_publication_root(self) -> None:
        self.assertEqual(scan(ROOT / "site"), [])


if __name__ == "__main__":
    unittest.main()
