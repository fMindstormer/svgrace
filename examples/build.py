"""Write the example SVGs and the page that shows the clocked one.

  maze-readme.svg   syncbase timing, a perfect maze: runs inside <img>, so it works in a README
  maze.svg          clocked timing, a maze with loops and terrain: needs <object>, inline SVG or the file itself
  index.html        a page with no script that embeds maze.svg with <object>
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from svgrace import compile_svg, generate, shortest_path_cells  # noqa: E402

HERE = Path(__file__).resolve().parent


def main():
    m = generate(24, 16, seed=7, loops=0.0)
    svg, info = compile_svg(m, tick=0.12, timing="syncbase",
                            title="A maze that solves itself: the browser's animation timing finds the route")
    (HERE / "maze-readme.svg").write_text(svg)
    print(f"maze-readme.svg: {len(svg) / 1024:.0f} KB, {info['elements']} timed elements")

    m = generate(24, 16, seed=3, loops=0.15)
    svg, info = compile_svg(m, tick=0.12, timing="clocked",
                            title="A maze that finds its cheapest route with animation timing alone")
    (HERE / "maze.svg").write_text(svg)
    path, total = shortest_path_cells(m)
    print(f"maze.svg: {len(svg) / 1024:.0f} KB, {info['elements']} timed elements, cheapest route costs {total}")

    (HERE / "index.html").write_text("""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>svgrace</title>
<style>
  :root { color-scheme: light dark; --bg: #faf8f3; --fg: #23221f; --muted: #6b675e; }
  @media (prefers-color-scheme: dark) { :root { --bg: #1d1c1a; --fg: #ece9e1; --muted: #a39f95; } }
  body { margin: 0; background: var(--bg); color: var(--fg); font: 16px/1.5 system-ui, sans-serif; }
  main { max-width: 720px; margin: 0 auto; padding: 32px 16px; }
  h1 { font-size: 1.6rem; margin: 0 0 .4rem; }
  p { margin: .4rem 0 1rem; } .muted { color: var(--muted); font-size: .9rem; }
  object { width: 100%; height: auto; aspect-ratio: 452 / 308; display: block; border-radius: 6px; }
  a { color: inherit; }
</style></head>
<body><main>
<h1>A maze that solves itself</h1>
<p>No script runs on this page. Each cell of the maze is an SVG animation that begins when its cheapest
neighbour's begins, plus the cost of stepping onto it, so the browser's animation scheduler settles the
cells in order of distance. The wave you see is that order. When it reaches the exit, a trace runs back
along the winning passages and lights every cheapest route in gold.</p>
<object data="maze.svg" type="image/svg+xml" aria-label="A maze; a coloured wave spreads from S, and a gold route then appears from E back to S"></object>
<p class="muted">Darker cells cost more to cross. Reload to run it again.
<a href="https://github.com/fMindstormer/svgrace">How it works</a></p>
</main></body></html>
""")
    print("index.html")


if __name__ == "__main__":
    main()
