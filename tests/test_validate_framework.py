#!/usr/bin/env python3
"""Minimal tests for tools/core/validate_framework.py — stdlib unittest only."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
VALIDATOR = REPO_ROOT / "tools" / "core" / "validate_framework.py"


def run_validator(args: list[str], cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    command = [sys.executable, str(VALIDATOR), *args]
    return subprocess.run(command, cwd=str(cwd or REPO_ROOT), capture_output=True, text=True, check=False)


def copy_foundation_skeleton(target: Path) -> None:
    for rel in (
        "AGENTS.md",
        "README.md",
        ".gitignore",
        "config/project.yaml",
        "config/site.example.yaml",
        "environments/environments.example.yaml",
        "references/registry/references.example.yaml",
        "site/README.md",
    ):
        src = REPO_ROOT / rel
        dst = target / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
    for rel_dir in (
        "Cursor",
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
        ".cursor/rules",
    ):
        (target / rel_dir).mkdir(parents=True, exist_ok=True)
    rules_src = REPO_ROOT / ".cursor" / "rules"
    for rule_file in rules_src.iterdir():
        if rule_file.is_file():
            shutil.copy2(rule_file, target / ".cursor" / "rules" / rule_file.name)
    for rel in (
        "content/en/index.md",
        "content/en/about.md",
        "content/jp/index.md",
        "content/jp/about.md",
    ):
        src = REPO_ROOT / rel
        if src.is_file():
            dst = target / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)


def i18n_rule_ids(payload: dict) -> set[str]:
    return {item["rule_id"] for item in payload.get("findings", []) if item["rule_id"].startswith("I18N-")}


class ValidateFrameworkTests(unittest.TestCase):
    def test_pyyaml_available(self) -> None:
        import yaml

        self.assertIsNotNone(yaml)

    def test_foundation_baseline_passes(self) -> None:
        result = run_validator(["--root", str(REPO_ROOT), "--format", "json"])
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["status"], "PASS")

    def test_json_output_is_valid(self) -> None:
        result = run_validator(["--root", str(REPO_ROOT), "--format", "json"])
        payload = json.loads(result.stdout)
        self.assertEqual(payload["validator"], "core-validator")
        self.assertIn("summary", payload)

    def test_both_output_format(self) -> None:
        result = run_validator(["--root", str(REPO_ROOT), "--format", "both"])
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("---JSON---", result.stdout)
        json_part = result.stdout.split("---JSON---", 1)[1].strip()
        payload = json.loads(json_part)
        self.assertEqual(payload["status"], "PASS")

    def test_strict_treats_warning_as_failure(self) -> None:
        result = run_validator(["--root", str(REPO_ROOT), "--format", "json", "--strict"])
        self.assertEqual(result.returncode, 1)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["status"], "FAIL")

    def test_missing_root_exit_two(self) -> None:
        result = run_validator(["--root", str(REPO_ROOT / "does-not-exist"), "--format", "json"])
        self.assertEqual(result.returncode, 2)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["status"], "ERROR")

    def test_detects_configuration_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            copy_foundation_skeleton(root)
            project = (root / "config" / "project.yaml").read_text(encoding="utf-8")
            (root / "config" / "project.yaml").write_text(
                project.replace("mode: NEW", "mode: INVALID", 1),
                encoding="utf-8",
            )
            result = run_validator(["--root", str(root), "--format", "json"])
            self.assertEqual(result.returncode, 1)
            payload = json.loads(result.stdout)
            rule_ids = {item["rule_id"] for item in payload["errors"]}
            self.assertIn("CFG-003", rule_ids)

    def test_secret_not_echoed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            copy_foundation_skeleton(root)
            secret_file = root / "config" / "credentials.yaml"
            secret_file.write_text("credentials:\n  api_key: super-secret-value-123\n", encoding="utf-8")
            result = run_validator(["--root", str(root), "--format", "json"])
            self.assertEqual(result.returncode, 1)
            self.assertNotIn("super-secret-value-123", result.stdout)

    def test_forbidden_publication_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            copy_foundation_skeleton(root)
            (root / "config" / "site.yaml").write_text(
                "site:\n  publication_root: site\npublication:\n  deploy_target: tools/output\n",
                encoding="utf-8",
            )
            result = run_validator(["--root", str(root), "--format", "json"])
            self.assertEqual(result.returncode, 1)
            payload = json.loads(result.stdout)
            rule_ids = {item["rule_id"] for item in payload["errors"]}
            self.assertIn("SEC-004", rule_ids)

    def test_no_plugins_no_error(self) -> None:
        result = run_validator(["--root", str(REPO_ROOT), "--format", "json"])
        payload = json.loads(result.stdout)
        plugin_errors = [item for item in payload["errors"] if item["rule_id"].startswith("PLUGIN-")]
        self.assertEqual(plugin_errors, [])

    def test_i18n_locales_with_counterparts_pass(self) -> None:
        result = run_validator(["--root", str(REPO_ROOT), "--format", "json"])
        payload = json.loads(result.stdout)
        i18n_warnings = [
            item for item in payload.get("warnings", []) if item["rule_id"].startswith("I18N-")
        ]
        self.assertEqual(i18n_warnings, [])

    def test_i18n_en_only_missing_jp(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            copy_foundation_skeleton(root)
            (root / "content" / "en" / "extra.md").write_text("# Extra\n", encoding="utf-8")
            result = run_validator(["--root", str(root), "--format", "json"])
            payload = json.loads(result.stdout)
            self.assertIn("I18N-002", i18n_rule_ids(payload))

    def test_i18n_jp_only_missing_en(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            copy_foundation_skeleton(root)
            (root / "content" / "jp" / "extra.md").write_text("# Extra\n", encoding="utf-8")
            result = run_validator(["--root", str(root), "--format", "json"])
            payload = json.loads(result.stdout)
            self.assertIn("I18N-003", i18n_rule_ids(payload))

    def test_i18n_mismatched_basenames(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            copy_foundation_skeleton(root)
            (root / "content" / "en" / "foo.md").write_text("# Foo\n", encoding="utf-8")
            (root / "content" / "jp" / "bar.md").write_text("# Bar\n", encoding="utf-8")
            result = run_validator(["--root", str(root), "--format", "json"])
            payload = json.loads(result.stdout)
            rules = i18n_rule_ids(payload)
            self.assertIn("I18N-002", rules)
            self.assertIn("I18N-003", rules)

    def test_i18n_empty_locale_directories(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            copy_foundation_skeleton(root)
            for name in ("index.md", "about.md"):
                (root / "content" / "en" / name).unlink(missing_ok=True)
                (root / "content" / "jp" / name).unlink(missing_ok=True)
            result = run_validator(["--root", str(root), "--format", "json"])
            payload = json.loads(result.stdout)
            self.assertIn("I18N-004", i18n_rule_ids(payload))


if __name__ == "__main__":
    unittest.main()
