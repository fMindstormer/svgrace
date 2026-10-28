"""Record examples/maze.svg running in Chromium, as an animated WebP for the README. The recording is of
the real file in a real engine; nothing is drawn by this script."""
import functools
import http.server
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]


def main(seconds=24):
    class Quiet(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *a):
            pass
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(Quiet, directory=str(ROOT / "examples")))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    tmp = Path(tempfile.mkdtemp())
    (ROOT / "examples" / "_rec.html").write_text(
        '<!doctype html><body style="margin:0;background:#3b3a36"><object data="maze.svg" type="image/svg+xml"></object></body>')
    with sync_playwright() as p:
        b = p.chromium.launch()
        ctx = b.new_context(viewport={"width": 452, "height": 308}, record_video_dir=str(tmp),
                            record_video_size={"width": 452, "height": 308})
        pg = ctx.new_page()
        pg.goto(f"http://127.0.0.1:{srv.server_port}/_rec.html")
        time.sleep(seconds)
        ctx.close()
        b.close()
    (ROOT / "examples" / "_rec.html").unlink()
    video = next(tmp.glob("*.webm"))
    out = ROOT / "docs" / "recording.webp"
    out.parent.mkdir(exist_ok=True)
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-i", str(video), "-vf", "fps=12", "-c:v", "libwebp_anim",
                    "-lossless", "0", "-q:v", "70", "-loop", "0", str(out)], check=True)
    shutil.rmtree(tmp)
    print(f"wrote {out} ({out.stat().st_size / 1024:.0f} KB)")


if __name__ == "__main__":
    main(*(float(a) for a in sys.argv[1:]))
