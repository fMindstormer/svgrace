"""Run a compiled SVG in a real browser engine and compare what its timing computed with Dijkstra.

The SVG has no script. The checker only reads when each timed element began
(SVGAnimationElement.getStartTime). Clocked SVGs run in real time; their answers are counted in clock
ticks from the moment the start cell was reached. The engine is Chromium, Firefox or WebKit, as
Playwright builds them, or Safari through safaridriver (browser.py).
"""
import time

from .maze import dijkstra, shortest_path_cells

READ = """n => {
  const t = id => { const el = document.getElementById(id);
    try { return el.getStartTime(); } catch (e) { return null; } };
  const out = {R: [], T: []};
  for (let i = 0; i < n; i++) { out.R.push(t('R' + i)); out.T.push(t('T' + i)); }
  return out; }"""


def duration(m, info):
    """How long, in document seconds, until the trace has certainly finished."""
    dist = dijkstra(m, m.start)
    path, _ = shortest_path_cells(m)
    return info["start_at"] + info["tick"] * (max(dist) + 2) + info["trace_after"] + len(path) * (info["dt"] + 0.05) + 1.5


def run(page, svg_text, m, info, mode="realtime", poll=2.0):
    """Start times read back from the engine: (R list, T list), None where an element never began.

    paused: the clock is paused as soon as the document has loaded and the times are read then, which only
    syncbase timing can answer, since it is resolved ahead of the clock. realtime: the clock runs until the
    trace has certainly finished, and the times are read every `poll` seconds, keeping each element's latest
    answer. Reading only at the end is not enough: Firefox stops reporting an element's start time once its
    interval has ended. Reading too often is not either: every 0.5 s, reading a 24x16 maze held up Firefox's
    main thread enough that clocked snaps missed their tick. Each R interval lasts the trail (6 s), so
    reading every 2 s still sees every one."""
    page.set_content(svg_text)
    if mode == "paused":
        page.evaluate("() => document.querySelector('svg').pauseAnimations()")
        got = page.evaluate(READ, m.cells)
        return got["R"], got["T"]
    stop = duration(m, info)
    R, T = [None] * m.cells, [None] * m.cells
    wall = time.time()
    while True:
        now = page.evaluate("() => document.querySelector('svg').getCurrentTime()")
        got = page.evaluate(READ, m.cells)
        R = [new if new is not None else old for new, old in zip(got["R"], R)]
        T = [new if new is not None else old for new, old in zip(got["T"], T)]
        if now >= stop:
            return R, T
        time.sleep(min(poll, stop - now))
        if time.time() - wall > 3 * stop + 30:
            raise TimeoutError("the document clock did not advance")


def compare(m, info, got_R, got_T):
    """A list of problems; empty when the engine computed exactly what Dijkstra says.

    Each cell's reach time, rounded to whole ticks after the start cell's, must equal its cheapest cost,
    and the trace must light exactly the cells on cheapest routes. How far the engine's times sat off the
    tick grid is recorded as worst_offset; past half a tick, a snap can land on the wrong tick."""
    tick = info["tick"]
    dist = dijkstra(m, m.start)
    path, total = shortest_path_cells(m)
    problems = []
    t0 = got_R[m.start]
    if t0 is None:
        return ["the start cell was never reached"]
    worst = 0.0
    for i in range(m.cells):
        r = got_R[i]
        if r is None:
            problems.append(f"cell {m.xy(i)} never reached")
            continue
        ticks = round((r - t0) / tick)              # the answer: a whole number of ticks
        worst = max(worst, abs(r - t0 - ticks * tick))   # how far off the tick grid the engine's clock was
        if ticks != dist[i]:
            problems.append(f"cell {m.xy(i)} reached {ticks} ticks after the start, expected {dist[i]}")
    lit = {i for i in range(m.cells) if got_T[i] is not None}
    if lit != path:
        problems.append(f"traced {len(lit)} cells, expected {len(path)}: "
                        f"extra {sorted(m.xy(i) for i in lit - path)[:5]}, missing {sorted(m.xy(i) for i in path - lit)[:5]}")
    info["worst_offset"] = worst
    return problems
