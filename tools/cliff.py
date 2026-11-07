"""Load times of syncbase timing, the cliff reported to Chromium, in Playwright's Chromium, Firefox and WebKit.

Writes the files attached to the report to upstream/chromium/, then times every case in every engine: from
handing the document over until it has loaded and its page answers a script. Each case runs in its own
process and is killed at the limit, because a page stuck in the cliff does not answer anything.

  python tools/cliff.py [limit in seconds, default 100]
"""
import os
import signal
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from svgrace import compile_svg, generate  # noqa: E402

ENGINES = {"chromium": "Chromium", "firefox": "Firefox", "webkit": "WebKit"}


def grid(k):
    """The smallest form of the cliff: k x k <animate>s, each beginning 0.1 s after the earliest of its
    neighbours, and nothing else. The far corner begins at (2k - 2) * 0.1 s."""
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" width="10" height="10"><title>{k}x{k} grid of syncbase '
           'begin lists</title><rect width="10" height="10" fill="teal">']
    for y in range(k):
        for x in range(k):
            nb = [f"c{a}_{b}.begin+0.1s" for a, b in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)) if 0 <= a < k and 0 <= b < k]
            out.append(f'<animate id="c{x}_{y}" attributeName="x" to="1" dur="1s" '
                       f'begin="{"0s" if x == y == 0 else "; ".join(nb)}" restart="never"/>')
    return "".join(out) + "</rect></svg>\n"


def maze(w, h, loops, timing):
    return compile_svg(generate(w, h, 0, loops=loops), timing=timing,
                       title=f"A {w}x{h} maze, {timing} timing")[0]


# (row label, kind of timing, file text, attachment name or None)
CASES = [
    ("perfect maze 24×16 (384 cells)", "syncbase", maze(24, 16, 0, "syncbase"), None),
    ("perfect maze 32×20 (640 cells)", "syncbase", maze(32, 20, 0, "syncbase"), None),
    ("braid maze 12×9 (108 cells)", "syncbase", maze(12, 9, 0.15, "syncbase"), None),
    ("braid maze 14×10 (140 cells)", "syncbase", maze(14, 10, 0.15, "syncbase"), None),
    ("braid maze 16×11 (176 cells)", "syncbase", maze(16, 11, 0.15, "syncbase"), "maze-16x11-syncbase.svg"),
    ("the same maze, clocked", "event-based", maze(16, 11, 0.15, "clocked"), "maze-16x11-clocked.svg"),
    ("braid maze 40×30 (1,200 cells), clocked", "event-based", maze(40, 30, 0.15, "clocked"), None),
    ("grid 5×5 (25 animations)", "syncbase", grid(5), "grid-5.svg"),
    ("grid 6×6 (36 animations)", "syncbase", grid(6), "grid-6.svg"),
    ("grid 7×7 (49 animations)", "syncbase", grid(7), "grid-7.svg"),
]


def one(engine, path):
    """Worker: time one file in one engine and print the seconds."""
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        b = getattr(p, engine).launch()
        page = b.new_page()
        text = Path(path).read_text()
        t = time.time()
        page.set_content(text, timeout=0)
        page.evaluate("1")
        print(f"{time.time() - t:.3f} {b.version}")


def main(limit=100.0):
    out = ROOT / "upstream" / "chromium"
    out.mkdir(parents=True, exist_ok=True)
    tmp = Path(tempfile.mkdtemp())
    for i, (_, _, text, name) in enumerate(CASES):
        (tmp / f"{i}.svg").write_text(text)
        if name:
            (out / name).write_text(text)
    times, versions = {}, {}
    for engine in ENGINES:
        for i, (label, *_) in enumerate(CASES):
            pr = subprocess.Popen([sys.executable, "-B", __file__, "--one", engine, str(tmp / f"{i}.svg")],
                                  stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, start_new_session=True)
            try:
                got, err = pr.communicate(timeout=limit)
                seconds, versions[engine] = got.split()
                times[engine, i] = f"{float(seconds):.2f} s"
            except subprocess.TimeoutExpired:
                os.killpg(pr.pid, signal.SIGKILL)
                pr.communicate()
                times[engine, i] = f"**over {limit:.0f} s**"
            except ValueError:
                times[engine, i] = "error: " + err.strip().splitlines()[-1][:80]
            print(f"{engine} {label}: {times[engine, i]}", file=sys.stderr, flush=True)
    print("| File | Timing | " + " | ".join(f"{ENGINES[e]} {versions.get(e, '')}" for e in ENGINES) + " |")
    print("|---|---|" + "---|" * len(ENGINES))
    for i, (label, kind, _, _) in enumerate(CASES):
        print(f"| {label} | {kind} | " + " | ".join(times[e, i] for e in ENGINES) + " |")


if __name__ == "__main__":
    if sys.argv[1:2] == ["--one"]:
        one(*sys.argv[2:4])
    else:
        main(*(float(a) for a in sys.argv[1:]))
