#!/usr/bin/env python3
"""Regression tests for safe candidate promotion and ownership preservation."""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools" / "core"))
from promote_build import run  # noqa: E402


class PromoteBuildTests(unittest.TestCase):
    def test_template_updates_apply_and_user_files_are_preserved(self) -> None:
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            (root / "config").mkdir()
            (root / "site/assets/css").mkdir(parents=True)
            (root / "build/assets/css").mkdir(parents=True)
            (root / "site/assets/images").mkdir(parents=True)
            (root / "build/assets/images").mkdir(parents=True)
            (root / "config/project.yaml").write_text(
                "paths:\n  publication_root: site\n  generated_root: build\n",
                encoding="utf-8",
            )
            (root / "config/template.manifest.yaml").write_text(
                "ownership:\n  template:\n    - site/assets/css/core.css\n  generated:\n    - site/en/**\n  user:\n    - site/assets/images/**\n",
                encoding="utf-8",
            )
            (root / "site/assets/css/core.css").write_text("old", encoding="utf-8")
            (root / "build/assets/css/core.css").write_text("new", encoding="utf-8")
            (root / "site/assets/images/user.jpg").write_bytes(b"old-user")
            (root / "build/assets/images/user.jpg").write_bytes(b"new-user")
            plan = run(root)
            self.assertEqual(plan["status"], "PASS")
            self.assertEqual([item["path"] for item in plan["safe_updates"]], ["assets/css/core.css"])
            run(root, apply=True)
            self.assertEqual((root / "site/assets/css/core.css").read_text(encoding="utf-8"), "new")
            self.assertEqual((root / "site/assets/images/user.jpg").read_bytes(), b"old-user")

    def test_unknown_changed_file_requires_review(self) -> None:
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            (root / "config").mkdir()
            (root / "site").mkdir()
            (root / "build").mkdir()
            (root / "config/project.yaml").write_text("paths:\n  publication_root: site\n  generated_root: build\n", encoding="utf-8")
            (root / "config/template.manifest.yaml").write_text("ownership: {}\n", encoding="utf-8")
            (root / "site/unknown.html").write_text("old", encoding="utf-8")
            (root / "build/unknown.html").write_text("new", encoding="utf-8")
            plan = run(root)
            self.assertEqual(plan["status"], "REVIEW_REQUIRED")
            with self.assertRaises(ValueError):
                run(root, apply=True)


if __name__ == "__main__":
    unittest.main()
