// svgrace in the browser: the maze generator and the clocked compiler, ported from svgrace/maze.py and
// svgrace/compile.py so that the page can build an SVG for a maze drawn on it. The port writes byte for
// byte what the Python writes (tests/test_page.py checks it). The SVG it writes has no script; this file
// only writes its text.
const svgrace = (() => {
  // Python's random.Random for a small non-negative integer seed: MT19937 seeded by init_by_array, and
  // the same draws as choice, shuffle and choices.
  class PyRandom {
    constructor(seed) {
      const mt = this.mt = new Uint32Array(624);
      const init = s => {
        mt[0] = s >>> 0;
        for (let i = 1; i < 624; i++) mt[i] = (Math.imul(1812433253, mt[i - 1] ^ (mt[i - 1] >>> 30)) + i) >>> 0;
      };
      init(19650218);
      const key = [seed >>> 0];
      let i = 1, j = 0;
      for (let k = Math.max(624, key.length); k; k--) {
        mt[i] = ((mt[i] ^ Math.imul(mt[i - 1] ^ (mt[i - 1] >>> 30), 1664525)) + key[j] + j) >>> 0;
        i++; j++;
        if (i >= 624) { mt[0] = mt[623]; i = 1; }
        if (j >= key.length) j = 0;
      }
      for (let k = 623; k; k--) {
        mt[i] = ((mt[i] ^ Math.imul(mt[i - 1] ^ (mt[i - 1] >>> 30), 1566083941)) - i) >>> 0;
        i++;
        if (i >= 624) { mt[0] = mt[623]; i = 1; }
      }
      mt[0] = 0x80000000;
      this.index = 624;
    }
    uint32() {
      const mt = this.mt;
      if (this.index >= 624) {
        for (let k = 0; k < 624; k++) {
          const y = (mt[k] & 0x80000000) | (mt[(k + 1) % 624] & 0x7fffffff);
          mt[k] = mt[(k + 397) % 624] ^ (y >>> 1) ^ (y & 1 ? 0x9908b0df : 0);
        }
        this.index = 0;
      }
      let y = mt[this.index++];
      y ^= y >>> 11;
      y ^= (y << 7) & 0x9d2c5680;
      y ^= (y << 15) & 0xefc60000;
      return (y ^ (y >>> 18)) >>> 0;
    }
    random() {
      const a = this.uint32() >>> 5, b = this.uint32() >>> 6;
      return (a * 67108864 + b) / 9007199254740992;
    }
    below(n) {   // _randbelow_with_getrandbits
      const k = 32 - Math.clz32(n);
      let r = this.uint32() >>> (32 - k);
      while (r >= n) r = this.uint32() >>> (32 - k);
      return r;
    }
    choice(seq) { return seq[this.below(seq.length)]; }
    shuffle(x) {
      for (let i = x.length - 1; i > 0; i--) {
        const j = this.below(i + 1);
        [x[i], x[j]] = [x[j], x[i]];
      }
    }
    choiceWeighted(population, weights) {   // choices(population, weights)[0]: bisect_right on the sums
      const cum = [];
      weights.reduce((s, w) => (cum.push(s + w), s + w), 0);
      const x = this.random() * cum[cum.length - 1];
      let lo = 0, hi = population.length - 1;
      while (lo < hi) { const mid = (lo + hi) >> 1; if (x < cum[mid]) hi = mid; else lo = mid + 1; }
      return population[lo];
    }
  }

  // A maze: passages are undirected, kept as the key of (smaller cell, larger cell); cost[i] is the cost
  // of entering cell i.
  function maze(width, height) {
    const cells = width * height;
    return {width, height, cells, passages: new Set(), cost: new Array(cells).fill(1), start: 0, exit: cells - 1};
  }
  const key = (m, i, j) => Math.min(i, j) * m.cells + Math.max(i, j);
  const isOpen = (m, i, j) => m.passages.has(key(m, i, j));
  const xy = (m, i) => [i % m.width, Math.floor(i / m.width)];
  const STEPS = [[1, 0], [-1, 0], [0, 1], [0, -1]];

  function neighbours(m, i) {
    const [x, y] = xy(m, i), out = [];
    for (const [dx, dy] of STEPS) {
      const nx = x + dx, ny = y + dy;
      if (nx >= 0 && nx < m.width && ny >= 0 && ny < m.height && isOpen(m, i, ny * m.width + nx)) out.push(ny * m.width + nx);
    }
    return out;
  }

  function directedEdges(m) {
    const out = [];
    for (let i = 0; i < m.cells; i++) for (const j of neighbours(m, i)) out.push([i, j]);
    return out;
  }

  function generate(width, height, seed = 0, loops = 0.15, costs = [1, 2, 3], weights = [6, 3, 1]) {
    const rng = new PyRandom(seed), m = maze(width, height);
    const seen = new Set([0]), stack = [0];
    while (stack.length) {
      const i = stack[stack.length - 1], [x, y] = xy(m, i);
      const options = STEPS.map(([dx, dy]) => [x + dx, y + dy])
        .filter(([nx, ny]) => nx >= 0 && nx < width && ny >= 0 && ny < height && !seen.has(nx + ny * width))
        .map(([nx, ny]) => nx + ny * width);
      if (!options.length) { stack.pop(); continue; }
      const j = rng.choice(options);
      m.passages.add(key(m, i, j));
      seen.add(j);
      stack.push(j);
    }
    const walls = [];
    for (let i = 0; i < m.cells; i++) {
      for (const j of [i + 1, i + width]) {
        if (j < m.cells && (j !== i + 1 || (i + 1) % width) && !m.passages.has(key(m, i, j))) walls.push([i, j]);
      }
    }
    rng.shuffle(walls);
    for (const [i, j] of walls.slice(0, Math.trunc(walls.length * loops))) m.passages.add(key(m, i, j));
    // terrain: random seeds of each cost, grown by two rounds of majority smoothing; ties go to the
    // lowest cost, which is the order Python's max() meets them in a set of small ints
    let grid = Array.from({length: m.cells}, () => rng.choiceWeighted(costs, weights));
    for (let round = 0; round < 2; round++) {
      const next = grid.slice();
      for (let i = 0; i < m.cells; i++) {
        const [x, y] = xy(m, i), count = new Map();
        for (const dx of [-1, 0, 1]) for (const dy of [-1, 0, 1]) {
          if (x + dx >= 0 && x + dx < width && y + dy >= 0 && y + dy < height) {
            const c = grid[(y + dy) * width + (x + dx)];
            count.set(c, (count.get(c) || 0) + 1);
          }
        }
        let best = null;
        for (const c of [...count.keys()].sort((a, b) => a - b)) if (best === null || count.get(c) > count.get(best)) best = c;
        next[i] = best;
      }
      grid = next;
    }
    m.cost = grid;
    m.cost[m.start] = m.cost[m.exit] = 1;
    return m;
  }

  function dijkstra(m, source, reverse = false) {
    const dist = new Array(m.cells).fill(Infinity), done = new Array(m.cells).fill(false);
    dist[source] = 0;
    for (;;) {
      let i = -1;
      for (let k = 0; k < m.cells; k++) if (!done[k] && dist[k] < Infinity && (i < 0 || dist[k] < dist[i])) i = k;
      if (i < 0) return dist;
      done[i] = true;
      for (const j of neighbours(m, i)) dist[j] = Math.min(dist[j], dist[i] + (reverse ? m.cost[i] : m.cost[j]));
    }
  }

  function shortestPathCells(m) {   // every cell on at least one cheapest route, and the route's cost
    const a = dijkstra(m, m.start), b = dijkstra(m, m.exit, true), total = a[m.exit], cells = new Set();
    for (let i = 0; i < m.cells; i++) if (a[i] + b[i] === total) cells.add(i);
    return {cells, total};
  }

  const PALETTE = {1: "#f2efe6", 2: "#d9cfb3", 3: "#b6a47c"}, WALL = "#3b3a36";
  const TRAIL = "#fff3b0;#f4a261;#2a9d8f;#22577a", PATH = "#ffd166";
  const fmt = t => t.toFixed(4).replace(/0+$/, "").replace(/\.$/, "") || "0";
  const pyFloat = v => Number.isInteger(v) ? `${v}.0` : `${v}`;   // how Python prints a float

  // compile_svg(m, timing="clocked") in svgrace/compile.py, which explains the machine
  function compile(m, {tick = 0.1, traceAfter = 0.6, dt = 0.05, cell = 18, margin = 10, trail = 6.0, title = null, startTicks = 10, hoist = true} = {}) {
    const W = m.width, H = m.height, sizeW = W * cell + 2 * margin, sizeH = H * cell + 2 * margin;
    const edges = directedEdges(m), into = [], outOf = [];
    for (let i = 0; i < m.cells; i++) { into.push([]); outOf.push([]); }
    edges.forEach(([j, i], e) => { into[i].push([e, j]); outOf[j].push([e, i]); });
    const parts = [`<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ${sizeW} ${sizeH}" width="${sizeW}" height="${sizeH}">`];
    if (title) parts.push(`<title>${title}</title>`);
    parts.push(`<rect width="${sizeW}" height="${sizeH}" fill="${WALL}"/>`);
    // R and T: with hoist, on the invisible element ahead of the gates, and each cell shows copies that begin with them
    const g = [];
    for (let i = 0; i < m.cells; i++) {
      const [x, y] = xy(m, i);
      let begin = i === m.start ? `${fmt(startTicks * tick)}s` : into[i].length ? `S${i}.endEvent` : "indefinite";
      let tbegin = i === m.exit ? `R${i}.beginEvent+${fmt(traceAfter)}s`
        : outOf[i].filter(([, k]) => k !== m.start).map(([e]) => `X${e}.endEvent`).join("; ") || "indefinite";
      let r = `id="R${i}" `, t = `id="T${i}" `;
      if (hoist) {
        g.push(`<set ${r}attributeName="x" to="0" begin="${begin}" restart="never"/>`
          + `<set ${t}attributeName="x" to="0" begin="${tbegin}" restart="never"/>`);
        [r, t, begin, tbegin] = ["", "", `R${i}.beginEvent`, `T${i}.beginEvent`];
      }
      parts.push(`<rect x="${margin + x * cell}" y="${margin + y * cell}" width="${cell}" height="${cell}" fill="${PALETTE[m.cost[i]]}">`
        + `<animate ${r}attributeName="fill" values="${TRAIL}" keyTimes="0;0.06;0.35;1" `
        + `dur="${fmt(trail)}s" fill="freeze" begin="${begin}" restart="never"/>`
        + `<set ${t}attributeName="fill" to="${PATH}" begin="${tbegin}" restart="never"/></rect>`);
    }
    const lines = [];
    for (let i = 0; i < m.cells; i++) {
      const [x, y] = xy(m, i), px = margin + x * cell, py = margin + y * cell;
      if (x + 1 < W && !m.passages.has(key(m, i, i + 1))) lines.push(`M${px + cell} ${py}v${cell}`);
      if (y + 1 < H && !m.passages.has(key(m, i, i + W))) lines.push(`M${px} ${py + cell}h${cell}`);
    }
    lines.push(`M${margin} ${margin}h${W * cell}v${H * cell}h${-W * cell}z`);
    parts.push(`<path d="${lines.join("")}" stroke="${WALL}" stroke-width="3" stroke-linecap="square" fill="none"/>`);
    for (const [i, label] of [[m.start, "S"], [m.exit, "E"]]) {
      const [x, y] = xy(m, i);
      parts.push(`<text x="${pyFloat(margin + x * cell + cell / 2)}" y="${pyFloat(margin + y * cell + cell * 0.72)}" `
        + `font-family="sans-serif" font-size="${(cell * 0.62).toFixed(0)}" font-weight="bold" `
        + `text-anchor="middle" fill="${WALL}">${label}</text>`);
    }
    g.push(`<animate id="CLK" attributeName="y" values="0;0" dur="${fmt(tick)}s" begin="0s" repeatCount="indefinite"/>`);
    for (let i = 0; i < m.cells; i++) {
      if (i === m.start || !into[i].length) continue;
      g.push(`<set id="M${i}" attributeName="x" to="0" begin="${into[i].map(([, j]) => `R${j}.beginEvent`).join("; ")}" restart="never"/>`);
      g.push(`<set id="D${i}" attributeName="x" to="0" begin="M${i}.beginEvent" dur="${fmt((m.cost[i] - 0.75) * tick)}s" restart="never"/>`);
      g.push(`<set id="S${i}" attributeName="x" to="0" begin="D${i}.endEvent" end="CLK.repeatEvent" restart="never"/>`);
    }
    edges.forEach(([j, i], e) => {
      if (i === m.start) return;
      g.push(`<set id="W${e}" attributeName="x" to="0" begin="R${j}.beginEvent" end="M${i}.beginEvent+${fmt(tick / 4)}s" restart="never"/>`);
      g.push(`<set id="X${e}" attributeName="x" to="0" begin="W${e}.endEvent" end="T${i}.beginEvent+${fmt(dt)}s" restart="never"/>`);
    });
    parts.push(`<rect width="0" height="0">${g.join("")}</rect>`);
    parts.push("</svg>");
    return {svg: parts.join(""), info: {tick, startAt: startTicks * tick, traceAfter, dt, sizeW, sizeH}};
  }

  return {PyRandom, maze, key, isOpen, xy, neighbours, generate, dijkstra, shortestPathCells, compile, PALETTE, WALL};
})();
