"""The engines the checks run in: Playwright's Chromium, Firefox and WebKit, and the real Safari.

Playwright does not drive Safari, so Safari goes through safaridriver (WebDriver, with the selenium
package), behind the few Playwright calls the checks make: new_page, set_content, goto, evaluate,
wait_for_function, screenshot, close, and the browser's version. set_content serves the text from a
local HTTP server as text/html, so Safari parses it the way Playwright's set_content does: as an HTML
document with the SVG inline.

Safari needs a one-time setup that asks for the user's password: `safaridriver --enable` in a terminal,
and Settings > Developer > "Allow remote automation" in Safari (Settings > Advanced > "Show features for
web developers" shows that tab). Safari runs in a visible window. Leave it uncovered while a check runs:
a page that cannot be seen may have its animations and timers throttled.
"""
import contextlib
import http.server
import io
import itertools
import threading
import time

ENGINES = {"chromium": "Chromium", "firefox": "Firefox", "webkit": "WebKit", "safari": "Safari"}
PLAYWRIGHT = ("chromium", "firefox", "webkit")


@contextlib.contextmanager
def launch(engine):
    """The browser for one engine, closed on exit. Playwright's engines are Playwright's own objects."""
    if engine == "safari":
        b = Safari()
        try:
            yield b
        finally:
            b.close()
        return
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        b = getattr(p, engine).launch()
        try:
            yield b
        finally:
            b.close()


class _Content(http.server.BaseHTTPRequestHandler):
    """Serves the text handed to set_content, as text/html, from memory."""

    def do_GET(self):
        body = self.server.content.get(self.path)
        if body is None:
            self.send_error(404)
            return
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *a):
        pass


class Safari:
    """Safari through safaridriver. Safari allows one WebDriver session at a time, so the browser has one
    page at a time: the session's window, sent back to about:blank when the page closes."""

    def __init__(self):
        from selenium import webdriver
        self.driver = webdriver.Safari()
        self.version = self.driver.capabilities.get("browserVersion", "")
        self.server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), _Content)
        self.server.content = {}
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.names = itertools.count()
        self.page = None
        self.load_timeout = None

    def new_page(self, viewport=None):
        if self.page is not None:
            raise RuntimeError("Safari has one page at a time; close the last one first")
        self.page = SafariPage(self, **(viewport or {"width": 1280, "height": 720}))   # Playwright's default
        return self.page

    def close(self):
        if self.driver is not None:
            self.driver.quit()
            self.server.shutdown()
            self.driver = None


class SafariPage:
    def __init__(self, browser, width, height):
        self.browser, self.driver = browser, browser.driver
        for _ in range(3):   # the window's size includes Safari's toolbar; adjust until the viewport fits
            w, h = self.driver.execute_script("return [innerWidth, innerHeight]")
            if (w, h) == (width, height):
                break
            r = self.driver.get_window_rect()
            self.driver.set_window_rect(width=r["width"] + width - w, height=r["height"] + height - h)

    def goto(self, url, timeout=30_000):
        """Navigate and wait for the load event. A timeout of 0 means none, as in Playwright."""
        if timeout != self.browser.load_timeout:
            self.driver.set_page_load_timeout(timeout / 1000 if timeout else 24 * 3600)
            self.browser.load_timeout = timeout
        self.driver.get(url)

    def set_content(self, html, timeout=30_000):
        path = f"/content{next(self.browser.names)}.html"
        self.browser.server.content = {path: html.encode()}
        self.goto(f"http://127.0.0.1:{self.browser.server.server_port}{path}", timeout)

    def evaluate(self, expression, arg=None):
        """Like Playwright's: a function is called with arg, anything else is evaluated as an expression."""
        return self.driver.execute_script(
            f"const value = ({expression});\nreturn typeof value === 'function' ? value(arguments[0]) : value;", arg)

    def wait_for_function(self, expression, timeout=30_000):
        end = time.time() + timeout / 1000
        while not self.evaluate(expression):
            if time.time() > end:
                raise TimeoutError(f"{expression} was still false after {timeout} ms")
            time.sleep(0.1)

    def screenshot(self):
        """The viewport as PNG bytes, like Playwright's: one pixel per CSS pixel, in sRGB. safaridriver takes
        it at the display's scale, and in the display's colour space when the PNG carries a profile."""
        from PIL import Image, ImageCms
        img = Image.open(io.BytesIO(self.driver.get_screenshot_as_png()))
        icc = img.info.get("icc_profile")
        img = img.convert("RGB")
        if icc:
            img = ImageCms.profileToProfile(img, ImageCms.ImageCmsProfile(io.BytesIO(icc)),
                                            ImageCms.createProfile("sRGB"), outputMode="RGB")
        scale = self.driver.execute_script("return devicePixelRatio")
        if scale != 1:
            img = img.resize((round(img.width / scale), round(img.height / scale)), Image.NEAREST)
        out = io.BytesIO()
        img.save(out, "PNG")
        return out.getvalue()

    def close(self):
        self.driver.get("about:blank")   # stops the document's clock
        self.browser.server.content = {}
        self.browser.page = None
