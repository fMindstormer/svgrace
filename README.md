# svgrace

**An SVG that solves its own maze.** There is no script in the file. Every number it computes is a
time, and the computer is the browser's animation scheduler, doing its ordinary job of deciding when
each animation starts.

**[Watch it run](https://fmindstormer.github.io/svgrace/)**: the clocked build, a maze with loops and
terrain, on a page with no script. Reload to run it again.

[![checks](https://github.com/fMindstormer/svgrace/actions/workflows/checks.yml/badge.svg)](https://github.com/fMindstormer/svgrace/actions/workflows/checks.yml)

![A maze in a dark frame. A wave spreads from S, orange at its front and fading to teal and navy behind it, until it fills the maze; then a gold route appears, running back from E to S.](docs/recording.webp)

*`examples/maze.svg` running in Chromium, recorded from the real file. The orange front is the set of cells
the scheduler is settling; the gold route is the cheapest way from S to E (darker cells cost more).*

The maze below is the file itself, not a recording. GitHub shows it through a plain `<img>`, where no
script can run, and the browser computes its route as the page loads (checked in Chromium; reload the
page to run it again):

![A maze that solves itself: a wave spreads from S and a gold route appears from E back to S](examples/maze-readme.svg)

The SVG animations (SMIL) that make icons spin can start when another animation starts or ends, plus a
delay. That one feature is a model of computation with a name: **race logic**, computing with the
arrival times of signals. "Start at the earliest of these" is a minimum, a delay is an addition, and
together they are one step of Dijkstra's shortest-path algorithm. svgrace compiles a maze into such an
SVG. The wave you watch spreading through it is the browser settling cells in order of distance; when
it reaches the exit, a trace runs back and lights every cell on a cheapest route.

## The machine

Each cell has an animation `R` that starts when the cell is reached. Its `begin` lists every neighbour:

```xml
<animate id="R57" begin="R56.begin+0.2s; R33.begin+0.2s; R81.begin+0.2s" restart="never" …/>
```

A begin list takes its earliest instance, so `R57` starts at min over neighbours of (their start + the
cost of entering cell 57). That is the relaxation step of Dijkstra's algorithm, and the scheduler applies
it to every cell. Cells cost 1, 2 or 3 to enter (the darker terrain), so the cheapest route is not the
one with the fewest steps.

| Race logic | SMIL timing |
|---|---|
| a signal arriving at time t | an animation beginning at t |
| delay by d | `begin="X.begin+ds"` |
| min (first arrival) | a begin list: `begin="X.begin; Y.begin"` |
| a gate: pass B only if A came first | an element begun by A and ended by B: its end fires at B only if A was earlier |
| a write-once bit | `restart="never"`: once an element has begun it can never begin again |

The last two rows find the route. For each passage j → i, a *winner* element begins when j's claim on i
arrives and is ended just after i is reached. An element only ends at a time after its begin, so the end
fires only if j's claim was not later than i's reach, which means j is a cheapest way into i. A *relay*,
armed by that end, passes the trace from i back to j. The trace starts at the exit and follows winning
passages only, so it lights exactly the cells on cheapest routes, and all of them when there are ties.

## Two ways to say "after", and what each costs

SMIL has two ways to make one animation follow another, and Chromium treats them very differently.

**Syncbase timing** (`R56.begin+0.2s`) is exact: the times are pure arithmetic. But the engine resolves
them ahead of the clock, as soon as the document loads, by propagating every improvement through the
dependency graph. That is the textbook worst case of label-correcting shortest-path algorithms, and the
cost grows exponentially with the number of alternative routes:

| Maze | Cells | Loops | Load time in Chromium 141 |
|---|---|---|---|
| perfect maze (one route) | 384 | none | 0.13 s |
| perfect maze | 640 | none | 0.84 s |
| braid maze | 108 | 15% of walls removed | 0.07 s |
| braid maze | 140 | 15% | 3.6 s |
| braid maze | 176 | 15% | 72 s |
| braid maze | 216 | 15% | over 5 minutes |
| open grid (every passage) | 80 | all | over 2 minutes |

**Event-based timing** (`R56.beginEvent+0.2s`) cannot be predicted: a time exists only once its event
has fired, so the engine settles cells in clock order, the way Dijkstra's priority queue would, and the
cost is linear. But Chromium stamps an event with the time of the frame that delivered it, so every hop
adds up to a frame of error: in a test chain, a cell due at 1.30 s arrived at 1.40 s.

**The clock.** The original race-logic hardware used clocked delays, and so does svgrace. A clock
animation ticks every 0.1 s. A cell's delay runs a little short of its cost, then a *snap* element waits
for the next tick, so frame jitter is absorbed at every hop instead of accumulating. Cells are reached on
whole ticks, exactly. Each cell takes the minimum over its neighbours first and snaps once, because a
passage's cost is the cost of the cell it enters; that keeps the clock's listeners to one per cell.

The price is real time: a snap fails if the engine falls more than about three quarters of a tick
behind, so the clock rate is limited by how fast the engine runs frames.

## Findings in Chromium

- **Syncbase resolution is exponential** in the number of alternative routes (table above). Seeking
  afterwards is instant: the cost is all in resolving the dependency graph at load.
- **Event times are frame times.** An event-based time is the time of the frame that delivered the
  event, not the time the event belonged to, so unclocked event chains drift.
- **No events inside `<img>`.** Chromium does not run event-based timing in an SVG shown as an image:
  only the start cell animates. Syncbase timing does run there.
- **The clock's speed limit.** On a 2-core container (headless Chromium, software rendering), with
  24×16 braid mazes (384 cells, about 3,650 timed elements), a tick of 0.1 s was exact in 20 of 20 runs
  and 0.08 s in 8 of 8; 0.06 s failed occasionally. At 40×30 (1,200 cells, about 11,470 elements)
  frames ran 50 to 67 ms late: 0.15 s failed in 2 of 3 runs, and 0.3 s was exact in 3 of 3. The
  engine's work per frame grows with the number of elements, so a bigger maze needs a slower clock.

So there are two builds. `--timing syncbase` on perfect mazes runs anywhere an SVG animates, including a
GitHub README. `--timing clocked` handles mazes with competing routes, in a page that embeds the SVG with
`<object>` or inline, or opened directly.

## How it is checked

The checker never trusts the picture: it computes the answer separately (Dijkstra) and compares.

| Claim | Evidence | Result (Chromium 141) |
|---|---|---|
| Every cell is reached at its cheapest cost | each `R`'s start time, read back with `getStartTime()`, rounded to whole ticks after the start cell's, equals Dijkstra's distance | clocked 24×16 with loops: 20 of 20 mazes; syncbase 24×16 perfect mazes: 30 of 30; syncbase 12×9 with loops: 30 of 30 |
| The trace lights exactly the cheapest routes | the set of cells whose `T` began equals the set of cells on some cheapest route (from forward and backward Dijkstra) | the same runs |
| It works where it will be shown | pixels after the race: gold cells must equal the route cells | syncbase inside `<img>`: 4 of 4; clocked inside `<object>`: 3 of 3 |

Rechecked in October 2026 on Chromium 156 (Playwright 1.64, an Apple-silicon Mac): clocked 24×16 with
loops, 5 of 5 mazes; syncbase inside `<img>`, 3 of 3; clocked inside `<object>`, 3 of 3. The load-time
table was not measured again.

```sh
pip install -r requirements.txt && python -m playwright install chromium
python -m svgrace check 24 16 --seeds 20                    # clocked, real time
python -m svgrace check 24 16 --seeds 30 --loops 0 --timing syncbase --mode seek
python tests/img_check.py --timing syncbase --tag img       # the README case
python -m svgrace build 24 16 --seed 3 --out maze.svg       # make one
```

## Limits and next steps

- **One engine.** Only Chromium was available here. Firefox and Safari implement SMIL timing
  independently, so the same files are a conformance test of three schedulers: ties, cycles,
  `restart="never"` and event timing are where they are most likely to disagree.
- **Mazes are the first program.** The same primitives compute edit distance (race logic's original
  application, DNA alignment) and sorting.
- **Universality.** With cycles and restarts, the same elements make temporal state machines: a counter
  can be held as the offset between two looping pulses, incremented or decremented by delaying one of
  them, and tested for zero by which arrives first. That should make SMIL timing Turing complete up to
  the engine's time precision; the construction is not built yet.
- **Report the cliff.** The exponential syncbase resolution is worth a Chromium bug with these files as
  test cases.

## Prior art

Race logic: A. Madhavan, T. Sherwood and D. Strukov, "Race Logic: A Hardware Acceleration for Dynamic
Programming Algorithms", ISCA 2014. Space-time algebra: J. E. Smith, ISCA 2018. Temporal state machines:
[arXiv:2009.14243](https://arxiv.org/abs/2009.14243). The SMIL timing model: [SMIL 3.0](https://www.w3.org/TR/SMIL3/smil-timing.html),
and its use in [SVG](https://www.w3.org/TR/SVG11/animate.html). I found no earlier use of SMIL timing to compute, in a
search in October 2026; that is not proof that none exists.

## License

MIT, Fedir Yudin. See [LICENSE](LICENSE).
