from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools" / "core"))

from external_javascript_policy import scan  # noqa: E402


class ExternalJavascriptPolicyTests(unittest.TestCase):
    def test_template_core_rejects_external_script(self) -> None:
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            (root / "site").mkdir()
            (root / "site/index.html").write_text(
                '<script src="https://static.cloudflareinsights.com/beacon.min.js/v1"></script>',
                encoding="utf-8",
            )
            findings = scan(root, {"policy": "forbidden", "roots": ["site"], "declarations": []})
            self.assertEqual(len(findings), 1)
            self.assertEqual(findings[0]["rule_id"], "JS-001")
            self.assertTrue(findings[0]["template_feedback"])

    def test_explicit_optional_client_only_declaration_is_allowed(self) -> None:
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            (root / "site").mkdir()
            url = "https://static.cloudflareinsights.com/beacon.min.js/v1"
            (root / "site/index.html").write_text(f'<script src="{url}"></script>', encoding="utf-8")
            findings = scan(
                root,
                {
                    "policy": "declared_client_only",
                    "roots": ["site"],
                    "declarations": [{"url": url, "purpose": "optional analytics", "required_for_content": False}],
                },
            )
            self.assertEqual(findings, [])

    def test_dynamic_and_module_external_javascript_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            (root / "site").mkdir()
            (root / "site/app.js").write_text(
                'import "https://cdn.example/app.js";\n'
                'const script = document.createElement("script"); script.src = "https://cdn.example/loader";',
                encoding="utf-8",
            )
            findings = scan(root, {"policy": "forbidden", "roots": ["site"], "declarations": []})
            self.assertEqual(len(findings), 2)
            self.assertTrue(all(item["rule_id"] == "JS-001" for item in findings))

    def test_content_required_declaration_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            (root / "site").mkdir()
            url = "https://example.com/widget.js"
            (root / "site/index.html").write_text(f'<script src="{url}"></script>', encoding="utf-8")
            findings = scan(
                root,
                {
                    "policy": "declared_client_only",
                    "roots": ["site"],
                    "declarations": [{"url": url, "required_for_content": True}],
                },
            )
            self.assertEqual({item["rule_id"] for item in findings}, {"JS-001", "JS-002"})

    def test_current_template_has_no_external_javascript(self) -> None:
        self.assertEqual(scan(ROOT), [])


if __name__ == "__main__":
    unittest.main()
