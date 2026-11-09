"""Run a compiled SVG in a real browser engine and compare what its timing computed with the reference:
Dijkstra for a maze, the edit-distance table for an alignment.

The SVG has no script. The checker only reads when each timed element began
(SVGAnimationElement.getStartTime). Clocked SVGs run in real time; their answers are counted in clock
ticks from the moment the start cell was reached. The engine is Chromium, Firefox or WebKit, as
Playwright builds them.
"""
import time

from .align import alignment_cells, edit_distance, prefix_distances
from .maze import dijkstra, shortest_path_cells

ENGINES = {"chromium": "Chromium", "firefox": "Firefox", "webkit": "WebKit"}

READ = """n => {
  const t = id => { const el = document.getElementById(id);
    try { return el.getStartTime(); } catch (e) { return null; } };
  const out = {R: [], T: []};
  for (let i = 0; i < n; i++) { out.R.push(t('R' + i)); out.T.push(t('T' + i)); }
  return out; }"""


def duration(m, info):
    """How long, in document seconds, until the trace has certainly finished."""
    path, _ = shortest_path_cells(m)
    return finished(dijkstra(m, m.start), path, info)


def finished(dist, path, info):
    return info["start_at"] + info["tick"] * (max(dist) + 2) + info["trace_after"] + len(path) * (info["dt"] + 0.05) + 1.5


def run(page, svg_text, m, info, mode="realtime", poll=2.0):
    return read(page, svg_text, m.cells, duration(m, info), mode, poll)


def read(page, svg_text, nodes, stop, mode="realtime", poll=2.0):
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
        got = page.evaluate(READ, nodes)
        return got["R"], got["T"]
    R, T = [None] * nodes, [None] * nodes
    wall = time.time()
    while True:
        now = page.evaluate("() => document.querySelector('svg').getCurrentTime()")
        got = page.evaluate(READ, nodes)
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
    path, _ = shortest_path_cells(m)
    return compare_race(dijkstra(m, m.start), path, m.start, m.xy, info, got_R, got_T)


def compare_race(dist, path, source, where, info, got_R, got_T):
    tick = info["tick"]
    problems = []
    t0 = got_R[source]
    if t0 is None:
        return ["the start cell was never reached"]
    worst = 0.0
    for i, r in enumerate(got_R):
        if r is None:
            problems.append(f"cell {where(i)} never reached")
            continue
        ticks = round((r - t0) / tick)              # the answer: a whole number of ticks
        worst = max(worst, abs(r - t0 - ticks * tick))   # how far off the tick grid the engine's clock was
        if ticks != dist[i]:
            problems.append(f"cell {where(i)} reached {ticks} ticks after the start, expected {dist[i]}")
    lit = {i for i, t in enumerate(got_T) if t is not None}
    if lit != path:
        problems.append(f"traced {len(lit)} cells, expected {len(path)}: "
                        f"extra {sorted(where(i) for i in lit - path)[:5]}, missing {sorted(where(i) for i in path - lit)[:5]}")
    info["worst_offset"] = worst
    return problems


READOUT = """() => { const l = document.getElementById('readout').transform.animVal;
  return l.numberOfItems ? l.getItem(0).matrix.f : 0; }"""


def expected_align(a, b, info):
    """Each cell's reach time in ticks (with the clocked build's shift), and the cells on cheapest alignments,
    as node numbers."""
    D, cols = prefix_distances(a, b), len(b) + 1
    dist = [D[i][j] + info["shift"] * (i + j) for i in range(len(a) + 1) for j in range(cols)]
    cells, _ = alignment_cells(a, b)
    return dist, {i * cols + j for i, j in cells}


def run_align(page, svg_text, a, b, info, mode="realtime", poll=2.0):
    """(R list, T list, the number the readout shows at the end). The readout is read in real time only
    (None when paused): with the clock paused, seeking past the end left Chromium's animated value at its base."""
    stop = finished(*expected_align(a, b, info), info)
    R, T = read(page, svg_text, (len(a) + 1) * (len(b) + 1), stop, mode, poll)
    return R, T, None if mode == "paused" else round(-page.evaluate(READOUT) / info["cell"]) - 1


def compare_align(a, b, info, got_R, got_T, shown):
    """A list of problems; empty when the corner's reach time and the readout give the edit distance, every
    cell is reached at the distance between the prefixes, and the trace lights exactly the cells on cheapest
    alignments."""
    dist, path = expected_align(a, b, info)
    n, m = len(a), len(b)
    problems = compare_race(dist, path, 0, lambda k: divmod(k, m + 1), info, got_R, got_T)
    total = edit_distance(a, b)
    if got_R[0] is not None and got_R[-1] is not None:
        corner = round((got_R[-1] - got_R[0]) / info["tick"]) - info["shift"] * (n + m)
        if corner != total:
            problems.insert(0, f"the corner gives distance {corner}, expected {total}")
    if shown is not None and shown != total:
        problems.insert(0, f"the readout shows {shown}, expected {total}")
    return problems
