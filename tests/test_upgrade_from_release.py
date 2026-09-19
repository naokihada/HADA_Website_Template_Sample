#!/usr/bin/env python3
"""Tests for tools/core/upgrade_from_release.py — offline-safe by default."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
import re
from pathlib import Path
from typing import Any, Dict, Optional, Tuple
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parents[1]
TOOLS_CORE = REPO_ROOT / "tools" / "core"
UPGRADE = TOOLS_CORE / "upgrade_from_release.py"
MANIFEST = REPO_ROOT / "config" / "template.manifest.yaml"
RELEASE_MANIFEST = MANIFEST

if str(TOOLS_CORE) not in sys.path:
    sys.path.insert(0, str(TOOLS_CORE))

import upgrade_from_release as ufr  # noqa: E402


def write_min_manifest(target: Path, version: str = "0.1.2") -> None:
    text = re.sub(r'(  version:\s*)"[^"]+"', rf'\g<1>"{version}"', MANIFEST.read_text(encoding="utf-8"), count=1)
    (target / "config").mkdir(parents=True, exist_ok=True)
    (target / "config" / "template.manifest.yaml").write_text(text, encoding="utf-8")


def mini_template(root: Path, version: str, tool_content: str) -> None:
    root.mkdir(parents=True, exist_ok=True)
    (root / "AGENTS.md").write_text("# AGENTS\n", encoding="utf-8")
    (root / "tools" / "core").mkdir(parents=True, exist_ok=True)
    (root / "tools" / "core" / "sample_tool.txt").write_text(tool_content, encoding="utf-8")
    (root / "config").mkdir(parents=True, exist_ok=True)
    (root / "config" / "project.yaml").write_text(
        'project:\n  name: Site Name\n  id: test\n  version: "1.0"\n  mode: MAINTENANCE\n',
        encoding="utf-8",
    )
    write_min_manifest(root, version)


class UpgradeMigrationTests(unittest.TestCase):
    def setUp(self) -> None:
        self._td = tempfile.TemporaryDirectory()
        self.base = Path(self._td.name)

    def tearDown(self) -> None:
        self._td.cleanup()

    def test_case_a_template_only_auto(self) -> None:
        prev = self.base / "P"
        new = self.base / "N"
        site = self.base / "C"
        mini_template(prev, "0.1.1", "old")
        mini_template(new, "0.1.2", "new")
        mini_template(site, "0.1.1", "old")
        manifest, _ = ufr.load_yaml(new / "config" / "template.manifest.yaml")
        plan, _ = ufr.build_plan(site, prev, new, manifest)
        actions = {i.rel_path: i.action for i in plan if i.rel_path.endswith("sample_tool.txt")}
        self.assertEqual(actions["tools/core/sample_tool.txt"], ufr.Action.AUTO)

    def test_case_b_user_only_preserve(self) -> None:
        prev = self.base / "P"
        new = self.base / "N"
        site = self.base / "C"
        mini_template(prev, "0.1.1", "same")
        mini_template(new, "0.1.2", "same")
        mini_template(site, "0.1.1", "user-edit")
        manifest, _ = ufr.load_yaml(new / "config" / "template.manifest.yaml")
        plan, _ = ufr.build_plan(site, prev, new, manifest)
        actions = {i.rel_path: i.action for i in plan if i.rel_path.endswith("sample_tool.txt")}
        self.assertEqual(actions["tools/core/sample_tool.txt"], ufr.Action.PRESERVE)

    def test_case_c_both_changed_review(self) -> None:
        prev = self.base / "P"
        new = self.base / "N"
        site = self.base / "C"
        mini_template(prev, "0.1.1", "old")
        mini_template(new, "0.1.2", "new")
        mini_template(site, "0.1.1", "user")
        manifest, _ = ufr.load_yaml(new / "config" / "template.manifest.yaml")
        plan, _ = ufr.build_plan(site, prev, new, manifest)
        actions = {i.rel_path: i.action for i in plan if i.rel_path.endswith("sample_tool.txt")}
        self.assertEqual(actions["tools/core/sample_tool.txt"], ufr.Action.REVIEW)

    def test_case_d_unchanged_skip(self) -> None:
        prev = self.base / "P"
        new = self.base / "N"
        site = self.base / "C"
        mini_template(prev, "0.1.1", "same")
        mini_template(new, "0.1.2", "same")
        mini_template(site, "0.1.1", "same")
        manifest, _ = ufr.load_yaml(new / "config" / "template.manifest.yaml")
        plan, _ = ufr.build_plan(site, prev, new, manifest)
        actions = {i.rel_path: i.action for i in plan if i.rel_path.endswith("sample_tool.txt")}
        self.assertEqual(actions["tools/core/sample_tool.txt"], ufr.Action.SKIP)

    def test_case_e_new_template_file_add(self) -> None:
        prev = self.base / "P"
        new = self.base / "N"
        site = self.base / "C"
        mini_template(prev, "0.1.1", "x")
        mini_template(new, "0.1.2", "x")
        mini_template(site, "0.1.1", "x")
        (new / "tools" / "core" / "new_file.txt").write_text("added", encoding="utf-8")
        manifest, _ = ufr.load_yaml(new / "config" / "template.manifest.yaml")
        manifest["ownership"]["template"].append("tools/core/new_file.txt")
        plan, _ = ufr.build_plan(site, prev, new, manifest)
        actions = {i.rel_path: i.action for i in plan}
        self.assertEqual(actions.get("tools/core/new_file.txt"), ufr.Action.ADD)

    def test_case_f_delete_with_user_mod_review(self) -> None:
        prev = self.base / "P"
        new = self.base / "N"
        site = self.base / "C"
        mini_template(prev, "0.1.1", "x")
        mini_template(new, "0.1.2", "x")
        mini_template(site, "0.1.1", "x")
        (prev / "tools" / "core" / "removed.txt").write_text("old", encoding="utf-8")
        (site / "tools" / "core" / "removed.txt").write_text("user", encoding="utf-8")
        manifest, _ = ufr.load_yaml(new / "config" / "template.manifest.yaml")
        manifest["ownership"]["template"].append("tools/core/removed.txt")
        plan, _ = ufr.build_plan(site, prev, new, manifest)
        actions = {i.rel_path: i.action for i in plan}
        self.assertEqual(actions.get("tools/core/removed.txt"), ufr.Action.REVIEW)

    def test_case_g_generated_manual_edit_review(self) -> None:
        prev = self.base / "P"
        new = self.base / "N"
        site = self.base / "C"
        for d in (prev, new, site):
            d.mkdir(parents=True, exist_ok=True)
            (d / "AGENTS.md").write_text("# A\n", encoding="utf-8")
            (d / "site" / "en").mkdir(parents=True, exist_ok=True)
            write_min_manifest(d, "0.1.2")
        (prev / "site" / "en" / "index.html").write_text("<p>gen</p>", encoding="utf-8")
        (new / "site" / "en" / "index.html").write_text("<p>gen2</p>", encoding="utf-8")
        (site / "site" / "en" / "index.html").write_text("<p>hand</p>", encoding="utf-8")
        manifest, _ = ufr.load_yaml(new / "config" / "template.manifest.yaml")
        plan, _ = ufr.build_plan(site, prev, new, manifest)
        actions = {i.rel_path: i.action for i in plan if "site/en/index.html" in i.rel_path}
        self.assertEqual(actions["site/en/index.html"], ufr.Action.REVIEW)

    def test_case_h_safe_yaml_merge_auto(self) -> None:
        prev = self.base / "P"
        new = self.base / "N"
        site = self.base / "C"
        mini_template(prev, "0.1.1", "t")
        mini_template(new, "0.1.2", "t")
        mini_template(site, "0.1.1", "t")
        shared = (
            'project:\n  name: My Site\n  id: test\n  version: "1.0"\n  mode: MAINTENANCE\n'
        )
        (prev / "config" / "project.yaml").write_text(shared, encoding="utf-8")
        (site / "config" / "project.yaml").write_text(shared, encoding="utf-8")
        (new / "config" / "project.yaml").write_text(
            shared + "  new_key: added\n",
            encoding="utf-8",
        )
        manifest, _ = ufr.load_yaml(new / "config" / "template.manifest.yaml")
        plan, _ = ufr.build_plan(site, prev, new, manifest)
        proj = [i for i in plan if i.rel_path == "config/project.yaml"][0]
        self.assertEqual(proj.action, ufr.Action.AUTO)

    def test_case_i_yaml_type_conflict_review(self) -> None:
        prev = self.base / "P"
        new = self.base / "N"
        site = self.base / "C"
        mini_template(prev, "0.1.1", "t")
        mini_template(new, "0.1.2", "t")
        mini_template(site, "0.1.1", "t")
        (prev / "config" / "project.yaml").write_text(
            'project:\n  name: 123\n  id: test\n  version: "1.0"\n  mode: MAINTENANCE\n',
            encoding="utf-8",
        )
        (site / "config" / "project.yaml").write_text(
            'project:\n  name: 123\n  id: test\n  version: "1.0"\n  mode: MAINTENANCE\n',
            encoding="utf-8",
        )
        (new / "config" / "project.yaml").write_text(
            'project:\n  name: Template\n  id: test\n  version: "1.0"\n  mode: NEW\n',
            encoding="utf-8",
        )
        manifest, _ = ufr.load_yaml(new / "config" / "template.manifest.yaml")
        plan, _ = ufr.build_plan(site, prev, new, manifest)
        proj = [i for i in plan if i.rel_path == "config/project.yaml"][0]
        self.assertEqual(proj.action, ufr.Action.REVIEW)

    def test_case_j_unknown_version_blocked(self) -> None:
        site = self.base / "site"
        site.mkdir()
        (site / "AGENTS.md").write_text("# A\n", encoding="utf-8")
        result = ufr.run_upgrade(
            site,
            skip_network=True,
            local_new_template=REPO_ROOT,
            release_resolver=lambda r, v: ("0.1.2", "v0.1.2", {"prerelease": False, "draft": False}),
        )
        self.assertEqual(result.status, "BLOCKED")
        self.assertEqual(result.exit_code, ufr.EXIT_BLOCKED)

    def test_case_k_network_failure_blocked(self) -> None:
        site = self.base / "site"
        mini_template(site, "0.1.2", "site")
        result = ufr.run_upgrade(
            site,
            network_check=lambda repo: (False, "offline"),
            release_resolver=lambda r, v: ("0.1.2", "v0.1.2", {"prerelease": False}),
        )
        self.assertEqual(result.status, "BLOCKED")

    def test_case_l_invalid_release_blocked(self) -> None:
        site = self.base / "site"
        site.mkdir(parents=True, exist_ok=True)
        write_min_manifest(site, "0.1.2")
        result = ufr.run_upgrade(
            site,
            skip_network=True,
            release_resolver=lambda r, v: (None, None, None),
        )
        self.assertEqual(result.status, "BLOCKED")

    def test_case_m_prerelease_blocked(self) -> None:
        site = self.base / "site"
        mini_template(site, "0.1.2", "site")
        detection, ver = ufr.detect_version(site)
        if detection == "unknown":
            self.skipTest("need detected version")
        result = ufr.run_upgrade(
            site,
            skip_network=True,
            release_resolver=lambda r, v: ("0.1.2", "v0.1.2", {"prerelease": True, "draft": False}),
        )
        self.assertEqual(result.status, "BLOCKED")

    def test_case_n_temp_clone_metadata(self) -> None:
        td = tempfile.mkdtemp(prefix="hada-upgrade-test-")
        dest = Path(td)
        try:
            mini_template(dest, "0.1.2", "x")
            ufr.write_clone_metadata(dest, "naokihada/HADA_Website_Template", "v0.1.2")
            meta_path = dest / ufr.CLONE_META
            self.assertTrue(meta_path.is_file())
            data, err = ufr.load_yaml(meta_path)
            self.assertIsNone(err)
            assert data is not None
            self.assertTrue(data.get("retain"))
        finally:
            shutil.rmtree(td, ignore_errors=True)

    def test_detect_version_from_manifest(self) -> None:
        site = self.base / "site"
        mini_template(site, "0.1.2", "x")
        status, ver = ufr.detect_version(site)
        self.assertEqual(status, "detected")
        self.assertEqual(ver, "0.1.2")

    def test_v011_to_v012_migration_allowed(self) -> None:
        manifest, _ = ufr.load_yaml(MANIFEST)
        assert manifest is not None
        self.assertTrue(ufr.migration_allowed(manifest, "0.1.1", "0.1.2"))

    def test_v013_to_v020_migration_allowed(self) -> None:
        manifest, _ = ufr.load_yaml(MANIFEST)
        assert manifest is not None
        self.assertTrue(ufr.migration_allowed(manifest, "0.1.3", "0.2.0"))

    def test_release_manifest_version_matches_target(self) -> None:
        manifest, error = ufr.load_yaml(RELEASE_MANIFEST)
        self.assertIsNone(error)
        assert manifest is not None
        self.assertEqual(manifest["template"]["version"], "0.3.1")

    def test_case_o_target_git_untouched(self) -> None:
        prev = self.base / "P"
        new = self.base / "N"
        site = self.base / "C"
        mini_template(prev, "0.1.1", "old")
        mini_template(new, "0.1.2", "new")
        mini_template(site, "0.1.1", "old")
        git_calls: list[list[str]] = []

        def track_run(cmd: Any, *args: Any, **kwargs: Any) -> subprocess.CompletedProcess[str]:
            if isinstance(cmd, list) and cmd and cmd[0] == "git":
                git_calls.append(list(cmd))
            return subprocess.CompletedProcess(cmd, 0, "", "")

        with mock.patch("subprocess.run", side_effect=track_run):
            result = ufr.run_upgrade(
                site,
                skip_network=True,
                local_new_template=new,
                local_previous_template=prev,
                assume_version="0.1.1",
                dry_run=True,
            )
        self.assertEqual(git_calls, [])
        self.assertIn(result.status, ("SUCCESS", "REVIEW_REQUIRED"))

    def test_user_owned_never_in_apply(self) -> None:
        prev = self.base / "P"
        new = self.base / "N"
        site = self.base / "C"
        mini_template(prev, "0.1.1", "x")
        mini_template(new, "0.1.2", "x")
        mini_template(site, "0.1.1", "x")
        (site / "content" / "jp").mkdir(parents=True, exist_ok=True)
        (site / "content" / "jp" / "index.md").write_text("# User\n", encoding="utf-8")
        (new / "content" / "jp").mkdir(parents=True, exist_ok=True)
        (new / "content" / "jp" / "index.md").write_text("# Template\n", encoding="utf-8")
        manifest, _ = ufr.load_yaml(new / "config" / "template.manifest.yaml")
        plan, _ = ufr.build_plan(site, prev, new, manifest)
        content_items = [i for i in plan if i.rel_path == "content/jp/index.md"]
        self.assertEqual(content_items, [])


class UpgradeCLITests(unittest.TestCase):
    def test_cli_dry_run_local(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            site = Path(td) / "site"
            prev = Path(td) / "prev"
            new = Path(td) / "new"
            mini_template(prev, "0.1.1", "old")
            mini_template(new, "0.1.2", "new")
            mini_template(site, "0.1.1", "old")
            before = (site / "tools" / "core" / "sample_tool.txt").read_text(encoding="utf-8")
            proc = subprocess.run(
                [
                    sys.executable,
                    str(UPGRADE),
                    "--root",
                    str(site),
                    "--skip-network",
                    "--local-new-template",
                    str(new),
                    "--local-previous-template",
                    str(prev),
                    "--assume-version",
                    "0.1.1",
                    "--dry-run",
                    "--format",
                    "json",
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, ufr.EXIT_SUCCESS, proc.stderr + proc.stdout)
            after = (site / "tools" / "core" / "sample_tool.txt").read_text(encoding="utf-8")
            self.assertEqual(before, after)


if __name__ == "__main__":
    unittest.main()
