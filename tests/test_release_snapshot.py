from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools" / "core"))
from release_snapshot import snapshot  # noqa: E402


class ReleaseSnapshotTests(unittest.TestCase):
    def test_snapshot_contains_manifest_site_and_checksums(self) -> None:
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            (root / "config").mkdir()
            (root / "site").mkdir()
            (root / "config/project.yaml").write_text(
                "paths:\r\n  publication_root: site\r\n  template_references: references/template-releases\r\n",
                encoding="utf-8",
            )
            (root / "config/template.manifest.yaml").write_text("template:\r\n  version: '0.3.1'\r\n", encoding="utf-8")
            (root / "site/index.html").write_text("ok", encoding="utf-8")
            target = snapshot(root, "v0.3.1")
            self.assertTrue((target / "manifest.yaml").is_file())
            self.assertEqual((target / "site/index.html").read_text(encoding="utf-8"), "ok")
            self.assertIn("site/index.html", (target / "checksums.sha256").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
