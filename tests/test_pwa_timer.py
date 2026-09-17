#!/usr/bin/env python3
"""Static contract checks for the PWA Timer install experience."""

import json
import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TIMER = ROOT / "site" / "timer.html"
SCRIPT = ROOT / "site" / "assets" / "timer.js"
MANIFEST = ROOT / "site" / "manifest.webmanifest"


class PwaTimerContractTests(unittest.TestCase):
    def test_install_button_is_hidden_and_labeled(self):
        html = TIMER.read_text(encoding="utf-8")
        self.assertRegex(html, r'<button[^>]+data-action="install"[^>]+hidden[^>]*>Install this timer</button>')

    def test_accessible_install_help_exists(self):
        html = TIMER.read_text(encoding="utf-8")
        self.assertIn('data-install-help role="status" aria-live="polite" hidden', html)

    def test_install_prompt_lifecycle_is_wired(self):
        script = SCRIPT.read_text(encoding="utf-8")
        for marker in ("beforeinstallprompt", ".prompt()", "appinstalled", "display-mode: standalone"):
            self.assertIn(marker, script)

    def test_manifest_declares_required_icons(self):
        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        icons = {icon["sizes"]: icon for icon in manifest["icons"]}
        self.assertIn("192x192", icons)
        self.assertIn("512x512", icons)
        for icon in icons.values():
            self.assertEqual(icon["type"], "image/png")
            self.assertTrue((ROOT / "site" / icon["src"][2:]).is_file())

    def test_unsupported_browser_copy_covers_apple_and_other(self):
        script = SCRIPT.read_text(encoding="utf-8")
        self.assertIn("Safari Share", script)
        self.assertIn("browser menu", script)


if __name__ == "__main__":
    unittest.main()
