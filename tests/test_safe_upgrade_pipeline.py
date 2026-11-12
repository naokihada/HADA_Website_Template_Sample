#!/usr/bin/env python3
"""Regression tests for HTML Master preservation and tree parity."""

from __future__ import annotations

import sys
import tempfile
import unittest
import json
import os
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools" / "core"))
from page_registry import build_html_masters  # noqa: E402
from tree_parity import compare, main as tree_parity_main  # noqa: E402


class SafeUpgradePipelineTests(unittest.TestCase):
    def test_html_master_preserves_existing_locale_and_marks_outdated(self) -> None:

        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            (root / "config").mkdir()
            (root / "content/pages").mkdir(parents=True)
            (root / "site/jp/about").mkdir(parents=True)
            (root / "site/en/about").mkdir(parents=True)
            (root / "build/candidate").mkdir(parents=True)
            (root / "config/project.toml").write_text(
                "[paths]\npublication_root = \"site\"\ngenerated_root = \"build\"\npage_registry = \"config/page-registry.json\"\n", encoding="utf-8"
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
            (root / "config/page-registry.json").write_text(json.dumps(registry), encoding="utf-8")
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

    def test_tree_parity_cli_is_read_only_without_report_path(self) -> None:
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            expected, candidate, working = root / "expected", root / "candidate", root / "working"
            expected.mkdir(); candidate.mkdir(); working.mkdir()
            (expected / "index.html").write_text("same", encoding="utf-8")
            (candidate / "index.html").write_text("same", encoding="utf-8")
            previous = Path.cwd()
            try:
                os.chdir(working)
                with redirect_stdout(StringIO()):
                    self.assertEqual(tree_parity_main([str(expected), str(candidate)]), 0)
            finally:
                os.chdir(previous)
            self.assertFalse((working / "tree-parity.json").exists())

    def test_tree_parity_cli_writes_only_explicit_report_path(self) -> None:
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            expected, candidate = root / "expected", root / "candidate"
            expected.mkdir(); candidate.mkdir()
            (expected / "index.html").write_text("old", encoding="utf-8")
            (candidate / "index.html").write_text("new", encoding="utf-8")
            report = root / "chosen-report.json"
            with redirect_stdout(StringIO()):
                self.assertEqual(tree_parity_main([str(expected), str(candidate), "--report", str(report)]), 1)
            self.assertEqual(json.loads(report.read_text(encoding="utf-8"))["status"], "REVIEW_REQUIRED")


if __name__ == "__main__":
    unittest.main()
