"""svgrace: SVG animations whose timing computes. A maze compiled to an SVG finds its own cheapest route, and
two strings compiled to an SVG find their edit distance and cheapest alignments."""
from .maze import Maze, generate, dijkstra, shortest_path_cells
from .align import edit_distance, alignment_cells, random_pair
from .compile import compile_svg, compile_align
