"""The README case: the SVG shown through a plain <img>, where no script can run and the DOM is out of
reach. After the race, the pixels must show gold on exactly the cells that lie on cheapest routes (with
--align, on cheapest alignments of random strings of lengths W and H)."""
import functools, http.server, sys, tempfile, threading, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from svgrace import generate, compile_align, compile_svg, random_pair, shortest_path_cells
from svgrace.browser import ENGINES, launch
from svgrace.check import duration, expected_align, finished

def main(w=24, h=16, seeds=(0, 1, 2), tick=0.1, timing="syncbase", loops=0.0, tag="img", engine="chromium", align=False,
         hoist=None):
    hoisted = {} if hoist is None else {"hoist": hoist}    # None: the compiler's default
    root = Path(tempfile.mkdtemp())
    class Quiet(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *a): pass
    handler = functools.partial(Quiet, directory=str(root))
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    ok = 0
    with launch(engine) as b:
        version = b.version
        for seed in seeds:
            if align:
                s1, s2 = random_pair(w, h, seed)
                svg, info = compile_align(s1, s2, tick=tick, timing=timing, **hoisted)
                dist, path = expected_align(s1, s2, info)
                wait, c = finished(dist, path, info), info["cell"]
                where = lambda k: divmod(k, len(s2) + 1)
                # near the top right corner: clear of the grid lines, the match strokes and the readout
                spots = [(10 + (j + 1) * c + c - 4, 10 + (i + 1) * c + 4) for i, j in map(where, range(len(dist)))]
            else:
                m = generate(w, h, seed, loops=loops)
                svg, info = compile_svg(m, tick=tick, timing=timing, **hoisted)
                path, total = shortest_path_cells(m)
                wait, where = duration(m, info), m.xy
                # near the corner: clear of the walls (1.5 px into the cell) and of the S and E labels, whose
                # width depends on the system's sans-serif
                spots = [(10 + x * 18 + 3, 10 + y * 18 + 3) for x, y in map(m.xy, range(m.cells))]
            (root / f"m{seed}.svg").write_text(svg)
            (root / f"m{seed}.html").write_text(f'<!doctype html><body style="margin:0;background:#fff">' + (f'<img src="m{seed}.svg">' if tag == "img" else f'<object data="m{seed}.svg" type="image/svg+xml"></object>') + '</body>')
            pg = b.new_page(viewport={"width": 1000, "height": 800})
            pg.goto(f"http://127.0.0.1:{srv.server_port}/m{seed}.html")
            time.sleep(wait + 1)
            shot = pg.screenshot()
            pg.close()
            from PIL import Image
            import io
            img = Image.open(io.BytesIO(shot)).convert("RGB")
            gold = set()
            for i, xy in enumerate(spots):
                r, g, bl = img.getpixel(xy)
                if abs(r - 0xff) < 12 and abs(g - 0xd1) < 12 and abs(bl - 0x66) < 12:
                    gold.add(i)
            good = gold == path
            ok += good
            print(f"seed {seed}: <{tag}> shows {len(gold)} gold cells, cheapest {'alignments' if align else 'routes'} cover {len(path)}: {'OK' if good else 'MISMATCH'}"
                  + ("" if good else f"\n    missing {sorted(where(i) for i in path - gold)[:5]}, extra {sorted(where(i) for i in gold - path)[:5]}"))
    what = f"alignments of {w} and {h} letters" if align else f"mazes (loops {loops})"
    print(f"{ok} of {len(seeds)} {timing} {what} drew exactly the cheapest {'alignments' if align else 'routes'} inside an <{tag}> ({engine} {version})")
    return ok == len(seeds)

if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--timing", default="syncbase"); ap.add_argument("--tag", default="img"); ap.add_argument("--engine", choices=list(ENGINES), default="chromium")
    ap.add_argument("--loops", type=float, default=0.0); ap.add_argument("--tick", type=float, default=0.1)
    ap.add_argument("--size", default="24x16"); ap.add_argument("--seeds", type=int, default=3)
    ap.add_argument("--align", action="store_true")
    ap.add_argument("--hoist", choices=["on", "off"], help="the reach and trace timing on one invisible element (default: the compiler's)")
    a = ap.parse_args(); w, h = map(int, a.size.split("x"))
    sys.exit(0 if main(w, h, range(a.seeds), a.tick, a.timing, a.loops, a.tag, a.engine, a.align,
                       None if a.hoist is None else a.hoist == "on") else 1)
