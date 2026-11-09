"""Load times of syncbase alignment SVGs, with their elements in the compiler's order and reversed.

The compiler writes the cells row by row and their gates in the same order. Every step of an alignment goes
down or right, so that is a topological order: each element comes after every element its begin depends on.
Reversing it changes nothing else in the file. Each file runs in its own process and is killed at the limit,
as in tools/cliff.py. The strings are random over ACGT, then two pairs with many cheapest alignments; clocked
builds are timed for comparison.

  python tools/order.py [limit in seconds, default 60] [engine, default chromium]
"""
import re
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))
from cliff import ENGINES, timed  # noqa: E402
from svgrace import compile_align, random_pair  # noqa: E402

CASES = [(f"random, {n} and {n}", *random_pair(n, n, 0)) for n in (4, 6, 8, 10, 12, 16, 24, 32, 48, 64)] + [
    ("AB×32 and BA×32", "AB" * 32, "BA" * 32), ("A×64 and A×65", "A" * 64, "A" * 65)]
OPEN = '<rect width="0" height="0">'


def reverse(svg):
    """The same file with the cells, and the timing-only elements, in reverse document order."""
    cells = re.findall(r'<rect x="[^>]*>.*?</rect>', svg)
    i, j = svg.index(cells[0]), svg.index(cells[-1]) + len(cells[-1])
    svg = svg[:i] + "".join(cells[::-1]) + svg[j:]
    k, e = svg.rindex(OPEN) + len(OPEN), svg.rindex("</rect></svg>")
    gates = re.findall(r"<(?:set|animate) [^>]*/>", svg[k:e])
    assert "".join(gates) == svg[k:e]
    return svg[:k] + "".join(gates[::-1]) + svg[e:]


def main(limit=60.0, engine="chromium"):
    tmp = Path(tempfile.mkdtemp())
    versions, slow = {}, set()
    rows = []
    for k, (label, a, b) in enumerate(CASES):
        row = []
        for kind in ("syncbase", "reversed", "clocked"):
            if kind in slow:
                row.append("not run")
                continue
            svg = compile_align(a, b, timing="clocked" if kind == "clocked" else "syncbase")[0]
            (tmp / f"{k}-{kind}.svg").write_text(reverse(svg) if kind == "reversed" else svg)
            row.append(timed(engine, tmp / f"{k}-{kind}.svg", limit, versions))
            slow |= {kind} if "over" in row[-1] else set()
        rows.append(f"| {label} | {(len(a) + 1) * (len(b) + 1):,} | " + " | ".join(row) + " |")
        print(rows[-1], file=sys.stderr, flush=True)
    print(f"| Strings ({ENGINES[engine]} {versions.get(engine, '')}) | Cells | Syncbase, row by row | Syncbase, reversed | Clocked |")
    print("|---|---|---|---|---|")
    print("\n".join(rows))


if __name__ == "__main__":
    main(*([float(sys.argv[1])] if sys.argv[1:] else []), *sys.argv[2:3])
