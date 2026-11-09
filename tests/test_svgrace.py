"""Fast checks: the references, small mazes in both timing modes and alignments of random strings, in headless
Chromium."""
import itertools
import random
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from svgrace import (alignment_cells, compile_align, compile_svg, dijkstra, edit_distance, generate,  # noqa: E402
                     random_pair, shortest_path_cells)
from svgrace.check import compare, compare_align, run, run_align  # noqa: E402


def test_reference_is_consistent():
    """Forward and backward distances agree on the total, and the route set contains start and exit."""
    for seed in range(20):
        m = generate(12, 9, seed)
        a = dijkstra(m, m.start)
        b = dijkstra(m, m.exit, reverse=True)
        path, total = shortest_path_cells(m)
        assert a[m.exit] == total == b[m.start]
        assert m.start in path and m.exit in path


def walks(n, m):
    """Every walk from (0, 0) to (n, m), as its list of cells."""
    if (n, m) == (0, 0):
        return [[(0, 0)]]
    return [w + [(n, m)] for di, dj in ((1, 0), (0, 1), (1, 1)) if n >= di and m >= dj for w in walks(n - di, m - dj)]


def test_alignment_reference_against_every_walk():
    """On short strings, the edit distance is the cheapest of all walks, and the cells on cheapest alignments
    (forward plus backward tables) are the cells of the cheapest walks."""
    assert edit_distance("KITTEN", "SITTING") == 3
    for a, b in itertools.product(["", "A", "AB", "BA", "ABA", "AAB", "BABA"], repeat=2):
        def cost(w):
            return sum(1 if i - k + j - l == 1 else a[i - 1] != b[j - 1] for (k, l), (i, j) in zip(w, w[1:]))
        best = min(cost(w) for w in walks(len(a), len(b)))
        cells, total = alignment_cells(a, b)
        assert edit_distance(a, b) == total == best
        assert cells == {c for w in walks(len(a), len(b)) if cost(w) == best for c in w}


@pytest.fixture(scope="module")
def browser():
    sp = pytest.importorskip("playwright.sync_api")
    with sp.sync_playwright() as p:
        b = p.chromium.launch()
        yield b
        b.close()


@pytest.mark.parametrize("seed", range(10))
def test_syncbase_small_mazes_with_loops(browser, seed):
    """Exact times, read with the clock paused: small enough that Chromium's ahead-of-time resolution stays fast."""
    m = generate(10, 7, seed)
    svg, info = compile_svg(m, timing="syncbase")
    page = browser.new_page()
    R, T = run(page, svg, m, info, mode="paused")
    page.close()
    assert compare(m, info, R, T) == []


@pytest.mark.parametrize("seed", range(2))
def test_clocked_mazes_in_real_time(browser, seed):
    m = generate(10, 7, seed)
    svg, info = compile_svg(m, tick=0.1)
    page = browser.new_page()
    R, T = run(page, svg, m, info, mode="realtime")
    page.close()
    assert compare(m, info, R, T) == []


def pair(seed, longest):
    """Random strings of random lengths, 0 included, over two letters (many ties) or four."""
    rng = random.Random(seed)
    return random_pair(rng.randint(0, longest), rng.randint(0, longest), seed, rng.choice(("AB", "ACGT")))


def check_alignment(browser, a, b, timing, mode):
    svg, info = compile_align(a, b, timing=timing)
    page = browser.new_page()
    R, T, shown = run_align(page, svg, a, b, info, mode)
    page.close()
    n, m = len(a), len(b)
    assert round((R[-1] - R[0]) / info["tick"]) - info["shift"] * (n + m) == edit_distance(a, b)   # the corner
    assert {divmod(k, m + 1) for k, t in enumerate(T) if t is not None} == alignment_cells(a, b)[0]  # the trace
    assert compare_align(a, b, info, R, T, shown) == []     # every cell's time, and the readout in real time


@pytest.mark.parametrize("seed", range(20))
def test_syncbase_alignments(browser, seed):
    """Times read with the clock paused, as Chromium resolved them at load."""
    check_alignment(browser, *pair(seed, 10), "syncbase", "paused")


@pytest.mark.parametrize("seed", range(4))
def test_clocked_alignments_in_real_time(browser, seed):
    check_alignment(browser, *(("KITTEN", "SITTING") if seed == 0 else pair(seed, 8)), "clocked", "realtime")


def test_syncbase_alignment_readout_in_real_time(browser):
    check_alignment(browser, "INTENTION", "EXECUTION", "syncbase", "realtime")
