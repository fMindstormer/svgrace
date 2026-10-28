"""Run a compiled SVG in a real browser engine and compare what its timing computed with Dijkstra.

The SVG has no script. The checker only reads, afterwards, when each timed element began
(SVGAnimationElement.getStartTime). Clocked SVGs run in real time; their answers are counted in clock
ticks from the moment the start cell was reached.
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


def run(page, svg_text, m, info, mode="realtime"):
    """Start times read back from the engine: (R list, T list), None where an element never began."""
    page.set_content(svg_text)
    stop = duration(m, info)
    if mode == "seek":
        page.evaluate(f"() => {{ const s = document.querySelector('svg'); s.pauseAnimations(); s.setCurrentTime({stop}); }}")
    else:
        wall = time.time()
        while (now := page.evaluate("() => document.querySelector('svg').getCurrentTime()")) < stop:
            time.sleep(min(0.5, stop - now))
            if time.time() - wall > 3 * stop + 30:
                raise TimeoutError("the document clock did not advance")
    got = page.evaluate(READ, m.cells)
    return got["R"], got["T"]


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
