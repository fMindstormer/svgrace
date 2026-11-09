"""Write the example SVGs.

  maze-readme.svg   syncbase timing, a perfect maze: runs inside <img>, so it works in a README
  maze.svg          clocked timing, a maze with loops and terrain: needs <object>, inline SVG or the file itself
  align-readme.svg  syncbase timing, the edit distance between KITTEN and SITTING: runs inside <img>
  align.svg         clocked timing, the same strings: needs <object>, inline SVG or the file itself

The live page, index.html, plays maze.svg and lets a visitor draw a maze; svgrace.js builds that maze's
SVG in the browser, byte for byte as compile_svg would (tests/test_page.py).
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from svgrace import compile_align, compile_svg, edit_distance, generate, shortest_path_cells  # noqa: E402

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

    for name, timing in (("align-readme.svg", "syncbase"), ("align.svg", "clocked")):
        svg, info = compile_align("KITTEN", "SITTING", tick=0.12, cell=36, timing=timing,
                                  title="The edit distance between KITTEN and SITTING, found by animation timing alone")
        (HERE / name).write_text(svg)
        print(f"{name}: {len(svg) / 1024:.0f} KB, {info['elements']} timed elements, edit distance {edit_distance('KITTEN', 'SITTING')}")


if __name__ == "__main__":
    main()
