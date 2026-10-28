"""svgrace: SVG animations whose timing computes. A maze compiled to an SVG finds its own cheapest route."""
from .maze import Maze, generate, dijkstra, shortest_path_cells
from .compile import compile_svg
