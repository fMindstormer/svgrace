"""Fast checks: the reference, and small mazes in both timing modes in headless Chromium."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from svgrace import compile_svg, dijkstra, generate, shortest_path_cells  # noqa: E402
from svgrace.check import compare, run  # noqa: E402


def test_reference_is_consistent():
    """Forward and backward distances agree on the total, and the route set contains start and exit."""
    for seed in range(20):
        m = generate(12, 9, seed)
        a = dijkstra(m, m.start)
        b = dijkstra(m, m.exit, reverse=True)
        path, total = shortest_path_cells(m)
        assert a[m.exit] == total == b[m.start]
        assert m.start in path and m.exit in path


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
