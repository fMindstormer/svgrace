"""Mazes and the reference answer.

A maze is a grid of cells with passages between neighbours. Each cell has a cost, the time it takes to
enter it, so the race finds the cheapest route rather than the one with fewest steps. The reference is
Dijkstra's algorithm, written out here so the checks never depend on the SVG to know the answer.
"""
import heapq
import random
from dataclasses import dataclass, field


@dataclass
class Maze:
    width: int
    height: int
    passages: set = field(default_factory=set)      # undirected edges, as (smaller cell, larger cell)
    cost: list = field(default_factory=list)         # cost of entering each cell, a small positive integer
    start: int = 0
    exit: int = -1

    def __post_init__(self):
        if self.exit < 0:
            self.exit = self.width * self.height - 1
        if not self.cost:
            self.cost = [1] * (self.width * self.height)

    @property
    def cells(self):
        return self.width * self.height

    def xy(self, i):
        return i % self.width, i // self.width

    def neighbours(self, i):
        x, y = self.xy(i)
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            nx, ny = x + dx, y + dy
            if 0 <= nx < self.width and 0 <= ny < self.height:
                j = ny * self.width + nx
                if (min(i, j), max(i, j)) in self.passages:
                    yield j

    def directed_edges(self):
        """Every passage in both directions, (from, to), in a fixed order."""
        return [(i, j) for i in range(self.cells) for j in self.neighbours(i)]


def generate(width, height, seed=0, loops=0.15, costs=(1, 2, 3), cost_weights=(6, 3, 1)):
    """A random maze: depth-first search carves a perfect maze, then a share of the remaining walls is
    knocked down so that there are several routes to compare. Costs are drawn in smooth patches, like
    terrain, so cheap and expensive regions are visible."""
    rng = random.Random(seed)
    m = Maze(width, height)
    seen, stack = {0}, [0]
    while stack:
        i = stack[-1]
        x, y = m.xy(i)
        options = [(x + dx) + (y + dy) * width for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))
                   if 0 <= x + dx < width and 0 <= y + dy < height and (x + dx) + (y + dy) * width not in seen]
        if not options:
            stack.pop()
            continue
        j = rng.choice(options)
        m.passages.add((min(i, j), max(i, j)))
        seen.add(j)
        stack.append(j)
    walls = [(i, j) for i in range(m.cells) for j in (i + 1, i + width)
             if (j < m.cells and (j != i + 1 or (i + 1) % width)) and (i, j) not in m.passages]
    rng.shuffle(walls)
    for w in walls[:int(len(walls) * loops)]:
        m.passages.add(w)
    # terrain: random seeds of each cost, grown by a few rounds of majority smoothing
    grid = [rng.choices(costs, cost_weights)[0] for _ in range(m.cells)]
    for _ in range(2):
        new = grid[:]
        for i in range(m.cells):
            x, y = m.xy(i)
            around = [grid[(y + dy) * width + (x + dx)] for dx in (-1, 0, 1) for dy in (-1, 0, 1)
                      if 0 <= x + dx < width and 0 <= y + dy < height]
            new[i] = max(set(around), key=around.count)
        grid = new
    m.cost = grid
    m.cost[m.start] = m.cost[m.exit] = 1
    return m


def dijkstra(m, source, reverse=False):
    """Cheapest cost from source to every cell, where stepping onto cell j costs cost[j].
    With reverse=True, the cost from every cell to source (stepping onto the next cell still costs its
    own price), which is what the path check needs."""
    inf = float("inf")
    dist = [inf] * m.cells
    dist[source] = 0
    heap = [(0, source)]
    while heap:
        d, i = heapq.heappop(heap)
        if d > dist[i]:
            continue
        for j in m.neighbours(i):
            step = m.cost[i] if reverse else m.cost[j]
            if d + step < dist[j]:
                dist[j] = d + step
                heapq.heappush(heap, (d + step, j))
    return dist


def shortest_path_cells(m):
    """Every cell that lies on at least one cheapest route from start to exit."""
    a, b = dijkstra(m, m.start), dijkstra(m, m.exit, reverse=True)
    total = a[m.exit]
    return {i for i in range(m.cells) if a[i] + b[i] == total}, total
