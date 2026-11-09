"""Edit distance and the reference answer.

Aligning a string a with a string b is a walk on a grid of (len(a) + 1) x (len(b) + 1) cells, from the top
left corner to the bottom right. Cell (i, j) stands for a[:i] aligned with b[:j]: a step down deletes a
letter of a, a step right inserts a letter of b, and a diagonal step keeps a letter, free when the two
letters match and a substitution, costing 1, when they differ. The edit distance (Levenshtein's) is the cost
of the cheapest walk. The reference is the textbook dynamic programme, written out here so the checks never
depend on the SVG to know the answer.
"""
import random


def edit_distance(a, b):
    """The plain way: the table one row at a time."""
    row = list(range(len(b) + 1))
    for i, x in enumerate(a, 1):
        diag, row[0] = row[0], i
        for j, y in enumerate(b, 1):
            diag, row[j] = row[j], min(row[j] + 1, row[j - 1] + 1, diag + (x != y))
    return row[-1]


def prefix_distances(a, b):
    """D[i][j], the edit distance between a[:i] and b[:j], for every cell."""
    D = [[i + j for j in range(len(b) + 1)] for i in range(len(a) + 1)]
    for i in range(1, len(a) + 1):
        for j in range(1, len(b) + 1):
            D[i][j] = min(D[i - 1][j] + 1, D[i][j - 1] + 1, D[i - 1][j - 1] + (a[i - 1] != b[j - 1]))
    return D


def alignment_cells(a, b):
    """Every cell (i, j) on at least one cheapest alignment, where the distances from the start and to the
    end add up to the total, and the total."""
    n, m = len(a), len(b)
    forward, backward = prefix_distances(a, b), prefix_distances(a[::-1], b[::-1])
    total = forward[n][m]
    return {(i, j) for i in range(n + 1) for j in range(m + 1) if forward[i][j] + backward[n - i][m - j] == total}, total


def random_pair(n, m, seed=0, alphabet="ACGT"):
    rng = random.Random(seed)
    return "".join(rng.choices(alphabet, k=n)), "".join(rng.choices(alphabet, k=m))
