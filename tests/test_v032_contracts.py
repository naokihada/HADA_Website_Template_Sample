from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools" / "core"))
from page_registry import classify_page  # noqa: E402
from site_audit import audit, compare  # noqa: E402
from site_contract import allows_absent_scaffold, resolve_site  # noqa: E402


class V032ContractTests(unittest.TestCase):
    def test_absent_scaffold_resolves_custom_root(self) -> None:
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            (root / "config").mkdir()
            (root / "config/project.yaml").write_text(
                "site:\n  publication_root: jp_co_hada_www\n  template_scaffold: absent\npaths:\n  content_master: content\n",
                encoding="utf-8",
            )
            self.assertEqual(resolve_site(root)["publication_root"], "jp_co_hada_www")
            self.assertTrue(allows_absent_scaffold(root))

    def test_registry_classifies_explicit_master_types(self) -> None:
        self.assertEqual(classify_page({"master": {"type": "html"}}), "html")
        self.assertEqual(classify_page({"master": {"type": "markdown"}}), "markdown")
        self.assertEqual(classify_page({"master": {"type": "unsupported"}}), "review_required")

    def test_html_audit_extracts_title_links_and_assets(self) -> None:
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            (root / "jp").mkdir()
            (root / "jp/index.html").write_text(
                '<html><head><title>Home</title></head><body><a href="/jp/about/">About</a><img src="/assets/a.jpg"></body></html>',
                encoding="utf-8",
            )
            result = audit(root)
            page = result["pages"]["jp/index.html"]
            self.assertEqual(page["title"], "Home")
            self.assertIn("/jp/about/", page["links"])
            self.assertIn("/assets/a.jpg", page["assets"])

    def test_html_audit_comparison_reports_changed_pages(self) -> None:
        before = {"pages": {"index.html": {"title": "Old"}}}
        after = {"pages": {"index.html": {"title": "New"}}}
        result = compare(before, after)
        self.assertEqual(result["status"], "REVIEW_REQUIRED")
        self.assertEqual(result["changed"], ["index.html"])

    def test_safe_mode_requires_candidate_root(self) -> None:
        repo = Path(__file__).resolve().parents[1]
        result = subprocess.run(
            [sys.executable, str(repo / "tools/core/build_site.py"), "--root", str(repo), "--mode", "build-safe"],
            capture_output=True, text=True,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("requires --candidate-root", result.stderr)


if __name__ == "__main__":
    unittest.main()
