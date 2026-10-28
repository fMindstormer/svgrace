"""Compile a maze into an SVG whose animation timing finds the cheapest route. There is no script.

Every number the SVG computes is a time, counted in ticks of one clock animation. The cost of a passage
is the cost of the cell it enters, so each cell can take its minimum first and pay its cost once. Per cell i:

  min    M<i>   begins at the first "R<j>.beginEvent" among i's neighbours j. A begin list takes its
                earliest instance, so this is the min in Dijkstra's relaxation, run by the engine.
  delay  D<i>   begins with M<i> and runs cost(i) - 3/4 ticks;
  snap   S<i>   begins when D<i> ends and is ended by the next clock tick, so i is reached exactly
                cost(i) ticks after its first neighbour, whatever the frame timing;
  reach  R<i>   begins when S<i> ends: cell i's cheapest cost from the start, in ticks.

Per passage e = j -> i (both directions of every passage):

  winner W<e>   begins when j is reached and is ended by "M<i> + 1/4 tick". An element only ends at a time
                after its begin, and restart="never" lets it begin once, so W<e> ends (fires) only if j was
                among i's first neighbours to be reached: only if j is on a cheapest way into i.
  relay  X<e>   is armed by W<e>'s end and fired by the trace reaching i; the trace then lights j.

The trace T starts at the exit after it is reached and walks back along winning passages only, so it
lights exactly the cells that lie on some cheapest route. Everything is event-based ("R5.beginEvent"): a
time exists only once its event has fired, so the engine settles cells in clock order, the way Dijkstra's
priority queue would. (timing="syncbase" writes "R5.begin+0.3s" instead, with no clock: exact, but
Chromium resolves such times ahead of the clock at load, at a cost that grows exponentially with the maze.)
"""
from .maze import Maze

PALETTE = {1: "#f2efe6", 2: "#d9cfb3", 3: "#b6a47c"}       # terrain: cost 1, 2, 3
WALL = "#3b3a36"
TRAIL = "#fff3b0;#f4a261;#2a9d8f;#22577a"                   # just reached -> settled long ago
PATH = "#ffd166"


def fmt(t):
    s = f"{t:.4f}".rstrip("0").rstrip(".")
    return s or "0"


def compile_svg(m: Maze, tick=0.1, trace_after=0.6, dt=0.05, cell=18, margin=10, trail=6.0, title=None,
                timing="clocked", start_ticks=10):
    """The SVG text, and the timing parameters the checker needs."""
    W, H = m.width, m.height
    size_w, size_h = W * cell + 2 * margin, H * cell + 2 * margin
    edges = m.directed_edges()
    into = {i: [] for i in range(m.cells)}       # passages e = j -> i, by i
    out_of = {i: [] for i in range(m.cells)}     # passages e = j -> i, by j
    for e, (j, i) in enumerate(edges):
        into[i].append((e, j))
        out_of[j].append((e, i))
    clocked = timing == "clocked"
    b, en = (".beginEvent", ".endEvent") if clocked else (".begin", ".end")

    def claim(e, j, i):        # syncbase mode only: when j's claim on i arrives
        return f"R{j}{b}+{fmt(m.cost[i] * tick)}s"

    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {size_w} {size_h}" width="{size_w}" '
             f'height="{size_h}">']
    if title:
        parts.append(f"<title>{title}</title>")
    parts.append(f'<rect width="{size_w}" height="{size_h}" fill="{WALL}"/>')

    for i in range(m.cells):
        x, y = m.xy(i)
        px, py = margin + x * cell, margin + y * cell
        if i == m.start:
            begin = f"{fmt(start_ticks * tick)}s"
        else:
            begin = (f"S{i}{en}" if clocked else "; ".join(claim(e, j, i) for e, j in into[i])) or "indefinite"
        tbegin = (f"R{i}{b}+{fmt(trace_after)}s" if i == m.exit
                  else "; ".join(f"X{e}{en}" for e, k in out_of[i] if k != m.start) or "indefinite")
        parts.append(
            f'<rect x="{px}" y="{py}" width="{cell}" height="{cell}" fill="{PALETTE[m.cost[i]]}">'
            f'<animate id="R{i}" attributeName="fill" values="{TRAIL}" keyTimes="0;0.06;0.35;1" '
            f'dur="{fmt(trail)}s" fill="freeze" begin="{begin}" restart="never"/>'
            f'<set id="T{i}" attributeName="fill" to="{PATH}" begin="{tbegin}" restart="never"/></rect>')

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

    # the clock, delays, snaps, winner gates and trace relays: timing only, on an invisible element
    g = []
    if clocked:
        g.append(f'<animate id="CLK" attributeName="y" values="0;0" dur="{fmt(tick)}s" begin="0s" repeatCount="indefinite"/>')
    if clocked:
        for i in range(m.cells):
            if i == m.start or not into[i]:
                continue
            g.append(f'<set id="M{i}" attributeName="x" to="0" begin="{"; ".join(f"R{j}{b}" for _, j in into[i])}" restart="never"/>')
            g.append(f'<set id="D{i}" attributeName="x" to="0" begin="M{i}{b}" dur="{fmt((m.cost[i] - 0.75) * tick)}s" restart="never"/>')
            g.append(f'<set id="S{i}" attributeName="x" to="0" begin="D{i}{en}" end="CLK.repeatEvent" restart="never"/>')
    for e, (j, i) in enumerate(edges):
        if i == m.start:   # the trace never needs to leave the start cell
            continue
        if clocked:   # j wins i if j was reached no later than i's first neighbour
            g.append(f'<set id="W{e}" attributeName="x" to="0" begin="R{j}{b}" end="M{i}{b}+{fmt(tick / 4)}s" restart="never"/>')
        else:         # j wins i if its claim arrived no later than i was reached
            g.append(f'<set id="W{e}" attributeName="x" to="0" begin="{claim(e, j, i)}" end="R{i}{b}+{fmt(tick / 4)}s" restart="never"/>')
        g.append(f'<set id="X{e}" attributeName="x" to="0" begin="W{e}{en}" end="T{i}{b}+{fmt(dt)}s" restart="never"/>')
    parts.append(f'<rect width="0" height="0">{"".join(g)}</rect>')
    parts.append("</svg>")
    text = "".join(parts)
    info = dict(tick=tick, start_at=start_ticks * tick, trace_after=trace_after, dt=dt, edges=len(edges), timing=timing,
                elements=text.count("<set ") + text.count("<animate "))
    return text, info
