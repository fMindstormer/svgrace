"""Run the web-platform-tests drafts in upstream/wpt/ in Playwright's Chromium, Firefox and WebKit.

A local server stands in for the WPT server: it serves upstream/wpt/ with testharness.js from the WPT
repository, and a testharnessreport.js that hands each subtest's result to this script.

  python tools/wpt.py              prints one line per subtest and engine
"""
import functools
import http.server
import shutil
import subprocess
import sys
import tempfile
import threading
import urllib.request
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
TESTS = ROOT / "upstream" / "wpt"
HARNESS = "https://raw.githubusercontent.com/web-platform-tests/wpt/master/resources/testharness.js"
REPORT = """add_completion_callback((tests, status) => {
  window.__results = {status: status.status, message: status.message,
                      tests: tests.map(t => ({name: t.name, status: t.status, message: t.message}))};
});"""
STATUS = {0: "PASS", 1: "FAIL", 2: "TIMEOUT", 3: "NOTRUN", 4: "PRECONDITION_FAILED"}


def main():
    root = Path(tempfile.mkdtemp())
    (root / "resources").mkdir()
    try:
        with urllib.request.urlopen(HARNESS, timeout=30) as r:
            (root / "resources" / "testharness.js").write_bytes(r.read())
    except OSError:   # e.g. a python.org Python without its certificates installed: curl uses the system's
        subprocess.run(["curl", "-sfL", "--retry", "3", "-o", str(root / "resources" / "testharness.js"), HARNESS], check=True)
    (root / "resources" / "testharnessreport.js").write_text(REPORT)
    shutil.copytree(TESTS / "svg", root / "svg")

    class Quiet(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *a):
            pass
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(Quiet, directory=str(root)))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    failed = 0
    with sync_playwright() as p:
        for engine in ("chromium", "firefox", "webkit"):
            b = getattr(p, engine).launch()
            for test in sorted(TESTS.rglob("*.html")):
                page = b.new_page()
                page.goto(f"http://127.0.0.1:{srv.server_port}/{test.relative_to(TESTS)}")
                page.wait_for_function("window.__results", timeout=20_000)
                got = page.evaluate("window.__results")
                page.close()
                for t in got["tests"]:
                    failed += t["status"] != 0
                    print(f"{engine:8s} {b.version:14s} {STATUS[t['status']]:7s} {test.name}: {t['name']}"
                          + (f"\n{'':32s}{t['message']}" if t["status"] else ""))
            b.close()
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
