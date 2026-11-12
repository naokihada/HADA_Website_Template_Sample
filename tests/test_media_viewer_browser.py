"""Browser checks for the progressive media viewer; requires the optional UI extra."""

from __future__ import annotations

import http.server
import socketserver
import tempfile
import threading
import unittest
from pathlib import Path

import json
from PIL import Image

try:
    from playwright.sync_api import sync_playwright
except ImportError:  # pragma: no cover - optional browser dependency
    sync_playwright = None

ROOT = Path(__file__).resolve().parents[1]
import sys
sys.path.insert(0, str(ROOT / "tools" / "core"))
from media_library import build_media_library  # noqa: E402


class MediaViewerBrowserTests(unittest.TestCase):
    @unittest.skipIf(sync_playwright is None, "Playwright UI extra is not installed")
    def test_manga_order_navigation_controls_and_empty_facing_slot(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "config").mkdir()
            media = []
            for number, title in ((1, "Cover"), (2, "Frontispiece"), (3, "Body 1"),
                                  (4, "Body 2"), (5, "Back cover")):
                relative = f"assets/media/web/{number:05d}.jpg"
                target = root / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                Image.new("RGB", (360, 540), (number * 35, 65, 120)).save(target, quality=90)
                media.append({"media_id": f"page-{number:05d}", "type": "image",
                              "public_file": relative, "status": "approved",
                              "source": {"visibility": "private"},
                              "title": {"en": title, "jp": title},
                              "alt": {"en": title, "jp": title}})
            catalog = {"schema_version": "0.3", "media": media, "collections": [{
                "collection_id": "manga", "route": "manga", "presentation": "gallery",
                "title": {"en": "Manga", "jp": "漫画"}, "listing": {"enabled": False},
                "media_ids": [f"page-{number:05d}" for number in range(1, 6)],
                "sequence": {"order": "manual", "reading_direction": "rtl",
                             "first_page_side": "right", "first_page_side_options": ["right", "left"]},
                "viewer": {"enabled": True, "modes": ["single", "manga"],
                           "default_mode": "manga", "mobile_default_mode": "single",
                           "open_on_load": True},
            }]}
            (root / "config/media.catalog.json").write_text(
                json.dumps(catalog, ensure_ascii=False), encoding="utf-8")
            site = root / "site"
            build_media_library(root, site, ["jp"])

            handler = lambda *args, **kwargs: http.server.SimpleHTTPRequestHandler(
                *args, directory=str(site), **kwargs)
            class ReuseServer(socketserver.TCPServer):
                allow_reuse_address = True
            server = ReuseServer(("127.0.0.1", 0), handler)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                with sync_playwright() as playwright:
                    browser = playwright.chromium.launch()
                    page = browser.new_page(viewport={"width": 1280, "height": 900})
                    page.goto(f"http://127.0.0.1:{server.server_address[1]}/jp/media/manga/")
                    dialog = page.locator("dialog.media-viewer")
                    dialog.wait_for(state="visible")
                    page.wait_for_function("document.querySelector('[data-viewer-right]').naturalWidth > 0")
                    page.wait_for_function("document.querySelector('dialog [data-viewer-position]').textContent.length > 0")
                    self.assertIn("1–2 / 5ページ", dialog.locator("[data-viewer-position]").inner_text())
                    self.assertIn("Cover · Frontispiece", dialog.locator("[data-viewer-caption]").inner_text())
                    self.assertEqual(page.locator("[data-viewer-right]").get_attribute("alt"), "Cover")
                    self.assertEqual(page.locator("[data-viewer-left]").get_attribute("alt"), "Frontispiece")
                    next_button = page.locator('[data-viewer-action="next"]')
                    previous_button = page.locator('[data-viewer-action="previous"]')
                    self.assertLess(next_button.bounding_box()["x"], previous_button.bounding_box()["x"])
                    self.assertEqual(page.locator(".media-viewer__navigation").evaluate(
                        "el => getComputedStyle(el).direction"), "ltr")

                    next_button.click()
                    self.assertEqual(page.locator("[data-viewer-right]").get_attribute("alt"), "Body 1")
                    self.assertEqual(page.locator("[data-viewer-left]").get_attribute("alt"), "Body 2")
                    page.locator("[data-viewer-stage]").focus()
                    page.keyboard.press("ArrowLeft")
                    self.assertEqual(page.locator("[data-viewer-right]").get_attribute("alt"), "Back cover")
                    self.assertTrue(page.locator("[data-viewer-left]").evaluate("el => el.hidden"))
                    self.assertEqual(page.locator(".media-viewer__stage img[hidden][src]").count(), 0)
                    page.wait_for_function(
                        "[...document.querySelectorAll('.media-viewer__stage img:not([hidden])')].every(el => el.naturalWidth > 0)"
                    )
                    previous_button.click()
                    self.assertEqual(page.locator("[data-viewer-right]").get_attribute("alt"), "Body 1")

                    page.locator('[data-viewer-side="left"]').click()
                    self.assertEqual(page.locator("[data-viewer-left]").get_attribute("alt"), "Body 1")
                    self.assertEqual(page.locator("[data-viewer-right]").get_attribute("alt"), "Frontispiece")
                    page.locator('[data-viewer-side="right"]').click()
                    self.assertEqual(page.locator("[data-viewer-right]").get_attribute("alt"), "Body 1")
                    self.assertEqual(page.locator("[data-viewer-left]").get_attribute("alt"), "Body 2")
                    page.locator('[data-viewer-action="close"]').click()
                    page.locator("[data-viewer-reopen]").click()
                    page.wait_for_function("document.querySelector('dialog.media-viewer')?.open")
                    page.locator('[data-viewer-side="left"]').click()
                    self.assertEqual(page.locator("[data-viewer-left]").get_attribute("alt"), "Cover")
                    self.assertTrue(page.locator("[data-viewer-right]").evaluate("el => el.hidden"))
                    self.assertEqual(page.locator(".media-viewer__stage img[hidden][src]").count(), 0)
                    self.assertEqual(page.locator(".media-viewer__stage img:not([hidden]):not([src])").count(), 0)
                    browser.close()
            finally:
                server.shutdown()
                server.server_close()

    @unittest.skipIf(sync_playwright is None, "Playwright UI extra is not installed")
    def test_collection_library_cover_cards_and_sorting(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "config").mkdir()
            media = []
            for media_id, filename, alt in (
                ("amber-cover", "amber.jpg", "Amber cover"),
                ("zephyr-cover", "zephyr.jpg", "Zephyr cover"),
            ):
                relative = f"assets/media/web/{filename}"
                target = root / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                Image.new("RGB", (320, 240), (30, 80, 130)).save(target, quality=90)
                media.append({"media_id": media_id, "type": "image", "public_file": relative,
                              "status": "approved", "source": {"visibility": "private"},
                              "alt": {"en": alt, "jp": alt}})
            catalog = {"schema_version": "0.3", "media": media, "collections": [{
                "collection_id": "library", "route": "library", "presentation": "gallery",
                "title": {"en": "Library", "jp": "本棚"}, "listing": {"enabled": True},
                "children": [
                    {"collection_id": "zephyr", "route": "library/zephyr", "presentation": "gallery",
                     "title": {"en": "Zephyr", "jp": "ゼファー"}, "media_ids": ["zephyr-cover"],
                     "publication_date": "2022-04-03", "updated_date": "2024-01-02"},
                    {"collection_id": "amber", "route": "library/amber", "presentation": "gallery",
                     "title": {"en": "Amber", "jp": "アンバー"}, "media_ids": ["amber-cover"],
                     "publication_date": "2024-02-01", "updated_date": "2023-03-01"},
                    {"collection_id": "undated", "route": "library/undated", "presentation": "gallery",
                     "title": {"en": "Beta", "jp": "ベータ"}, "media_ids": []},
                ],
            }]}
            (root / "config/media.catalog.json").write_text(
                json.dumps(catalog, ensure_ascii=False), encoding="utf-8")
            site = root / "site"
            build_media_library(root, site, ["en", "jp", "de"])
            handler = lambda *args, **kwargs: http.server.SimpleHTTPRequestHandler(
                *args, directory=str(site), **kwargs)

            class ReuseServer(socketserver.TCPServer):
                allow_reuse_address = True

            server = ReuseServer(("127.0.0.1", 0), handler)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            base = f"http://127.0.0.1:{server.server_address[1]}"
            try:
                with sync_playwright() as playwright:
                    browser = playwright.chromium.launch()
                    page = browser.new_page()
                    page.goto(f"{base}/jp/media/library/")
                    cards = page.locator("[data-collection-library] > li")
                    names = lambda: cards.locator(".collection-library__title").all_text_contents()
                    self.assertEqual(names(), ["アンバー", "ゼファー", "ベータ"])
                    self.assertEqual(page.locator(".collection-library__cover").count(), 2)
                    self.assertEqual(page.locator(".collection-library__cover").first.get_attribute("alt"), "Amber cover")
                    self.assertEqual(page.locator('select[name="key"] option').all_text_contents(), ["名前", "出版日", "更新日"])
                    page.locator('select[name="key"]').select_option("publication_date")
                    self.assertEqual(names(), ["ゼファー", "アンバー", "ベータ"])
                    page.locator('select[name="direction"]').select_option("desc")
                    self.assertEqual(names(), ["アンバー", "ゼファー", "ベータ"])
                    page.locator('select[name="key"]').select_option("updated_date")
                    page.locator('select[name="direction"]').select_option("asc")
                    self.assertEqual(names(), ["アンバー", "ゼファー", "ベータ"])
                    for locale, expected in (("en", "Sort by"), ("de", "Sortieren nach")):
                        page.goto(f"{base}/{locale}/media/library/")
                        self.assertIn(expected, page.locator("form[data-library-sort]").inner_text())
                    no_js = browser.new_context(java_script_enabled=False).new_page()
                    no_js.goto(f"{base}/en/media/library/")
                    self.assertEqual(no_js.locator("[data-collection-library] > li").count(), 3)
                    self.assertEqual(no_js.locator('ul.collection-library a[href^="/en/media/library/"]').count(), 3)
                    browser.close()
            finally:
                server.shutdown()
                server.server_close()

    @unittest.skipIf(sync_playwright is None, "Playwright UI extra is not installed")
    def test_dialog_fit_actual_navigation_deterrence_and_no_js_fallback(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "config").mkdir()
            media = []
            for number, color in ((1, (20, 80, 140)), (2, (140, 80, 20))):
                relative = f"assets/media/web/{number:05d}.jpg"
                target = root / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                dimensions = (160, 120) if number == 1 else (1800, 1400)
                Image.new("RGB", dimensions, color).save(target, quality=90)
                media.append({"media_id": f"page-{number:05d}", "type": "image",
                              "public_file": relative, "status": "approved",
                              "source": {"visibility": "private"},
                              "alt": {"en": f"Page {number}", "jp": f"ページ{number}"}})
            catalog = {"schema_version": "0.3", "media": media, "collections": [{
                "collection_id": "reader", "route": "reader", "presentation": "sequence",
                "listing": {"enabled": True}, "media_ids": ["page-00001", "page-00002"],
                "sequence": {"order": "filename", "reading_direction": "rtl",
                             "first_page_side": "right", "view": "single", "spread_enabled": True},
                "viewer": {"enabled": True},
            }]}
            (root / "config/media.catalog.json").write_text(
                json.dumps(catalog, ensure_ascii=False), encoding="utf-8")
            site = root / "site"
            build_media_library(root, site, ["en"])

            handler = lambda *args, **kwargs: http.server.SimpleHTTPRequestHandler(
                *args, directory=str(site), **kwargs)
            class ReuseServer(socketserver.TCPServer):
                allow_reuse_address = True
            server = ReuseServer(("127.0.0.1", 0), handler)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            base = f"http://127.0.0.1:{server.server_address[1]}"
            try:
                with sync_playwright() as playwright:
                    browser = playwright.chromium.launch()
                    page = browser.new_page()
                    page.goto(f"{base}/en/media/reader/page-00001.html")
                    page.evaluate("""() => {
                      window.__mediaEvent = null;
                      window.addEventListener('contextmenu', event => {
                        window.__mediaEvent = {type: 'contextmenu', prevented: event.defaultPrevented};
                      });
                      window.addEventListener('dragstart', event => {
                        window.__mediaEvent = {type: 'dragstart', prevented: event.defaultPrevented};
                      });
                    }""")
                    thumbnail = page.locator("#media-item-00001 img")
                    self.assertEqual(thumbnail.get_attribute("draggable"), "false")
                    thumbnail.click(button="right")
                    self.assertTrue(page.evaluate("window.__mediaEvent.prevented"))
                    page.locator("h1").click(button="right")
                    self.assertFalse(page.evaluate("window.__mediaEvent.prevented"))
                    thumbnail.dispatch_event("dragstart")
                    self.assertTrue(page.evaluate("window.__mediaEvent.prevented"))
                    trigger = page.locator("#media-item-00001")
                    trigger.focus()
                    trigger.press("Enter")
                    dialog = page.locator("dialog.media-viewer")
                    dialog.wait_for(state="visible")
                    page.locator("dialog [data-viewer-image]").wait_for()
                    page.wait_for_function("document.querySelector('[data-viewer-image]').naturalWidth > 0")
                    stage = page.locator("[data-viewer-stage]")
                    self.assertLessEqual(stage.evaluate("el => el.scrollWidth"), stage.evaluate("el => el.clientWidth"))
                    self.assertEqual(stage.evaluate("el => getComputedStyle(el).scrollbarWidth"), "none")
                    self.assertEqual(stage.evaluate("el => getComputedStyle(el, '::-webkit-scrollbar').display"), "none")
                    self.assertEqual(dialog.locator("[data-viewer-position]").inner_text(), "1 / 2")
                    self.assertTrue(page.locator("dialog [data-viewer-image]").get_attribute("src").endswith("00001.jpg"))
                    image = page.locator("dialog [data-viewer-image]")
                    natural_width = image.evaluate("el => el.naturalWidth")
                    fitted_width = image.evaluate("el => parseFloat(el.style.width)")
                    self.assertGreater(fitted_width, natural_width)
                    page.keyboard.press("Escape")
                    self.assertEqual(page.evaluate("document.activeElement.id"), "media-item-00001")

                    trigger.click()
                    actual = page.locator('[data-viewer-action="actual"]')
                    actual.click()
                    rendered_width = image.evaluate("el => parseFloat(el.style.width)")
                    self.assertEqual(rendered_width, natural_width)
                    self.assertEqual(stage.evaluate("el => getComputedStyle(el).scrollbarWidth"), "none")
                    page.locator('[data-viewer-action="fit"]').click()
                    self.assertGreater(image.evaluate("el => parseFloat(el.style.width)"), natural_width)
                    self.assertLessEqual(stage.evaluate("el => el.scrollWidth"), stage.evaluate("el => el.clientWidth"))
                    self.assertEqual(page.locator('[data-viewer-action="zoom-in"]').count(), 0)
                    self.assertEqual(page.locator('[data-viewer-action="zoom-out"]').count(), 0)
                    image.click(button="right")
                    self.assertTrue(page.evaluate("window.__mediaEvent.prevented"))
                    image.dispatch_event("dragstart")
                    self.assertTrue(page.evaluate("window.__mediaEvent.prevented"))
                    page.locator('[data-viewer-action="next"]').click()
                    page.wait_for_url("**/page-00002.html#media-item-00002")
                    page.wait_for_function("document.querySelector('[data-viewer-image]').naturalWidth === 1800")
                    actual.click()
                    self.assertGreater(stage.evaluate("el => el.scrollWidth"), stage.evaluate("el => el.clientWidth"))
                    self.assertGreater(stage.evaluate("el => el.scrollHeight"), stage.evaluate("el => el.clientHeight"))
                    before = stage.evaluate("el => [el.scrollLeft, el.scrollTop]")
                    stage_box = stage.bounding_box()
                    start_x, start_y = stage_box["x"] + stage_box["width"] / 2, stage_box["y"] + stage_box["height"] / 2
                    page.mouse.move(start_x, start_y)
                    page.mouse.down()
                    page.mouse.move(start_x - 180, start_y - 180)
                    page.mouse.up()
                    after = stage.evaluate("el => [el.scrollLeft, el.scrollTop]")
                    self.assertGreater(after[0], before[0])
                    self.assertGreater(after[1], before[1])
                    page.locator('[data-viewer-action="fit"]').click()
                    self.assertLessEqual(stage.evaluate("el => el.scrollWidth"), stage.evaluate("el => el.clientWidth"))
                    self.assertLessEqual(stage.evaluate("el => el.scrollHeight"), stage.evaluate("el => el.clientHeight"))
                    page.locator('[data-viewer-action="previous"]').click()
                    page.wait_for_url("**/page-00001.html#media-item-00001")
                    fullscreen = page.locator('[data-viewer-action="fullscreen"]')
                    if fullscreen.is_visible():
                        fullscreen.click()
                        page.wait_for_function("!!document.fullscreenElement")
                        self.assertTrue(page.evaluate("!!document.fullscreenElement"))
                        fullscreen.click()
                        page.wait_for_function("!document.fullscreenElement")
                    page.keyboard.press("ArrowLeft")
                    page.wait_for_url("**/page-00002.html#media-item-00002")
                    page.wait_for_function("document.querySelector('dialog.media-viewer')?.open === true")
                    self.assertEqual(dialog.locator("[data-viewer-position]").inner_text(), "2 / 2")
                    page.locator('[data-viewer-action="previous"]').click()
                    page.wait_for_url("**/page-00001.html#media-item-00001")
                    page.wait_for_function("document.querySelector('dialog.media-viewer')?.open === true")

                    no_js = browser.new_context(java_script_enabled=False).new_page()
                    no_js.goto(f"{base}/en/media/reader/page-00001.html")
                    no_js.locator("#media-item-00001").click()
                    no_js.wait_for_url("**/assets/media/web/00001.jpg")
                    self.assertTrue(no_js.url.endswith("assets/media/web/00001.jpg"))
                    browser.close()
            finally:
                server.shutdown()
                server.server_close()


if __name__ == "__main__":
    unittest.main()
