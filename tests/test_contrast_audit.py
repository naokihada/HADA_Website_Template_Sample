#!/usr/bin/env python3
"""Tests for the deterministic accessibility policy audit."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools" / "core"))
from contrast_audit import audit_policy, contrast_ratio, validate_accessibility_policy  # noqa: E402


class ContrastAuditTests(unittest.TestCase):
    def test_wcag_ratio_is_calculated(self) -> None:
        self.assertGreaterEqual(contrast_ratio("#111111", "#ffffff"), 18.0)
        self.assertLess(contrast_ratio("#777777", "#ffffff"), 4.5)

    def test_default_policy_preserves_background_and_prioritizes_foreground(self) -> None:
        policy = {
            "normal_text_min_contrast": 4.5,
            "large_text_min_contrast": 3.0,
            "minimum_font_size": "1rem",
            "preserve_background_treatment": True,
            "foreground_adjustment_order": ["color", "font_weight", "font_size", "font_family"],
            "contrast_pairs": [{"name": "body", "foreground": "#111111", "background": "#ffffff", "minimum": 4.5}],
        }
        result = audit_policy(policy)
        self.assertEqual(result["status"], "PASS")
        self.assertTrue(result["preserve_background_treatment"])

    def test_policy_rejects_background_first_adjustment(self) -> None:
        errors = validate_accessibility_policy(
            {
                "minimum_font_size": "0.9rem",
                "foreground_adjustment_order": ["background", "color"],
            }
        )
        self.assertIn("accessibility.minimum_font_size must be at least 1rem", errors)
        self.assertIn("foreground_adjustment_order", errors[-1])


if __name__ == "__main__":
    unittest.main()
