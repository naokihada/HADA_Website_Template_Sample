#!/usr/bin/env python3
"""Optional Playwright contract runner for the configured publication surface."""

from __future__ import annotations

import json
import sys
from contextlib import contextmanager
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread
from typing import Any, Iterator
from urllib.parse import urlparse

from site_contract import resolve_site
from ui_contract import configured_viewports, external_links, parse_html, route_inventory

try:
    from playwright.sync_api import Error as PlaywrightError
    from playwright.sync_api import sync_playwright
except ImportError:  # pragma: no cover - exercised on environments without UI dependencies
    PlaywrightError = RuntimeError  # type: ignore[assignment,misc]
    sync_playwright = None  # type: ignore[assignment]


class QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, format: str, *args: Any) -> None:  # noqa: A002
        return


@contextmanager
def static_server(root: Path) -> Iterator[str]:
    handler = partial(QuietHandler, directory=str(root))
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}"
    finally:
        server.shutdown()
        thread.join(timeout=5)
        server.server_close()


def _check_profile(page: Any, profile: str, route: str, failures: list[dict[str, str]]) -> None:
    if profile == "review_required":
        failures.append({"route": route, "check": "profile", "message": "No supported UI profile was declared"})
        return
    if not page.title().strip():
        failures.append({"route": route, "check": "title", "message": "Page title is empty"})
    if page.locator('meta[name="viewport"]').count() == 0:
        failures.append({"route": route, "check": "viewport", "message": "Viewport meta tag is missing"})
    if profile == "shared-shell":
        for selector, label in (
            ("[data-site-header]", "header"),
            ("[data-site-footer]", "footer"),
            ("[data-display-controls]", "display controls"),
        ):
            if page.locator(selector).count() == 0:
                failures.append({"route": route, "check": "shared-shell", "message": f"Missing {label}"})
        surface = page.evaluate("getComputedStyle(document.body).getPropertyValue('--site-surface').trim()")
        if not surface:
            failures.append({"route": route, "check": "surface-token", "message": "Shared surface token is not defined"})
        for selector, label in (("[data-site-header]", "header"), ("[data-site-footer]", "footer"), ("main", "main")):
            color = page.locator(selector).first.evaluate("el => getComputedStyle(el).color")
            if not color:
                failures.append({"route": route, "check": "readability", "message": f"{label} text color is not resolved"})
    elif profile == "standalone":
        if page.locator("a").count() == 0:
            failures.append({"route": route, "check": "standalone", "message": "Standalone page has no navigation link"})
    elif profile == "pwa" and page.locator("main").count() == 0:
        failures.append({"route": route, "check": "pwa", "message": "PWA page is missing main content"})


def run_browser_contract(root: Path, test_root: Path | None = None) -> dict[str, Any]:
    site = resolve_site(root)
    config = site.get("browser") if isinstance(site.get("browser"), dict) else {}
    if config.get("enabled") is not True:
        return {"status": "SKIPPED", "reason": "verification.browser.enabled is not true", "routes": [], "failures": []}
    if sync_playwright is None:
        return {"status": "REVIEW_REQUIRED", "reason": "Playwright is not installed", "routes": [], "failures": []}

    test_root = (test_root or (root / str(site.get("local_test_root") or site.get("publication_root", "site")))).resolve()
    if not test_root.is_dir():
        return {"status": "REVIEW_REQUIRED", "reason": f"local test root does not exist: {test_root}", "routes": [], "failures": []}
    routes = route_inventory(root, test_root)
    failures: list[dict[str, str]] = []
    blocked_requests: list[str] = []
    checked: list[dict[str, Any]] = []
    if not routes:
        return {"status": "REVIEW_REQUIRED", "reason": "No HTML routes discovered", "routes": [], "failures": []}

    try:
        with static_server(test_root) as base_url, sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            try:
                context = browser.new_context()
                try:
                    def handle_route(route: Any) -> None:
                        request_url = route.request.url
                        parsed = urlparse(request_url)
                        if parsed.hostname in {"127.0.0.1", "localhost"} or parsed.scheme in {"data", "about"}:
                            route.continue_()
                        else:
                            blocked_requests.append(request_url)
                            route.abort()

                    if config.get("block_external_requests", True):
                        context.route("**/*", handle_route)
                    for viewport in configured_viewports(root):
                        context.set_default_timeout(10000)
                        context.set_default_navigation_timeout(15000)
                        for route_info in routes:
                            page = context.new_page()
                            console_errors: list[str] = []
                            page_errors: list[str] = []
                            page.on("console", lambda message: console_errors.append(message.text) if message.type == "error" else None)
                            page.on("pageerror", lambda error: page_errors.append(str(error)))
                            url = f"{base_url}/{route_info['route']}"
                            try:
                                page.set_viewport_size(viewport)
                                page.goto(url, wait_until="load")
                                _check_profile(page, str(route_info["profile"]), str(route_info["route"]), failures)
                                overflow = page.evaluate("document.documentElement.scrollWidth > document.documentElement.clientWidth + 1")
                                if overflow:
                                    failures.append({"route": str(route_info["route"]), "check": "overflow", "message": f"Horizontal overflow at {viewport['width']}px"})
                                links = page.locator("a").evaluate_all("els => els.map(a => ({href:a.href,target:a.target,rel:a.rel}))")
                                for link in external_links(links):
                                    if urlparse(link.get("href", "")).hostname in {"127.0.0.1", "localhost"}:
                                        continue
                                    rel = set(link.get("rel", "").lower().split())
                                    if link.get("target") != "_blank" or not {"noopener", "noreferrer"}.issubset(rel):
                                        failures.append({"route": str(route_info["route"]), "check": "external-link", "message": "External link needs target=_blank and rel=noopener noreferrer"})
                                if page.locator(".background-fade").count():
                                    background = page.locator(".background-fade").first.evaluate("el => getComputedStyle(el).backgroundImage")
                                    if background == "none":
                                        failures.append({"route": str(route_info["route"]), "check": "background", "message": "Background fade has no computed image"})
                            except Exception as exc:  # browser diagnostics become contract failures
                                failures.append({"route": str(route_info["route"]), "check": "navigation", "message": str(exc)})
                            if console_errors or page_errors:
                                failures.append({"route": str(route_info["route"]), "check": "console", "message": "; ".join(console_errors + page_errors)})
                            checked.append({"route": route_info["route"], "profile": route_info["profile"], "viewport": viewport})
                            page.close()

                    reduced_context = browser.new_context(reduced_motion="reduce")
                    try:
                        reduced_page = reduced_context.new_page()
                        reduced_page.set_viewport_size({"width": 390, "height": 844})
                        reduced_page.goto(f"{base_url}/{routes[0]['route']}", wait_until="load")
                        if not reduced_page.evaluate("window.matchMedia('(prefers-reduced-motion: reduce)').matches"):
                            failures.append({"route": routes[0]["route"], "check": "reduced-motion", "message": "Reduced-motion media preference was not observed"})
                        if reduced_page.evaluate("document.documentElement.scrollWidth > document.documentElement.clientWidth + 1"):
                            failures.append({"route": routes[0]["route"], "check": "reduced-motion", "message": "Reduced-motion viewport overflows horizontally"})
                        reduced_page.close()
                    finally:
                        reduced_context.close()

                    shared = [item for item in routes if item["profile"] == "shared-shell"]
                    if len(shared) >= 2:
                        page = context.new_page()
                        context.set_default_timeout(10000)
                        page.goto(f"{base_url}/{shared[0]['route']}", wait_until="load")
                        page.locator('[data-set-theme="dark"]').click()
                        page.locator('[data-set-text-size="xlarge"]').click()
                        page.goto(f"{base_url}/{shared[1]['route']}", wait_until="load")
                        if page.locator("body").get_attribute("data-theme") != "dark":
                            failures.append({"route": shared[1]["route"], "check": "persistence", "message": "Theme was not preserved after navigation"})
                        if page.locator("body").get_attribute("data-text-size") != "xlarge":
                            failures.append({"route": shared[1]["route"], "check": "persistence", "message": "Text size was not preserved after navigation"})
                        page.close()
                finally:
                    context.close()
            finally:
                browser.close()
    except PlaywrightError as exc:
        return {"status": "REVIEW_REQUIRED", "reason": f"Browser runtime unavailable: {exc}", "routes": routes, "failures": failures}

    if blocked_requests:
        failures.append({"route": "*", "check": "external-request", "message": f"Blocked external requests: {len(blocked_requests)}"})
    return {
        "status": "PASS" if not failures else "REVIEW_REQUIRED",
        "routes": [{"route": item["route"], "profile": item["profile"], "source": item["source"]} for item in routes],
        "checked": checked,
        "failures": failures,
        "blocked_requests": blocked_requests,
    }


def main(argv: list[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Run the optional Playwright UI contract")
    parser.add_argument("--root", default=".")
    parser.add_argument("--test-root", help="Override the local server root, for example an isolated candidate")
    parser.add_argument("--output")
    args = parser.parse_args(argv)
    test_root = Path(args.test_root).resolve() if args.test_root else None
    result = run_browser_contract(Path(args.root).resolve(), test_root=test_root)
    text = json.dumps(result, indent=2, ensure_ascii=False) + "\n"
    print(text, end="")
    if args.output:
        Path(args.output).write_text(text, encoding="utf-8", newline="\r\n")
    return 0 if result["status"] in {"PASS", "SKIPPED"} else 4


if __name__ == "__main__":
    raise SystemExit(main())
