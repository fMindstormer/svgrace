"""python -m svgrace build  W H --seed S --out maze.svg     compile a random maze
   python -m svgrace check  W H --seeds N [--mode paused|realtime] [--engine chromium|firefox|webkit|safari] [--align]
                                                             compile and verify N random mazes in a browser engine, or
                                                             with --align, N random pairs of strings of lengths W and H
   python -m svgrace align  A B --out align.svg             compile the edit distance between strings A and B
   --hoist off                                               any of them in the earlier form, with each cell's
                                                             reach and trace timing on the cell"""
import argparse
import sys
import time

from .align import alignment_cells, random_pair
from .browser import ENGINES
from .compile import compile_align, compile_svg
from .maze import generate, shortest_path_cells


def main(argv=None):
    ap = argparse.ArgumentParser(prog="python -m svgrace")
    ap.add_argument("command", choices=["build", "check", "align"])
    ap.add_argument("args", nargs=2, metavar="W H | A B")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--seeds", type=int, default=1)
    ap.add_argument("--loops", type=float, default=0.15)
    ap.add_argument("--tick", type=float, default=0.1)
    ap.add_argument("--mode", choices=["paused", "realtime"], default="realtime")
    ap.add_argument("--timing", choices=["clocked", "syncbase"], default="clocked")
    ap.add_argument("--engine", choices=list(ENGINES), default="chromium")
    ap.add_argument("--align", action="store_true")
    ap.add_argument("--hoist", choices=["on", "off"], help="the reach and trace timing on one invisible element "
                    "(default: the compiler's)")
    ap.add_argument("--alphabet", default="ACGT")
    ap.add_argument("--out")
    a = ap.parse_args(argv)
    hoist = {} if a.hoist is None else {"hoist": a.hoist == "on"}

    if a.command == "align":
        s, t = a.args
        out = a.out or "align.svg"
        svg, timing = compile_align(s, t, tick=a.tick, timing=a.timing, **hoist,
                                    title=f"The edit distance between {s} and {t}, found by animation timing alone")
        open(out, "w").write(svg)
        cells, total = alignment_cells(s, t)
        print(f"wrote {out}: {len(svg) / 1024:.1f} KB, {(len(s) + 1) * (len(t) + 1)} cells, {timing['edges']} steps, "
              f"{timing['elements']} timed elements; edit distance {total} ({len(cells)} cells on cheapest alignments)")
        return 0
    width, height = map(int, a.args)
    if a.command == "build":
        m = generate(width, height, a.seed, a.loops)
        out = a.out or "maze.svg"
        svg, timing = compile_svg(m, tick=a.tick, timing=a.timing, **hoist, title=f"A {width}x{height} maze that finds its own cheapest route")
        open(out, "w").write(svg)
        path, total = shortest_path_cells(m)
        print(f"wrote {out}: {len(svg) / 1024:.1f} KB, {m.cells} cells, {timing['edges']} passages each way, "
              f"{timing['elements']} timed elements; cheapest route costs {total} "
              f"({len(path)} cells on cheapest routes)")
        return 0

    from .browser import launch
    from .check import compare, compare_align, run, run_align
    bad = 0
    with launch(a.engine) as browser:
        version = browser.version
        for seed in range(a.seed, a.seed + a.seeds):
            page = browser.new_page()
            t = time.time()
            if a.align:
                s1, s2 = random_pair(width, height, seed, a.alphabet)
                svg, timing = compile_align(s1, s2, tick=a.tick, timing=a.timing, **hoist)
                R, T, shown = run_align(page, svg, s1, s2, timing, a.mode)
                problems = compare_align(s1, s2, timing, R, T, shown)
                what = f"{s1 or '(empty)'} / {s2 or '(empty)'}, readout {shown}"
            else:
                m = generate(width, height, seed, a.loops)
                svg, timing = compile_svg(m, tick=a.tick, timing=a.timing, **hoist)
                R, T = run(page, svg, m, timing, a.mode)
                problems = compare(m, timing, R, T)
                what = f"{m.cells} cells"
            page.close()
            bad += bool(problems)
            print(f"seed {seed}: {'OK' if not problems else 'FAIL'} ({time.time() - t:.1f} s, {what}, {timing['elements']} elements, largest offset from the tick grid {timing.get('worst_offset', 0) * 1000:.0f} ms)"
                  + "".join(f"\n    {x}" for x in problems[:6]))
    print(f"{a.seeds - bad} of {a.seeds} {'alignments' if a.align else 'mazes'} computed exactly ({a.timing} timing, {a.mode}, {ENGINES[a.engine]} {version})")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
