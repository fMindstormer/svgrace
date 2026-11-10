"""python -m svgrace build  W H --seed S --out maze.svg     compile a random maze
   python -m svgrace check  W H --seeds N [--mode paused|realtime] [--engine chromium|firefox|webkit|safari]
                                                             compile and verify N random mazes in a browser engine"""
import argparse
import sys
import time

from .browser import ENGINES
from .compile import compile_svg
from .maze import generate, shortest_path_cells


def main(argv=None):
    ap = argparse.ArgumentParser(prog="python -m svgrace")
    ap.add_argument("command", choices=["build", "check"])
    ap.add_argument("width", type=int)
    ap.add_argument("height", type=int)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--seeds", type=int, default=1)
    ap.add_argument("--loops", type=float, default=0.15)
    ap.add_argument("--tick", type=float, default=0.1)
    ap.add_argument("--mode", choices=["paused", "realtime"], default="realtime")
    ap.add_argument("--timing", choices=["clocked", "syncbase"], default="clocked")
    ap.add_argument("--engine", choices=list(ENGINES), default="chromium")
    ap.add_argument("--out", default="maze.svg")
    a = ap.parse_args(argv)

    if a.command == "build":
        m = generate(a.width, a.height, a.seed, a.loops)
        svg, timing = compile_svg(m, tick=a.tick, timing=a.timing, title=f"A {a.width}x{a.height} maze that finds its own cheapest route")
        open(a.out, "w").write(svg)
        path, total = shortest_path_cells(m)
        print(f"wrote {a.out}: {len(svg) / 1024:.1f} KB, {m.cells} cells, {timing['edges']} passages each way, "
              f"{timing['elements']} timed elements; cheapest route costs {total} "
              f"({len(path)} cells on cheapest routes)")
        return 0

    from .browser import launch
    from .check import run, compare
    bad = 0
    with launch(a.engine) as browser:
        version = browser.version
        for seed in range(a.seed, a.seed + a.seeds):
            page = browser.new_page()
            m = generate(a.width, a.height, seed, a.loops)
            svg, timing = compile_svg(m, tick=a.tick, timing=a.timing)
            t = time.time()
            R, T = run(page, svg, m, timing, a.mode)
            problems = compare(m, timing, R, T)
            page.close()
            bad += bool(problems)
            print(f"seed {seed}: {'OK' if not problems else 'FAIL'} ({time.time() - t:.1f} s, {m.cells} cells, {timing['elements']} elements, largest offset from the tick grid {timing.get('worst_offset', 0) * 1000:.0f} ms)"
                  + "".join(f"\n    {x}" for x in problems[:6]))
    print(f"{a.seeds - bad} of {a.seeds} mazes computed exactly ({a.timing} timing, {a.mode}, {ENGINES[a.engine]} {version})")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
