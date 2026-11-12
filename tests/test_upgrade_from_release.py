#!/usr/bin/env python3
"""Tests for tools/core/upgrade_from_release.py — offline-safe by default."""

from __future__ import annotations

import hashlib
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
MANIFEST = REPO_ROOT / "config" / "website-template.json"
RELEASE_MANIFEST = MANIFEST

if str(TOOLS_CORE) not in sys.path:
    sys.path.insert(0, str(TOOLS_CORE))

import upgrade_from_release as ufr  # noqa: E402


def write_min_manifest(target: Path, version: str = "0.1.2") -> None:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    manifest["template"]["version"] = version
    manifest["template"]["release"] = f"v{version}"
    (target / "config").mkdir(parents=True, exist_ok=True)
    (target / "config" / "website-template.json").write_text(json.dumps(manifest), encoding="utf-8")


def mini_template(root: Path, version: str, tool_content: str) -> None:
    root.mkdir(parents=True, exist_ok=True)
    (root / "AGENTS.md").write_text("# AGENTS\n", encoding="utf-8")
    (root / "tools" / "core").mkdir(parents=True, exist_ok=True)
    (root / "tools" / "core" / "sample_tool.txt").write_text(tool_content, encoding="utf-8")
    (root / "config").mkdir(parents=True, exist_ok=True)
    (root / "config" / "project.toml").write_text(
        '[project]\nname = "Site Name"\nid = "test"\nversion = "1.0"\nmode = "MAINTENANCE"\n',
        encoding="utf-8",
    )
    write_min_manifest(root, version)


class UpgradeMigrationTests(unittest.TestCase):
    def setUp(self) -> None:
        self._td = tempfile.TemporaryDirectory()
        self.base = Path(self._td.name)

    def tearDown(self) -> None:
        self._td.cleanup()

    def test_template_attribution_updates_only_linked_official_repository(self) -> None:
        linked = '<a href="https://github.com/naokihada/HADA_Website_Template">Built with HADA Website Template (v0.2.2) · GitHub</a>'
        updated, changed = ufr.update_template_attribution_text(linked, "0.4.1", ufr.DEFAULT_REPO)
        self.assertTrue(changed)
        self.assertIn("(v0.4.1)", updated)
        unlinked, changed = ufr.update_template_attribution_text("Built with HADA Website Template (v0.2.2)", "0.4.1", ufr.DEFAULT_REPO)
        self.assertFalse(changed)
        self.assertEqual(unlinked, "Built with HADA Website Template (v0.2.2)")
        other_link = '<a href="https://example.com/template">Built with HADA Website Template (v0.2.2)</a>'
        unchanged, changed = ufr.update_template_attribution_text(other_link, "0.4.1", ufr.DEFAULT_REPO)
        self.assertFalse(changed)
        self.assertEqual(unchanged, other_link)

    def test_attribution_plan_updates_master_publication_and_registry_hash(self) -> None:
        root = self.base / "site"
        master = root / "content/pages/index.html"
        publication = root / "published/index.html"
        master.parent.mkdir(parents=True)
        publication.parent.mkdir(parents=True)
        source = '<a href="https://github.com/naokihada/HADA_Website_Template">Built with HADA Website Template (v0.2.2) · GitHub</a>'
        master.write_text(source, encoding="utf-8")
        publication.write_text(source, encoding="utf-8")
        old_hash = hashlib.sha256(master.read_bytes()).hexdigest()
        (root / "config").mkdir()
        (root / "config/project.toml").write_text('[paths]\npublication_root = "published"\ncontent_master = "content"\n', encoding="utf-8")
        (root / "config/page-registry.json").write_text(json.dumps({"source_hash": old_hash}), encoding="utf-8")

        updates = ufr.plan_template_attribution_updates(root, "0.4.1", ufr.DEFAULT_REPO)

        self.assertIn("content/pages/index.html", updates)
        self.assertIn("published/index.html", updates)
        self.assertIn("config/page-registry.json", updates)
        self.assertIn(b"(v0.4.1)", updates["content/pages/index.html"])
        new_hash = hashlib.sha256(updates["content/pages/index.html"]).hexdigest()
        self.assertIn(new_hash.encode("ascii"), updates["config/page-registry.json"])
        self.assertNotIn(old_hash.encode("ascii"), updates["config/page-registry.json"])

    def test_semantic_site_audit_ignores_only_linked_attribution_version(self) -> None:
        before_root = self.base / "before"
        after_root = self.base / "after"
        before_root.mkdir()
        after_root.mkdir()
        prefix = '<html><head><title>Site</title></head><body><p>Content</p>'
        suffix = "</body></html>"
        link = '<a href="https://github.com/naokihada/HADA_Website_Template">Built with HADA Website Template (v{})</a>'
        (before_root / "index.html").write_text(prefix + link.format("0.2.2") + suffix, encoding="utf-8")
        (after_root / "index.html").write_text(prefix + link.format("0.4.1") + suffix, encoding="utf-8")

        diff = ufr.compare_site(ufr.audit_site(before_root), ufr.audit_site(after_root))

        self.assertEqual(diff["status"], "PASS")
        (after_root / "index.html").write_text(prefix + "<p>Changed content</p>" + link.format("0.4.1") + suffix, encoding="utf-8")
        changed_content_diff = ufr.compare_site(ufr.audit_site(before_root), ufr.audit_site(after_root))
        self.assertEqual(changed_content_diff["status"], "REVIEW_REQUIRED")

    def test_upgrade_dry_run_reports_linked_attribution_without_writing(self) -> None:
        prev = self.base / "P"
        new = self.base / "N"
        site = self.base / "C"
        mini_template(prev, "0.1.1", "old")
        mini_template(new, "0.1.2", "new")
        mini_template(site, "0.1.1", "old")
        footer = '<a href="https://github.com/naokihada/HADA_Website_Template">Built with HADA Website Template (v0.1.1) · GitHub</a>'
        (site / "content").mkdir()
        (site / "content/index.html").write_text(footer, encoding="utf-8")
        before = (site / "content/index.html").read_bytes()

        result = ufr.run_upgrade(site, dry_run=True, skip_network=True, local_new_template=new,
            local_previous_template=prev, assume_version="0.1.1")

        self.assertEqual(result.status, "SUCCESS")
        self.assertTrue(any(item.action == ufr.Action.UPDATE_ATTRIBUTION for item in result.plan))
        self.assertEqual((site / "content/index.html").read_bytes(), before)

    def test_case_a_template_only_auto(self) -> None:
        prev = self.base / "P"
        new = self.base / "N"
        site = self.base / "C"
        mini_template(prev, "0.1.1", "old")
        mini_template(new, "0.1.2", "new")
        mini_template(site, "0.1.1", "old")
        manifest, _ = ufr.load_structured(new / "config" / "website-template.json")
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
        manifest, _ = ufr.load_structured(new / "config" / "website-template.json")
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
        manifest, _ = ufr.load_structured(new / "config" / "website-template.json")
        plan, _ = ufr.build_plan(site, prev, new, manifest)
        actions = {i.rel_path: i.action for i in plan if i.rel_path.endswith("sample_tool.txt")}
        self.assertEqual(actions["tools/core/sample_tool.txt"], ufr.Action.REVIEW)

    def test_safe_partial_plan_excludes_destructive_and_adoption_paths(self) -> None:
        plan = [
            ufr.PlanItem("tools/core/safe.py", ufr.Action.AUTO, "template three-way"),
            ufr.PlanItem("tools/core/new.py", ufr.Action.ADD, "template three-way"),
            ufr.PlanItem("tools/core/remove.py", ufr.Action.REMOVE, "template three-way"),
            ufr.PlanItem("config/project.toml", ufr.Action.AUTO, "safe TOML merge"),
            ufr.PlanItem("config/website-template.json", ufr.Action.AUTO, "template three-way"),
            ufr.PlanItem("content/page.html", ufr.Action.UPDATE_ATTRIBUTION, "linked attribution"),
            ufr.PlanItem("tools/core/conflict.py", ufr.Action.REVIEW, "template three-way"),
        ]

        selected = ufr.safe_partial_plan(plan)

        self.assertEqual([item.rel_path for item in selected], ["tools/core/safe.py", "tools/core/new.py"])

    def test_apply_safe_applies_only_safe_template_items_and_keeps_adoption_pending(self) -> None:
        prev, new, site = self.base / "P", self.base / "N", self.base / "C"
        for root, version, tool_text, conflict_text in (
            (prev, "0.1.1", "old", "old"),
            (new, "0.1.2", "new", "new"),
            (site, "0.1.1", "old", "consumer edit"),
        ):
            mini_template(root, version, tool_text)
            core = root / "tools/core"
            (core / "validate_framework.py").write_text("raise SystemExit(0)\n", encoding="utf-8")
            (core / "build_site.py").write_text("raise SystemExit(0)\n", encoding="utf-8")
            (core / "conflict.txt").write_text(conflict_text, encoding="utf-8")
            (root / "tests").mkdir(exist_ok=True)
            (root / "site").mkdir(exist_ok=True)
        footer = '<a href="https://github.com/naokihada/HADA_Website_Template">Built with HADA Website Template (v0.1.1)</a>'
        (site / "content").mkdir()
        (site / "content/index.html").write_text(footer, encoding="utf-8")
        before_manifest = (site / "config/website-template.json").read_bytes()

        result = ufr.run_upgrade(
            site, skip_network=True, local_new_template=new, local_previous_template=prev,
            assume_version="0.1.1", apply_safe=True,
        )

        self.assertEqual(result.status, "REVIEW_REQUIRED")
        self.assertIn("tools/core/sample_tool.txt", result.applied)
        self.assertNotIn("tools/core/conflict.txt", result.applied)
        self.assertEqual((site / "tools/core/sample_tool.txt").read_text(encoding="utf-8"), "new")
        self.assertEqual((site / "tools/core/conflict.txt").read_text(encoding="utf-8"), "consumer edit")
        self.assertEqual((site / "config/website-template.json").read_bytes(), before_manifest)
        self.assertFalse((site / "TEMPLATE_BASE.md").exists())
        self.assertIn("v0.1.1", (site / "content/index.html").read_text(encoding="utf-8"))
        receipts = list((site / "AI/history").glob("upgrade-partial-*/PARTIAL.json"))
        self.assertEqual(len(receipts), 1)
        receipt = json.loads(receipts[0].read_text(encoding="utf-8"))
        self.assertFalse(receipt["manifest_and_template_base_advanced"])
        self.assertFalse(receipt["footer_attribution_advanced"])

    def test_case_d_unchanged_skip(self) -> None:
        prev = self.base / "P"
        new = self.base / "N"
        site = self.base / "C"
        mini_template(prev, "0.1.1", "same")
        mini_template(new, "0.1.2", "same")
        mini_template(site, "0.1.1", "same")
        manifest, _ = ufr.load_structured(new / "config" / "website-template.json")
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
        manifest, _ = ufr.load_structured(new / "config" / "website-template.json")
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
        manifest, _ = ufr.load_structured(new / "config" / "website-template.json")
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
        manifest, _ = ufr.load_structured(new / "config" / "website-template.json")
        plan, _ = ufr.build_plan(site, prev, new, manifest)
        actions = {i.rel_path: i.action for i in plan if "site/en/index.html" in i.rel_path}
        self.assertEqual(actions["site/en/index.html"], ufr.Action.REVIEW)

    def test_case_h_safe_toml_merge_auto(self) -> None:
        prev = self.base / "P"
        new = self.base / "N"
        site = self.base / "C"
        mini_template(prev, "0.1.1", "t")
        mini_template(new, "0.1.2", "t")
        mini_template(site, "0.1.1", "t")
        shared = '[project]\nname = "My Site"\nid = "test"\nversion = "1.0"\nmode = "MAINTENANCE"\n'
        (prev / "config" / "project.toml").write_text(shared, encoding="utf-8")
        (site / "config" / "project.toml").write_text(shared, encoding="utf-8")
        (new / "config" / "project.toml").write_text(
            shared + 'new_key = "added"\n',
            encoding="utf-8",
        )
        manifest, _ = ufr.load_structured(new / "config" / "website-template.json")
        plan, _ = ufr.build_plan(site, prev, new, manifest)
        proj = [i for i in plan if i.rel_path == "config/project.toml"][0]
        self.assertEqual(proj.action, ufr.Action.AUTO)

    def test_case_i_toml_type_conflict_review(self) -> None:
        prev = self.base / "P"
        new = self.base / "N"
        site = self.base / "C"
        mini_template(prev, "0.1.1", "t")
        mini_template(new, "0.1.2", "t")
        mini_template(site, "0.1.1", "t")
        (prev / "config" / "project.toml").write_text(
            '[project]\nname = 123\nid = "test"\nversion = "1.0"\nmode = "MAINTENANCE"\n',
            encoding="utf-8",
        )
        (site / "config" / "project.toml").write_text(
            '[project]\nname = 123\nid = "test"\nversion = "1.0"\nmode = "MAINTENANCE"\n',
            encoding="utf-8",
        )
        (new / "config" / "project.toml").write_text(
            '[project]\nname = "Template"\nid = "test"\nversion = "1.0"\nmode = "NEW"\n',
            encoding="utf-8",
        )
        manifest, _ = ufr.load_structured(new / "config" / "website-template.json")
        plan, _ = ufr.build_plan(site, prev, new, manifest)
        proj = [i for i in plan if i.rel_path == "config/project.toml"][0]
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
            data, err = ufr.load_structured(meta_path)
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
        manifest, _ = ufr.load_structured(MANIFEST)
        assert manifest is not None
        self.assertTrue(ufr.migration_allowed(manifest, "0.1.1", "0.1.2"))

    def test_v013_to_v020_migration_allowed(self) -> None:
        manifest, _ = ufr.load_structured(MANIFEST)
        assert manifest is not None
        self.assertTrue(ufr.migration_allowed(manifest, "0.1.3", "0.2.0"))

    def test_v033_to_v040_migration_allowed(self) -> None:
        manifest, _ = ufr.load_structured(MANIFEST)
        assert manifest is not None
        self.assertTrue(ufr.migration_allowed(manifest, "0.3.3", "0.4.0"))

    def test_v040_to_v041_migration_allowed(self) -> None:
        manifest, _ = ufr.load_structured(MANIFEST)
        assert manifest is not None
        self.assertTrue(ufr.migration_allowed(manifest, "0.4.0", "0.4.1"))

    def test_release_manifest_version_matches_target(self) -> None:
        manifest, error = ufr.load_structured(RELEASE_MANIFEST)
        self.assertIsNone(error)
        assert manifest is not None
        self.assertEqual(manifest["template"]["version"], "0.5.0")

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
        manifest, _ = ufr.load_structured(new / "config" / "website-template.json")
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
