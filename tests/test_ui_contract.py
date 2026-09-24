#!/usr/bin/env python3
"""Unit tests for route profile discovery and configuration-driven UI contracts."""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools" / "core"))
from ui_contract import route_inventory  # noqa: E402


class UIContractTests(unittest.TestCase):
    def test_profile_is_discovered_from_generated_html(self) -> None:
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            (root / "config").mkdir()
            (root / "site/jp").mkdir(parents=True)
            (root / "config/project.yaml").write_text(
                "paths:\n  publication_root: site\n",
                encoding="utf-8",
            )
            (root / "site/jp/index.html").write_text(
                '<html><head><title>Home</title></head><body data-ui-profile="shared-shell"></body></html>',
                encoding="utf-8",
            )
            routes = route_inventory(root)
            self.assertEqual(routes[0]["profile"], "shared-shell")
            self.assertEqual(routes[0]["source"], "html")

    def test_registry_profile_overrides_html_profile(self) -> None:
        with tempfile.TemporaryDirectory() as name:
            import yaml

            root = Path(name)
            (root / "config").mkdir()
            (root / "site/jp").mkdir(parents=True)
            (root / "config/project.yaml").write_text(
                "paths:\n  publication_root: site\n  page_registry: config/page-registry.yaml\n",
                encoding="utf-8",
            )
            (root / "config/page-registry.yaml").write_text(yaml.safe_dump({
                "pages": [{
                    "page_id": "home",
                    "ui_profile": "standalone",
                    "locales": {"jp": {"path": "site/jp/index.html"}},
                }],
            }), encoding="utf-8")
            (root / "site/jp/index.html").write_text(
                '<html><head><title>Home</title></head><body data-ui-profile="shared-shell"></body></html>',
                encoding="utf-8",
            )
            routes = route_inventory(root)
            self.assertEqual(routes[0]["profile"], "standalone")
            self.assertEqual(routes[0]["source"], "registry")

    def test_undeclared_profile_is_review_required(self) -> None:
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            (root / "config").mkdir()
            (root / "site").mkdir()
            (root / "config/project.yaml").write_text("paths:\n  publication_root: site\n", encoding="utf-8")
            (root / "site/index.html").write_text("<html><title>Home</title><body></body></html>", encoding="utf-8")
            self.assertEqual(route_inventory(root)[0]["profile"], "review_required")


if __name__ == "__main__":
    unittest.main()
