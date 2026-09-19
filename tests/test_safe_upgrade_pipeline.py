#!/usr/bin/env python3
"""Regression tests for HTML Master preservation and tree parity."""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools" / "core"))
from page_registry import build_html_masters  # noqa: E402
from tree_parity import compare  # noqa: E402


class SafeUpgradePipelineTests(unittest.TestCase):
    def test_html_master_preserves_existing_locale_and_marks_outdated(self) -> None:
        import yaml

        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            (root / "config").mkdir()
            (root / "content/pages").mkdir(parents=True)
            (root / "site/jp/about").mkdir(parents=True)
            (root / "site/en/about").mkdir(parents=True)
            (root / "build/candidate").mkdir(parents=True)
            (root / "config/project.yaml").write_text(
                "paths:\n  publication_root: site\n  generated_root: build\n  page_registry: config/page-registry.yaml\n", encoding="utf-8"
            )
            master = root / "content/pages/about.jp.html"
            master.write_text('<html lang="jp"><body>Master</body></html>\n', encoding="utf-8")
            (root / "site/jp/about/about.html").write_text("<html>JP</html>\n", encoding="utf-8")
            (root / "site/en/about/about.html").write_text("<html>Manual EN</html>\n", encoding="utf-8")
            registry = {
                "schema_version": "0.1",
                "pages": [{
                    "page_id": "about",
                    "source": {"type": "html", "master_locale": "jp", "master_path": "content/pages/about.jp.html", "source_hash": "old"},
                    "locales": {"jp": {"path": "site/jp/about/about.html"}, "en": {"path": "site/en/about/about.html"}},
                }],
            }
            (root / "config/page-registry.yaml").write_text(yaml.safe_dump(registry), encoding="utf-8")
            statuses = build_html_masters(root, root / "build/candidate")
            self.assertEqual((root / "site/en/about/about.html").read_text(encoding="utf-8"), "<html>Manual EN</html>\n")
            self.assertEqual((root / "build/candidate/en/about/about.html").read_text(encoding="utf-8"), "<html>Manual EN</html>\n")
            self.assertTrue(any(item["status"] == "OUTDATED" for item in statuses))
            self.assertTrue((root / "build/candidate/.build/page-status.json").is_file())

    def test_tree_parity_reports_changed_files(self) -> None:
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            expected, candidate = root / "expected", root / "candidate"
            expected.mkdir(); candidate.mkdir()
            (expected / "index.html").write_text("same", encoding="utf-8")
            (candidate / "index.html").write_text("changed", encoding="utf-8")
            result = compare(expected, candidate)
            self.assertEqual(result["status"], "REVIEW_REQUIRED")
            self.assertEqual(result["changed"], ["index.html"])


if __name__ == "__main__":
    unittest.main()
