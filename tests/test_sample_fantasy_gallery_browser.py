"""Browser regression for the published eight-image fantasy sample gallery."""

from __future__ import annotations

import http.server
import socketserver
import threading
import unittest
from urllib.parse import urljoin
from pathlib import Path

try:
    from playwright.sync_api import sync_playwright
except ImportError:  # pragma: no cover - optional UI extra
    sync_playwright = None

ROOT = Path(__file__).resolve().parents[1]
GALLERY_ROUTE = "media/otherworld-landscapes"


class SampleFantasyGalleryBrowserTests(unittest.TestCase):
    @unittest.skipIf(sync_playwright is None, "Playwright UI extra is not installed")
    def test_real_eight_image_gallery_and_viewer(self) -> None:
        publication = ROOT / "site"
        self.assertTrue((publication / "en" / GALLERY_ROUTE / "index.html").is_file())
        handler = lambda *args, **kwargs: http.server.SimpleHTTPRequestHandler(
            *args, directory=str(publication), **kwargs
        )

        class ReuseServer(socketserver.TCPServer):
            allow_reuse_address = True

        server = ReuseServer(("127.0.0.1", 0), handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        base = f"http://127.0.0.1:{server.server_address[1]}"
        try:
            with sync_playwright() as playwright:
                browser = playwright.chromium.launch()
                page = browser.new_page(viewport={"width": 1280, "height": 800})
                page.set_default_timeout(10_000)
                page_errors: list[str] = []
                page.on("pageerror", lambda error: page_errors.append(str(error)))
                response = page.goto(f"{base}/en/media/", wait_until="networkidle")
                self.assertEqual(response.status, 200)
                self.assertEqual(page.locator("body").get_attribute("data-ui-profile"), "shared-shell")
                self.assertEqual(page.locator("[data-site-header]").count(), 1)
                self.assertEqual(page.locator("[data-site-footer]").count(), 1)
                child_link = page.locator(f'a[href="/en/{GALLERY_ROUTE}/"]')
                self.assertEqual(child_link.count(), 1)
                child_link.click()
                page.wait_for_url(f"**/en/{GALLERY_ROUTE}/")
                self.assertEqual(page.locator("h1").inner_text(), "Otherworld Landscapes")
                self.assertEqual(page.locator('.breadcrumbs a[href="/en/media/"]').count(), 1)
                images = page.locator(".items figure img")
                links = page.locator(".items figure a")
                self.assertEqual(images.count(), 8)
                self.assertEqual(len(set(links.evaluate_all("els => els.map(el => el.href)"))), 8)
                self.assertTrue(all(alt.strip() for alt in images.evaluate_all("els => els.map(el => el.alt)")))
                decoded = page.evaluate("""async () => {
                  const images = [...document.querySelectorAll('.items figure img')];
                  await Promise.all(images.map(image => new Promise((resolve, reject) => {
                    if (image.complete && image.naturalWidth > 0) return resolve();
                    image.addEventListener('load', resolve, {once: true});
                    image.addEventListener('error', () => reject(new Error(image.src + ' failed')), {once: true});
                    image.loading = 'eager';
                    image.src = image.src;
                  })));
                  return images.map(image => image.naturalWidth);
                }""")
                self.assertEqual(len(decoded), 8)
                self.assertTrue(all(width > 0 for width in decoded))
                page.evaluate("""() => {
                  window.__mediaEvent = null;
                  window.addEventListener('contextmenu', event => {
                    window.__mediaEvent = {type: 'contextmenu', prevented: event.defaultPrevented};
                  });
                  window.addEventListener('dragstart', event => {
                    window.__mediaEvent = {type: 'dragstart', prevented: event.defaultPrevented};
                  });
                }""")
                self.assertEqual(images.nth(0).get_attribute("draggable"), "false")
                images.nth(0).click(button="right")
                self.assertTrue(page.evaluate("window.__mediaEvent.prevented"))
                page.locator("h1").click(button="right")
                self.assertFalse(page.evaluate("window.__mediaEvent.prevented"))
                images.nth(0).dispatch_event("dragstart")
                self.assertTrue(page.evaluate("window.__mediaEvent.prevented"))
                for index in range(8):
                    image = images.nth(index)
                    self.assertGreater(image.evaluate("el => el.naturalWidth"), 0)
                    asset = page.request.get(urljoin(base, links.nth(index).get_attribute("href")))
                    self.assertEqual(asset.status, 200)
                    self.assertTrue(asset.headers.get("content-type", "").startswith("image/jpeg"))

                links.nth(0).click()
                dialog = page.locator("dialog.media-viewer")
                dialog.wait_for(state="visible")
                position = dialog.locator("[data-viewer-position]")
                self.assertEqual(position.inner_text(), "1 / 8")
                for index in range(2, 9):
                    page.locator('[data-viewer-action="next"]').click()
                    page.wait_for_function(
                        f"document.querySelector('dialog [data-viewer-position]').textContent==='{index} / 8'"
                    )
                    self.assertEqual(position.inner_text(), f"{index} / 8")
                page.locator('[data-viewer-action="previous"]').click()
                page.wait_for_function(
                    "document.querySelector('dialog [data-viewer-position]').textContent==='7 / 8'"
                )

                viewer_image = dialog.locator("[data-viewer-image]")
                page.locator('[data-viewer-action="actual"]').click()
                native_width = viewer_image.evaluate("el => el.naturalWidth")
                self.assertEqual(float(viewer_image.evaluate("el => parseFloat(el.style.width)")), native_width)
                viewer_image.click(button="right")
                self.assertTrue(page.evaluate("window.__mediaEvent.prevented"))
                self.assertEqual(page.locator('[data-viewer-action="zoom-in"]').count(), 0)
                self.assertEqual(page.locator('[data-viewer-action="zoom-out"]').count(), 0)
                stage = page.locator("[data-viewer-stage]")
                box = stage.bounding_box()
                page.mouse.move(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
                page.mouse.wheel(450, 250)
                page.wait_for_function("document.querySelector('[data-viewer-stage]').scrollLeft>0")
                self.assertGreater(stage.evaluate("el => el.scrollTop"), 0)
                page.locator('[data-viewer-action="fit"]').click()
                self.assertEqual(stage.evaluate("el => [el.scrollLeft, el.scrollTop]"), [0, 0])
                self.assertLessEqual(
                    float(viewer_image.evaluate("el => parseFloat(el.style.width)")),
                    page.locator("[data-viewer-stage]").evaluate("el => el.clientWidth") + 1,
                )
                fullscreen = page.locator('[data-viewer-action="fullscreen"]')
                if fullscreen.is_visible():
                    fullscreen.click()
                    page.wait_for_function("!!document.fullscreenElement")
                    self.assertTrue(page.evaluate("!!document.fullscreenElement"))
                    fullscreen.click()
                    page.wait_for_function("!document.fullscreenElement")
                page.keyboard.press("Escape")
                self.assertFalse(dialog.evaluate("el => el.open"))
                self.assertEqual(page.evaluate("document.activeElement.id"), "media-item-00001")
                page.keyboard.press("Enter")
                page.wait_for_function("document.querySelector('dialog.media-viewer')?.open===true")
                self.assertEqual(position.inner_text(), "1 / 8")
                self.assertEqual(dialog.get_attribute("data-reading-direction"), "rtl")
                no_js = browser.new_context(java_script_enabled=False).new_page()
                no_js.goto(f"{base}/en/{GALLERY_ROUTE}/", wait_until="networkidle")
                no_js.locator("#media-item-00001").click()
                self.assertTrue(no_js.url.endswith("/assets/media/web/otherworld-landscapes-20261108/001-whispering-river-valley.jpg"))

                for locale in ("jp", "de"):
                    mobile = browser.new_page(viewport={"width": 390, "height": 844})
                    localized = mobile.goto(f"{base}/{locale}/{GALLERY_ROUTE}/", wait_until="networkidle")
                    self.assertEqual(localized.status, 200)
                    self.assertEqual(mobile.locator(".items figure").count(), 8)
                    self.assertLessEqual(
                        mobile.evaluate("document.documentElement.scrollWidth"),
                        mobile.evaluate("innerWidth"),
                    )
                    self.assertTrue(mobile.locator("h1").inner_text().strip())
                self.assertEqual(page_errors, [])
                browser.close()
        finally:
            server.shutdown()
            server.server_close()


if __name__ == "__main__":
    unittest.main()
