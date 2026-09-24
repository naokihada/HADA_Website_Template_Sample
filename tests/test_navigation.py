#!/usr/bin/env python3
"""Regression checks for the static navigation and breadcrumb example."""

from __future__ import annotations

import re
import unittest
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests" / "fixtures" / "navigation" / "about-notice.html"


class NavigationParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.landmarks: list[tuple[str, str]] = []
        self.links: list[tuple[str, str]] = []
        self.current_page_text: list[str] = []
        self.non_link_group_text: list[str] = []
        self._capture: str | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = {key: value or "" for key, value in attrs}
        if tag == "nav":
            self.landmarks.append((values.get("aria-label", ""), values.get("class", "")))
        if tag == "a":
            self.links.append((values.get("href", ""), values.get("aria-current", "")))
            if values.get("aria-current") == "page":
                self._capture = "current"
        elif values.get("aria-current") == "page":
            self._capture = "current"
        if tag == "span" and "site-nav-group" in values.get("class", "").split():
            self._capture = "group"

    def handle_endtag(self, tag: str) -> None:
        if tag in {"a", "span", "li"}:
            self._capture = None

    def handle_data(self, data: str) -> None:
        if self._capture == "current":
            self.current_page_text.append(data.strip())
        elif self._capture == "group":
            self.non_link_group_text.append(data.strip())


class NavigationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.html = FIXTURE.read_text(encoding="utf-8")
        self.parser = NavigationParser()
        self.parser.feed(self.html)

    def test_primary_secondary_and_breadcrumb_landmarks_are_distinct(self) -> None:
        self.assertEqual(
            self.parser.landmarks,
            [
                ("Primary navigation", "site-nav-primary"),
                ("About navigation", "site-nav-secondary"),
                ("Breadcrumb", "site-breadcrumbs"),
            ],
        )

    def test_group_label_is_not_a_fabricated_link(self) -> None:
        self.assertEqual(self.parser.non_link_group_text, ["About"])
        self.assertIn(("/en/about/", ""), self.parser.links)
        self.assertTrue(all(href.startswith("/") for href, _ in self.parser.links))

    def test_notice_breadcrumb_uses_company_as_its_parent(self) -> None:
        self.assertIn('<li><a href="/en/about/">Company</a></li>', self.html)
        self.assertIn('<li aria-current="page">Notice</li>', self.html)
        self.assertNotIn('<li><a href="/notice/">About</a></li>', self.html)
        self.assertEqual(self.parser.current_page_text, ["Notice"])

    def test_fixture_does_not_require_javascript(self) -> None:
        self.assertNotRegex(self.html, re.compile(r"<\s*script\b", re.IGNORECASE))

    def test_core_css_wraps_navigation_and_collapses_mobile_empty_row(self) -> None:
        css = (ROOT / "site" / "assets" / "css" / "core.css").read_text(encoding="utf-8")
        self.assertIn(".site-nav-primary, .site-nav-secondary", css)
        self.assertIn("flex-wrap: wrap", css)
        self.assertIn(".site-nav-empty-secondary { min-height:", css)
        self.assertRegex(css, r"@media\s*\(max-width:\s*40rem\)[\s\S]*?\.site-nav-empty-secondary\s*\{\s*display:\s*none")


if __name__ == "__main__":
    unittest.main()
