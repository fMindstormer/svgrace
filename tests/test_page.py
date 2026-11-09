"""The live page. Its port of the generator and compiler, examples/svgrace.js, must write byte for byte
what svgrace writes, and a maze drawn on the page must find its cheapest route there.

Chromium by default; SVGRACE_ENGINES=chromium,firefox,webkit runs the same tests in each engine."""
import functools
import http.server
import os
import random
import sys
import threading
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from svgrace import Maze, compile_svg, generate, shortest_path_cells  # noqa: E402

EXAMPLES = Path(__file__).resolve().parents[1] / "examples"
TITLE = "A maze that finds its cheapest route with animation timing alone"
CASES = [(24, 16, 3, 0.15), (24, 16, 7, 0.0), (12, 8, 0, 0.15), (16, 11, 42, 0.3), (5, 4, 123, 1.0), (24, 16, 9999, 0.15)]
TO_JS = """([w, h, passages, cost]) => {
  const m = svgrace.maze(w, h);
  for (const [i, j] of passages) m.passages.add(svgrace.key(m, i, j));
  m.cost = cost;
  return m; }"""


@pytest.fixture(scope="module", params=os.environ.get("SVGRACE_ENGINES", "chromium").split(","))
def browser(request):
    sp = pytest.importorskip("playwright.sync_api")
    with sp.sync_playwright() as p:
        b = getattr(p, request.param).launch()
        yield b
        b.close()


@pytest.fixture(scope="module")
def js(browser):
    page = browser.new_page()
    page.add_script_tag(path=str(EXAMPLES / "svgrace.js"))
    yield page
    page.close()


def edited(seed):
    """A generated maze, then edited at random: walls opened and closed, costs repainted."""
    rng = random.Random(seed)
    m = generate(16, 11, seed)
    for _ in range(40):
        i = rng.randrange(m.cells)
        j = i + rng.choice((1, m.width))
        if j < m.cells and (j != i + 1 or (i + 1) % m.width):
            m.passages ^= {(i, j)}
    for _ in range(30):
        m.cost[rng.randrange(1, m.cells)] = rng.choice((1, 2, 3))
    return m


@pytest.mark.parametrize("case", CASES)
def test_generator_matches(js, case):
    w, h, seed, loops = case
    got = js.evaluate("""([w, h, seed, loops]) => { const m = svgrace.generate(w, h, seed, loops);
      return {passages: [...m.passages].map(k => [Math.floor(k / m.cells), k % m.cells]), cost: m.cost}; }""", list(case))
    m = generate(w, h, seed, loops)
    assert sorted(map(tuple, got["passages"])) == sorted(m.passages)
    assert got["cost"] == m.cost


@pytest.mark.parametrize("case", CASES)
def test_compiler_matches(js, case):
    m = generate(*case)
    got = js.evaluate(f"""([w, h, seed, loops, title]) =>
      svgrace.compile(svgrace.generate(w, h, seed, loops), {{tick: 0.12, title}}).svg""", [*case, TITLE])
    assert got == compile_svg(m, tick=0.12, title=TITLE)[0]
    assert js.evaluate("args => svgrace.compile(svgrace.generate(...args)).svg", list(case)) == compile_svg(m)[0]


@pytest.mark.parametrize("seed", range(3))
def test_compiler_matches_on_edited_mazes(js, seed):
    m = edited(seed)
    data = [m.width, m.height, sorted(m.passages), m.cost]
    assert js.evaluate(f"data => svgrace.compile(({TO_JS})(data), {{tick: 0.12}}).svg", data) == compile_svg(m, tick=0.12)[0]
    got = js.evaluate(f"data => {{ const r = svgrace.shortestPathCells(({TO_JS})(data)); return [[...r.cells], r.total]; }}", data)
    path, total = shortest_path_cells(m)
    assert (set(got[0]), got[1]) == (path, total)


def test_the_page_starts_with_maze_svg(js):
    """The maze the page's editor opens with is the one in maze.svg, which examples/build.py writes."""
    svg = js.evaluate("title => svgrace.compile(svgrace.generate(24, 16, 3, 0.15), {tick: 0.12, title}).svg", TITLE)
    assert svg == (EXAMPLES / "maze.svg").read_text()


def test_a_maze_drawn_on_the_page_finds_its_route(browser):
    class Quiet(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *a):
            pass
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(Quiet, directory=str(EXAMPLES)))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    page = browser.new_page(viewport={"width": 800, "height": 900})
    try:
        page.goto(f"http://127.0.0.1:{srv.server_port}/index.html")
        page.click("#edit")
        page.select_option("#size", "12x8")
        page.check("input[value=terrain]", force=True)
        box = page.locator("#editor").bounding_box()
        scale = box["width"] / (12 * 18 + 20)
        for x, y in ((3, 2), (4, 2), (8, 5)):   # paint three cells: each tap moves a cell to the next cost
            page.mouse.click(box["x"] + (10 + x * 18 + 9) * scale, box["y"] + (10 + y * 18 + 9) * scale)
        assert "Your maze" in page.inner_text("#status")
        page.click("#run")
        page.wait_for_function("document.getElementById('status').className.match(/ok|bad/)", timeout=60_000)
        status = page.inner_text("#status")
        drawn = page.evaluate("() => [m.width, m.height, [...m.passages].map(k => [Math.floor(k / m.cells), k % m.cells]), m.cost]")
        built = page.evaluate("() => fetch(document.getElementById('download').href).then(r => r.text())")
    finally:
        page.close()
        srv.shutdown()
    w, h, passages, cost = drawn
    m = Maze(w, h, {tuple(p) for p in passages}, cost)
    assert m.cost != generate(12, 8, 3).cost, "the taps did not repaint any cell"
    assert built == compile_svg(m, tick=0.12, title=TITLE)[0]
    assert "Dijkstra, run by this page, agrees" in status, status
