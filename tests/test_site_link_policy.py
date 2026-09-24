from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools" / "core"))

from site_link_policy import classify_url, same_site_hosts, scan  # noqa: E402


class SiteLinkPolicyTests(unittest.TestCase):
    def test_apex_and_www_are_same_site_aliases(self) -> None:
        aliases = same_site_hosts(["hada.org"])
        self.assertEqual(aliases, {"hada.org", "www.hada.org"})
        self.assertEqual(same_site_hosts(["hada.co.jp"]), {"hada.co.jp", "www.hada.co.jp"})
        self.assertIsNotNone(classify_url("https://www.hada.org/about/", aliases))
        self.assertIsNotNone(classify_url("https://hada.org/about/", aliases))
        self.assertIsNone(classify_url("https://gallery.hada.org/", aliases))

    def test_root_relative_policy_classifies_paths(self) -> None:
        hosts = {"hada.org", "www.hada.org"}
        self.assertIsNone(classify_url("/assets/site.css", hosts))
        self.assertIsNone(classify_url("#section", hosts))
        self.assertIsNotNone(classify_url("./about.html", hosts))
        self.assertIsNotNone(classify_url("../assets/site.css", hosts))
        self.assertIsNotNone(classify_url("about.html", hosts))

    def test_external_links_require_safe_new_tab_attributes(self) -> None:
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            pages = root / "pages"
            pages.mkdir()
            (pages / "index.html").write_text(
                '<a href="https://www.hada.org/about/">same site</a>'
                '<a href="https://gallery.hada.org/">unsafe external</a>'
                '<a href="https://blog.hada.org/" target="_blank" rel="noopener noreferrer">safe</a>',
                encoding="utf-8",
            )
            violations = scan(
                root,
                {
                    "enabled": True,
                    "roots": ["pages"],
                    "attributes": ["href", "src", "action"],
                    "internal_hosts": ["hada.org", "www.hada.org"],
                    "external_links": {"require_new_tab": True, "required_rel": ["noopener", "noreferrer"]},
                },
            )
            self.assertEqual(len(violations), 2)
            self.assertEqual({item["rule_id"] for item in violations}, {"LINK-002", "LINK-003"})
            self.assertTrue(all(item["template_feedback"] for item in violations))

    def test_current_template_publication_has_no_violations(self) -> None:
        self.assertEqual(scan(ROOT), [])


if __name__ == "__main__":
    unittest.main()
