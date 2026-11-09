"""Compile a shortest-path race into an SVG whose animation timing runs it. There is no script.

The race runs on a directed graph whose edges cost whole numbers of ticks; a maze and an alignment of two
strings are two such graphs. Every number the SVG computes is a time, counted in ticks of one clock
animation. In a maze, an edge costs the cell it enters, so each node can take its minimum first and pay
that cost once. Per node i whose incoming edges all cost the same, c:

  min    M<i>   begins at the first "R<j>.beginEvent" among i's predecessors j. A begin list takes its
                earliest instance, so this is the min in Dijkstra's relaxation, run by the engine.
  delay  D<i>   begins with M<i> and runs c - 3/4 ticks;
  snap   S<i>   begins when D<i> ends and is ended by the next clock tick, so i is reached exactly
                c ticks after its first predecessor, whatever the frame timing;
  reach  R<i>   begins when S<i> ends: node i's cheapest cost from the source, in ticks.

Where the edges into i cost different amounts (an alignment's diagonal), each edge pays before the min:

  claim  C<e>   begins when j is reached and runs cost(e) - 3/4 ticks, for e = j -> i;
  snap   S<i>   begins when the first of i's claims ends and is ended by the next clock tick.

Every cost is at least one tick, so a delay never runs out before its snap's tick. Per edge e = j -> i:

  winner W<e>   begins when j is reached and is ended by "M<i> + 1/4 tick" (with claims: begins when C<e>
                ends and is ended by "S<i> + 1/2 tick"). An element only ends at a time after its begin,
                and restart="never" lets it begin once, so W<e> ends (fires) only if j's claim on i was
                among the first to arrive: only if j is on a cheapest way into i.
  relay  X<e>   is armed by W<e>'s end and fired by the trace reaching i; the trace then lights j.

The trace T starts at the sink after it is reached and walks back along winning edges only, so it lights
exactly the nodes that lie on some cheapest route. Everything is event-based ("R5.beginEvent"): a time
exists only once its event has fired, so the engine settles nodes in clock order, the way Dijkstra's
priority queue would. (timing="syncbase" writes "R5.begin+0.3s" instead, with no clock: exact, but
Chromium resolves such times ahead of the clock at load, at a cost that grows exponentially with the maze,
unless the nodes come in an order where each follows all its predecessors, as an alignment's can.)

With hoist=True, R and T animate the invisible element too, next to the rest of the timing, and each shape
shows a copy that begins with them. WebKit's syncbase alignments were then exact in 60 of 60; with R and T
on the shapes, in 1 to 6 of 30 in each of five runs, its traces lighting extra cells. Alignments are
hoisted; a maze keeps its published form.
"""
from html import escape

from .maze import Maze

PALETTE = {1: "#f2efe6", 2: "#d9cfb3", 3: "#b6a47c"}       # terrain: cost 1, 2, 3
WALL = "#3b3a36"
TRAIL = "#fff3b0;#f4a261;#2a9d8f;#22577a"                   # just reached -> settled long ago
PATH = "#ffd166"


def fmt(t):
    s = f"{t:.4f}".rstrip("0").rstrip(".")
    return s or "0"


def race(nodes, edges, cost, source, sink, tick=0.1, trace_after=0.6, dt=0.05, trail=6.0, timing="clocked",
         start_ticks=10, hoist=False):
    """The race on a graph of `nodes` nodes, whose edge e = (j, i) costs cost[e] ticks: marks[i], node i's
    reach and trace animations (of a fill), to put inside the shape that shows it; the timing-only elements;
    and the timing parameters the checker needs."""
    into = {i: [] for i in range(nodes)}       # edges e = j -> i, by i
    out_of = {i: [] for i in range(nodes)}     # edges e = j -> i, by j
    for e, (j, i) in enumerate(edges):
        into[i].append((e, j))
        out_of[j].append((e, i))
    single = [len({cost[e] for e, _ in into[i]}) == 1 for i in range(nodes)]    # one price to enter i
    clocked = timing == "clocked"
    b, en = (".beginEvent", ".endEvent") if clocked else (".begin", ".end")

    def claim(e, j):        # syncbase mode only: when j's claim on i arrives
        return f"R{j}{b}+{fmt(cost[e] * tick)}s"

    marks, g = [], []       # g: the timing only, for an invisible element
    for i in range(nodes):
        if i == source:
            begin = f"{fmt(start_ticks * tick)}s"
        else:
            begin = (f"S{i}{en}" if clocked else "; ".join(claim(e, j) for e, j in into[i])) if into[i] else "indefinite"
        tbegin = (f"R{i}{b}+{fmt(trace_after)}s" if i == sink
                  else "; ".join(f"X{e}{en}" for e, k in out_of[i] if k != source) or "indefinite")
        r, t = f'id="R{i}" ', f'id="T{i}" '
        if hoist:
            g.append(f'<set {r}attributeName="x" to="0" begin="{begin}" restart="never"/>'
                     f'<set {t}attributeName="x" to="0" begin="{tbegin}" restart="never"/>')
            r, t, begin, tbegin = "", "", f"R{i}{b}", f"T{i}{b}"
        marks.append(f'<animate {r}attributeName="fill" values="{TRAIL}" keyTimes="0;0.06;0.35;1" '
                     f'dur="{fmt(trail)}s" fill="freeze" begin="{begin}" restart="never"/>'
                     f'<set {t}attributeName="fill" to="{PATH}" begin="{tbegin}" restart="never"/>')

    # the clock, delays, snaps, winner gates and trace relays
    if clocked:
        g.append(f'<animate id="CLK" attributeName="y" values="0;0" dur="{fmt(tick)}s" begin="0s" repeatCount="indefinite"/>')
        for i in range(nodes):
            if i == source or not into[i]:
                continue
            if single[i]:
                g.append(f'<set id="M{i}" attributeName="x" to="0" begin="{"; ".join(f"R{j}{b}" for _, j in into[i])}" restart="never"/>')
                g.append(f'<set id="D{i}" attributeName="x" to="0" begin="M{i}{b}" dur="{fmt((cost[into[i][0][0]] - 0.75) * tick)}s" restart="never"/>')
                g.append(f'<set id="S{i}" attributeName="x" to="0" begin="D{i}{en}" end="CLK.repeatEvent" restart="never"/>')
            else:
                for e, j in into[i]:
                    g.append(f'<set id="C{e}" attributeName="x" to="0" begin="R{j}{b}" dur="{fmt((cost[e] - 0.75) * tick)}s" restart="never"/>')
                g.append(f'<set id="S{i}" attributeName="x" to="0" begin="{"; ".join(f"C{e}{en}" for e, _ in into[i])}" end="CLK.repeatEvent" restart="never"/>')
    for e, (j, i) in enumerate(edges):
        if i == source:   # the trace never needs to leave the source
            continue
        if not clocked:   # j wins i if its claim arrived no later than i was reached
            g.append(f'<set id="W{e}" attributeName="x" to="0" begin="{claim(e, j)}" end="R{i}{b}+{fmt(tick / 4)}s" restart="never"/>')
        elif single[i]:   # j wins i if j was reached no later than i's first predecessor
            g.append(f'<set id="W{e}" attributeName="x" to="0" begin="R{j}{b}" end="M{i}{b}+{fmt(tick / 4)}s" restart="never"/>')
        else:             # j wins i if its claim arrived on the same tick as i's first claim
            g.append(f'<set id="W{e}" attributeName="x" to="0" begin="C{e}{en}" end="S{i}{b}+{fmt(tick / 2)}s" restart="never"/>')
        g.append(f'<set id="X{e}" attributeName="x" to="0" begin="W{e}{en}" end="T{i}{b}+{fmt(dt)}s" restart="never"/>')
    info = dict(tick=tick, start_at=start_ticks * tick, trace_after=trace_after, dt=dt, edges=len(edges), timing=timing)
    return marks, "".join(g), info


def finish(parts, info):
    text = "".join(parts)
    info["elements"] = text.count("<set ") + text.count("<animate ")
    return text, info


def compile_svg(m: Maze, tick=0.1, trace_after=0.6, dt=0.05, cell=18, margin=10, trail=6.0, title=None,
                timing="clocked", start_ticks=10):
    """The maze's SVG text, and the timing parameters the checker needs. Entering a cell costs its terrain."""
    W, H = m.width, m.height
    size_w, size_h = W * cell + 2 * margin, H * cell + 2 * margin
    edges = m.directed_edges()
    marks, gates, info = race(m.cells, edges, [m.cost[i] for _, i in edges], m.start, m.exit, tick, trace_after, dt,
                              trail, timing, start_ticks)
    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {size_w} {size_h}" width="{size_w}" '
             f'height="{size_h}">']
    if title:
        parts.append(f"<title>{title}</title>")
    parts.append(f'<rect width="{size_w}" height="{size_h}" fill="{WALL}"/>')

    for i in range(m.cells):
        x, y = m.xy(i)
        parts.append(f'<rect x="{margin + x * cell}" y="{margin + y * cell}" width="{cell}" height="{cell}" '
                     f'fill="{PALETTE[m.cost[i]]}">{marks[i]}</rect>')

    lines = []
    for i in range(m.cells):
        x, y = m.xy(i)
        px, py = margin + x * cell, margin + y * cell
        if x + 1 < W and (i, i + 1) not in m.passages:
            lines.append(f"M{px + cell} {py}v{cell}")
        if y + 1 < H and (i, i + W) not in m.passages:
            lines.append(f"M{px} {py + cell}h{cell}")
    lines.append(f"M{margin} {margin}h{W * cell}v{H * cell}h{-W * cell}z")
    parts.append(f'<path d="{"".join(lines)}" stroke="{WALL}" stroke-width="3" stroke-linecap="square" fill="none"/>')
    for i, label in ((m.start, "S"), (m.exit, "E")):
        x, y = m.xy(i)
        parts.append(f'<text x="{margin + x * cell + cell / 2}" y="{margin + y * cell + cell * 0.72}" '
                     f'font-family="sans-serif" font-size="{cell * 0.62:.0f}" font-weight="bold" '
                     f'text-anchor="middle" fill="{WALL}">{label}</text>')
    parts.append(f'<rect width="0" height="0">{gates}</rect>')
    parts.append("</svg>")
    return finish(parts, info)


def compile_align(a, b, tick=0.1, trace_after=0.6, dt=0.05, cell=24, margin=10, trail=6.0, title=None,
                  timing="clocked", start_ticks=10, hoist=True):
    """The SVG text of the race that aligns a (down the left edge) with b (along the top), and the timing
    parameters the checker needs. Cell (i, j) is node i * (len(b) + 1) + j, and is reached at the edit
    distance between a[:i] and b[:j], in ticks. The clocked build needs every step to cost a tick or more,
    so there each step costs one more per letter it consumes: every walk to (i, j) consumes i + j letters,
    so that adds the same i + j to all of them (info["shift"] is 1) and the cheapest walks stay the same."""
    n, m = len(a), len(b)
    cols, s = m + 1, int(timing == "clocked")
    steps = []
    for k in range((n + 1) * cols):
        i, j = divmod(k, cols)
        if i:
            steps.append((k - cols, k, 1 + s))                                # delete a[i - 1]
        if j:
            steps.append((k - 1, k, 1 + s))                                   # insert b[j - 1]
        if i and j:
            steps.append((k - cols - 1, k, (a[i - 1] != b[j - 1]) + 2 * s))   # keep a[i - 1], or substitute b[j - 1]
    sink = (n + 1) * cols - 1
    marks, gates, info = race(sink + 1, [(j, i) for j, i, _ in steps], [c for *_, c in steps], 0, sink, tick,
                              trace_after, dt, trail, timing, start_ticks, hoist)
    info.update(shift=s, cell=cell)
    x0, y0 = margin + cell, margin + cell                 # the strings take the first column and row
    size_w, size_h = x0 + cols * cell + margin, y0 + (n + 1) * cell + margin
    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {size_w} {size_h}" width="{size_w}" '
             f'height="{size_h}">']
    if title:
        parts.append(f"<title>{escape(title)}</title>")
    parts.append(f'<rect width="{size_w}" height="{size_h}" fill="{WALL}"/>')
    for k in range(sink + 1):
        i, j = divmod(k, cols)
        parts.append(f'<rect x="{x0 + j * cell + 1}" y="{y0 + i * cell + 1}" width="{cell - 2}" height="{cell - 2}" '
                     f'fill="{PALETTE[1]}">{marks[k]}</rect>')
    # a diagonal stroke where the letters match: the free step into that cell
    free = "".join(f"M{x0 + j * cell + 5} {y0 + i * cell + 5}l{cell - 10} {cell - 10}" for i in range(1, n + 1)
                   for j in range(1, cols) if a[i - 1] == b[j - 1])
    if free:
        parts.append(f'<path d="{free}" stroke="{WALL}" stroke-opacity="0.45" stroke-width="2" stroke-linecap="round" fill="none"/>')
    font = f'font-family="monospace" font-size="{cell * 0.62:.0f}" font-weight="bold" text-anchor="middle"'
    parts.append(f'<g {font} fill="{PALETTE[1]}">')
    parts += [f'<text x="{margin + cell / 2}" y="{y0 + i * cell + cell * 0.72}">{escape(a[i - 1])}</text>' for i in range(1, n + 1)]
    parts += [f'<text x="{x0 + j * cell + cell / 2}" y="{margin + cell * 0.72}">{escape(b[j - 1])}</text>' for j in range(1, cols)]
    parts.append("</g>")
    # the readout, in the corner cell: a column of numbers behind a window, moved up one number per tick from
    # the shift (n + m ticks after the start) and frozen when the corner is reached, so it shows the distance.
    # It starts a quarter tick early, so the corner's frame lag (under 3/4 tick) never reaches the next number.
    top = max(n, m)
    reached = f"R{sink}.beginEvent" if s else f"R{sink}.begin"
    parts.append(f'<svg x="{x0 + m * cell}" y="{y0 + n * cell}" width="{cell}" height="{cell}"><g id="readout" {font} fill="{WALL}">'
                 f'<animateTransform attributeName="transform" type="translate" calcMode="discrete" '
                 f'values="{";".join(f"0 {-(v + 1) * cell}" for v in range(top + 1))}" dur="{fmt((top + 1) * tick)}s" '
                 f'begin="{fmt((start_ticks + s * (n + m) - 0.25) * tick)}s" end="{reached}" fill="freeze" restart="never"/>'
                 + "".join(f'<text x="{cell / 2}" y="{(v + 1.72) * cell}">{v}</text>' for v in range(top + 1)) + "</g></svg>")
    parts.append(f'<rect width="0" height="0">{gates}</rect>')
    parts.append("</svg>")
    return finish(parts, info)
