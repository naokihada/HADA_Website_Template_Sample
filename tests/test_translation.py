#!/usr/bin/env python3
"""Tests for translation, term dictionary, and build_site — no external AI APIs."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

TOOLS_CORE = Path(__file__).resolve().parents[1] / "tools" / "core"
REPO_ROOT = Path(__file__).resolve().parents[1]
VALIDATOR = TOOLS_CORE / "validate_framework.py"
BUILD_SITE = TOOLS_CORE / "build_site.py"
FIXTURE_DICTIONARY = REPO_ROOT / "tests" / "fixtures" / "term_dictionary.yaml"

if str(TOOLS_CORE) not in sys.path:
    sys.path.insert(0, str(TOOLS_CORE))

from term_dictionary import load_term_dictionary  # noqa: E402
from translation_provider import MockTranslationProvider, translate_with_dictionary  # noqa: E402
from build_site import build_master_pages, markdown_to_html, parse_front_matter, should_preserve_en  # noqa: E402
from i18n_pipeline import parse_blocks, select_locale_content, source_hash  # noqa: E402


def run_validator(args: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(VALIDATOR), *args],
        cwd=str(cwd),
        capture_output=True,
        text=True,
        check=False,
    )


def run_build_site(cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(BUILD_SITE), "--root", str(cwd)],
        capture_output=True,
        text=True,
        check=False,
    )


def copy_minimal_project(target: Path) -> None:
    for rel in (
        "AGENTS.md",
        "README.md",
        ".gitignore",
        "config/project.yaml",
        "config/site.example.yaml",
        "config/term_dictionary.yaml",
        "environments/environments.example.yaml",
        "references/registry/references.example.yaml",
        "site/README.md",
        "site/index.html",
        "tests/fixtures/content/jp/index.md",
        "tests/fixtures/content/jp/about.md",
    ):
        src = REPO_ROOT / rel
        dst = target / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        if rel.startswith("tests/fixtures/content/jp/"):
            content_rel = rel.replace("tests/fixtures/content/", "content/")
            content_dst = target / content_rel
            content_dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, content_dst)
    for rel_dir in (
        "AI",
        "content/en",
        "content/jp",
        "site/en",
        "site/jp",
        "site/assets",
        "references/registry",
        "references/cache",
        "references/reports",
        "environments",
        "tools/core",
        "tools/plugins",
        "tests",
        "docs",
        "config",
    ):
        (target / rel_dir).mkdir(parents=True, exist_ok=True)


class TranslationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.entries = load_term_dictionary(FIXTURE_DICTIONARY)
        self.provider = MockTranslationProvider()

    def test_jp_to_en_translation(self) -> None:
        source = "サンプル文章です。"
        result = translate_with_dictionary(source, self.entries, self.provider)
        self.assertIn("[en]", result)

    def test_term_dictionary_hit(self) -> None:
        source = "佐藤花子"
        result = translate_with_dictionary(source, self.entries, self.provider)
        self.assertEqual(result, "Hanako Sato")

    def test_term_dictionary_miss_uses_provider(self) -> None:
        source = "通常の文章"
        result = translate_with_dictionary(source, self.entries, self.provider)
        self.assertEqual(result, "[en]通常の文章[/en]")

    def test_dictionary_precedence_over_mock(self) -> None:
        source = "株式会社サンプル製茶の佐藤花子です。"
        result = translate_with_dictionary(source, self.entries, self.provider)
        self.assertIn("Sample Tea Co.", result)
        self.assertIn("Hanako Sato", result)
        self.assertNotIn("株式会社サンプル製茶", result)
        self.assertNotIn("佐藤花子", result)

    def test_company_name_preserved(self) -> None:
        result = translate_with_dictionary("株式会社サンプル製茶", self.entries, self.provider)
        self.assertEqual(result, "Sample Tea Co.")

    def test_person_name_preserved(self) -> None:
        result = translate_with_dictionary("佐藤花子", self.entries, self.provider)
        self.assertEqual(result, "Hanako Sato")

    def test_markdown_to_html(self) -> None:
        html = markdown_to_html("# Title\n\nBody text.", "en", title="Title")
        self.assertIn("<h1", html)
        self.assertIn("Body text.", html)

    def test_page_visual_css_is_inside_a_style_element(self) -> None:
        html = markdown_to_html("# Title", "en", background_image="demo.jpg")
        self.assertIn("<style>\n  .background-fade{", html)
        self.assertIn("url('/assets/images/demo.jpg')", html)
        self.assertIn("</style>", html)

    def test_locale_wrappers_preserve_translated_heading_anchors(self) -> None:
        rendered = markdown_to_html(
            "[en]## Sample Artwork[/en]\n\n[de]## Beispielkunst[/de]",
            "en",
            locale="en",
            page_visuals={"background": None, "header": "", "illustrations": {"sample-artwork": '<figure><img src="/art.jpg" alt="art"></figure>'}},
        )
        self.assertIn('<h2 id="sample-artwork">Sample Artwork</h2>', rendered)
        self.assertIn('<figure><img src="/art.jpg" alt="art"></figure>', rendered)
        self.assertNotIn("Beispielkunst", rendered)

    def test_select_locale_content_keeps_unwrapped_content_and_active_language(self) -> None:
        selected = select_locale_content("[en]English[/en][de]Deutsch[/de]\nShared", "en")
        self.assertEqual(selected, "English\nShared")

    def test_build_site_basename_mapping(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            copy_minimal_project(root)
            result = run_build_site(root)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue((root / "content" / "en" / "about.md").is_file())
            self.assertTrue((root / "site" / "jp" / "about.html").is_file())
            self.assertTrue((root / "site" / "en" / "about.html").is_file())

    def test_existing_locale_validation(self) -> None:
        result = run_validator(["--root", str(REPO_ROOT), "--format", "json"], REPO_ROOT)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["status"], "PASS")

    def test_existing_counterpart_validation_passes(self) -> None:
        result = run_validator(["--root", str(REPO_ROOT), "--format", "json"], REPO_ROOT)
        payload = json.loads(result.stdout)
        i18n_warnings = [w for w in payload.get("warnings", []) if w["rule_id"].startswith("I18N-0") and w["rule_id"] != "I18N-004"]
        self.assertEqual(i18n_warnings, [])

    def test_en_only_proper_noun_not_invented_in_jp(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            copy_minimal_project(root)
            en_path = root / "content" / "en" / "about.md"
            en_path.write_text(
                "---\ntranslation_status: REVIEW_REQUIRED\nen_only_terms:\n  - John Smith\n---\n\nJohn Smith\n",
                encoding="utf-8",
            )
            jp_before = (root / "content" / "jp" / "about.md").read_text(encoding="utf-8")
            result = run_build_site(root)
            self.assertEqual(result.returncode, 0, result.stderr)
            jp_after = (root / "content" / "jp" / "about.md").read_text(encoding="utf-8")
            self.assertEqual(jp_before, jp_after)
            self.assertIn("John Smith", en_path.read_text(encoding="utf-8"))
            self.assertNotIn("John Smith", jp_after)

    def test_single_term_dictionary_file(self) -> None:
        config_dir = REPO_ROOT / "config"
        self.assertTrue((config_dir / "term_dictionary.yaml").is_file())
        extra = [
            p.name
            for p in config_dir.glob("term_dictionary*.yaml")
            if p.name not in ("term_dictionary.yaml", "term_dictionary.example.yaml")
        ]
        self.assertEqual(extra, [])

    def test_preserve_en_review_required(self) -> None:
        self.assertTrue(
            should_preserve_en({"translation_status": "REVIEW_REQUIRED", "en_only_terms": ["John Smith"]})
        )

    def test_master_pipeline_supports_three_locales_and_protected_blocks(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            copy_minimal_project(root)
            project = (root / "config" / "project.yaml").read_text(encoding="utf-8")
            project = project.replace("    - jp\n", "    - jp\n    - de\n", 1)
            (root / "config" / "project.yaml").write_text(project, encoding="utf-8")
            pages = root / "content" / "pages"
            pages.mkdir(parents=True, exist_ok=True)
            master = pages / "demo_master.md"
            master.write_text(
                "---\n"
                "title: Demo\n"
                "source_locale: mixed\n"
                "logical_page: demo\n"
                "---\n\n"
                "# サンプルページ\n\n"
                "<!-- i18n: no-translate -->\n"
                "HADA Website Template\n"
                "<!-- i18n: end -->\n\n"
                "```python i18n-comments\n"
                "# ビルド処理\n"
                "value = 'HADA'\n"
                "```\n",
                encoding="utf-8",
            )

            build_master_pages(root, self.provider)

            self.assertTrue((pages / "demo_JP.md").is_file())
            self.assertTrue((pages / "demo_EN.md").is_file())
            self.assertTrue((pages / "demo_DE.md").is_file())
            self.assertTrue((root / "site" / "de" / "demo.html").is_file())
            en = (pages / "demo_EN.md").read_text(encoding="utf-8")
            de = (pages / "demo_DE.md").read_text(encoding="utf-8")
            self.assertIn("HADA Website Template", en)
            self.assertIn("value = 'HADA'", de)
            self.assertIn("source_hash: " + source_hash(master.read_text(encoding="utf-8")), en)
            self.assertEqual(len(parse_blocks(master.read_text(encoding="utf-8"))), 4)

    def test_candidate_build_keeps_generated_snapshots_inside_candidate(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            copy_minimal_project(root)
            pages = root / "content" / "pages"
            pages.mkdir(parents=True, exist_ok=True)
            master = pages / "candidate_master.md"
            master.write_text(
                "---\n"
                "title: Candidate\n"
                "source_locale: mixed\n"
                "logical_page: candidate\n"
                "---\n\n"
                "# Candidate page\n\n"
                "Candidate output must stay isolated.\n",
                encoding="utf-8",
            )
            candidate = root / "candidate"
            candidate.mkdir()

            build_master_pages(root, self.provider, publication_override=candidate)

            self.assertTrue((candidate / ".generated/content/pages/candidate_JP.md").is_file())
            self.assertTrue((candidate / ".generated/content/pages/candidate_EN.md").is_file())
            self.assertFalse((root / "build/content/pages/candidate_JP.md").exists())
            self.assertFalse((pages / "candidate_EN.md").exists())


if __name__ == "__main__":
    unittest.main()
