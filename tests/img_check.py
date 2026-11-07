"""The README case: the SVG shown through a plain <img>, where no script can run and the DOM is out of
reach. After the race, the pixels must show gold on exactly the cells that lie on cheapest routes."""
import functools, http.server, sys, tempfile, threading, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from playwright.sync_api import sync_playwright
from svgrace import generate, compile_svg, shortest_path_cells
from svgrace.check import duration

def main(w=24, h=16, seeds=(0, 1, 2), tick=0.1, timing="syncbase", loops=0.0, tag="img", engine="chromium"):
    root = Path(tempfile.mkdtemp())
    class Quiet(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *a): pass
    handler = functools.partial(Quiet, directory=str(root))
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    ok = 0
    with sync_playwright() as p:
        b = getattr(p, engine).launch()
        version = b.version
        for seed in seeds:
            m = generate(w, h, seed, loops=loops)
            svg, info = compile_svg(m, tick=tick, timing=timing)
            (root / f"m{seed}.svg").write_text(svg)
            (root / f"m{seed}.html").write_text(f'<!doctype html><body style="margin:0;background:#fff">' + (f'<img src="m{seed}.svg">' if tag == "img" else f'<object data="m{seed}.svg" type="image/svg+xml"></object>') + '</body>')
            pg = b.new_page(viewport={"width": 1000, "height": 800})
            pg.goto(f"http://127.0.0.1:{srv.server_port}/m{seed}.html")
            time.sleep(duration(m, info) + 1)
            shot = pg.screenshot()
            pg.close()
            from PIL import Image
            import io
            img = Image.open(io.BytesIO(shot)).convert("RGB")
            path, total = shortest_path_cells(m)
            cell, margin = 18, 10
            gold = set()
            for i in range(m.cells):
                x, y = m.xy(i)
                # near the corner: clear of the walls (1.5 px into the cell) and of the S and E labels, whose
                # width depends on the system's sans-serif
                r, g, bl = img.getpixel((margin + x * cell + 3, margin + y * cell + 3))
                if abs(r - 0xff) < 12 and abs(g - 0xd1) < 12 and abs(bl - 0x66) < 12:
                    gold.add(i)
            good = gold == path
            ok += good
            print(f"seed {seed}: <{tag}> shows {len(gold)} gold cells, cheapest routes cover {len(path)}: {'OK' if good else 'MISMATCH'}"
                  + ("" if good else f"\n    missing {sorted(m.xy(i) for i in path - gold)[:5]}, extra {sorted(m.xy(i) for i in gold - path)[:5]}"))
        b.close()
    print(f"{ok} of {len(seeds)} {timing} mazes (loops {loops}) drew exactly the cheapest routes inside an <{tag}> ({engine} {version})")
    return ok == len(seeds)

if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--timing", default="syncbase"); ap.add_argument("--tag", default="img"); ap.add_argument("--engine", default="chromium")
    ap.add_argument("--loops", type=float, default=0.0); ap.add_argument("--tick", type=float, default=0.1)
    ap.add_argument("--size", default="24x16"); ap.add_argument("--seeds", type=int, default=3)
    a = ap.parse_args(); w, h = map(int, a.size.split("x"))
    sys.exit(0 if main(w, h, range(a.seeds), a.tick, a.timing, a.loops, a.tag, a.engine) else 1)
