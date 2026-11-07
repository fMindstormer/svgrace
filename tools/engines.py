"""Where the three engines agree on the SMIL timing svgrace is built from, and where they do not.

Each probe is a small SVG with no script, run in Playwright's Chromium, Firefox and WebKit, and compared
with what SMIL 3.0 (https://www.w3.org/TR/SMIL3/smil-timing.html) says it must compute. Times are read
with getStartTime() from outside the SVG; "none" means the element has no interval (the call threw).
Like svgrace's own elements, every probe element has restart="never" unless the probe is about restart.

How each probe is read:
  paused       the clock is paused once the document has loaded: what the engine resolved ahead of time
  running t    the clock runs to document time t
  seek t       the paused clock is moved to t with setCurrentTime()
  chain        an event-based chain is read while it runs
  img          the SVG is shown through <img>, and its colour is read from a screenshot

  python tools/engines.py          prints a Markdown table
"""
import functools
import http.server
import io
import sys
import tempfile
import threading
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

ENGINES = {"chromium": "Chromium", "firefox": "Firefox", "webkit": "WebKit"}


def svg(*parts):
    return ('<svg xmlns="http://www.w3.org/2000/svg" width="40" height="40">'
            f'<rect id="target" width="10" height="10" fill="teal">{"".join(parts)}</rect></svg>')


def s(id, begin, more="", restart="never"):
    """A timed element whose only job is to have an interval."""
    return f'<set id="{id}" attributeName="x" to="0" begin="{begin}" restart="{restart}" {more}/>'


def gate(a, b, *extra):
    """svgrace's winner gate: W begins at a.begin+1s and is ended by b.begin+1s; X begins when W ends."""
    return svg(s("a", a, 'dur="10s"'), s("b", b, 'dur="10s"'), s("w", "a.begin+1s", 'end="b.begin+1s"'), s("x", "w.end"), *extra)


# A gate whose end is corrected: b first resolves through p (3 s), then through the longer chain r -> q to
# 0.5 s, which moves W's end (b.begin) from 3 s to 0.5 s, before W's begin at 1 s.
CORE = [s("a", "0s", 'dur="10s"'), s("b", "p.begin+3s; q.begin+0.5s", 'dur="10s"'), s("w", "a.begin+1s", 'end="b.begin"'), s("x", "w.end")]
CHAIN = [s("p", "0s", 'dur="10s"'), s("r", "0s", 'dur="10s"'), s("q", "r.begin", 'dur="10s"')]
WIDTH = '<animate attributeName="width" from="10" to="20" dur="1s" begin="0s; 3s" restart="never"/>'
HOPS = 20
IMG = ('<svg xmlns="http://www.w3.org/2000/svg" width="40" height="40"><rect width="40" height="40" fill="teal">'
       '<set id="e0" attributeName="x" to="0" begin="0.1s" dur="10s"/><set id="e1" attributeName="x" to="0" begin="e0.{0}+0.1s" dur="10s"/>'
       '<set attributeName="fill" to="red" begin="e1.{0}+0.1s"/></rect></svg>')

PROBES = [
    # (name, what SMIL 3.0 requires, how it is read, SVG, expression read, expected)
    ("begin list takes the earliest", "`begin=\"0.3s; 0.1s\"` begins at 0.1 s",
     "paused", svg(s("e", "0.3s; 0.1s")), "st('e')", 0.1),
    ("open cycle", "A `0s; B.begin+1s`, B `A.begin+1s`: A at 0, B at 1",
     "paused", svg(s("a", "0s; b.begin+1s"), s("b", "a.begin+1s")), "[st('a'), st('b')]", [0, 1]),
    ("closed cycle", "A `B.begin+1s`, B `A.begin+1s`: both unresolved",
     "paused", svg(s("a", "b.begin+1s"), s("b", "a.begin+1s")), "[st('a'), st('b')]", [None, None]),
    ("gate, end after begin", "W is 1 s to 1.5 s, X begins at 1.5",
     "paused", gate("0s", "0.5s"), "st('x')", 1.5),
    ("gate, end equals begin", "a 0-length interval still ends and \"propagate[s] to time dependents\": X at 1",
     "paused", gate("0s", "0s"), "st('x')", 1.0),
    ("the same, clock running", "X at 1",
     "running 2", gate("0s", "0s"), "st('x')", 1.0),
    ("gate, end before begin", "no interval, so X never begins",
     "paused", gate("0.5s", "0s"), "st('x')", None),
    ("gate, end corrected to before begin", "\"the interval must be pruned and all dependent instance times must be removed\": X never begins",
     "paused", svg(*CORE, *CHAIN), "[st('b'), st('x')]", [0.5, None]),
    ("the same, elements in another order", "X never begins",
     "paused", svg(*CHAIN[::-1], *CORE), "[st('b'), st('x')]", [0.5, None]),
    ("`restart=\"never\"` while active", "`begin=\"0s; 0.5s\"`, 2 s long: at 1 s still the interval from 0",
     "running 1", svg(s("e", "0s; 0.5s", 'dur="2s"')), "st('e')", 0),
    ("`restart=\"never\"` after the end", "`begin=\"0s; 3s\"`, 1 s long: inactive at 3.5 s, width stays 10",
     "running 3.5", svg(WIDTH), "document.getElementById('target').width.animVal.value", 10),
    ("the same two, after `setCurrentTime()`", "a forward seek \"should\" leave the state playing would: 0, and 10",
     "seek", (svg(s("e", "0s; 0.5s", 'dur="2s"')), svg(WIDTH)), None, [0, 10]),
    ("`restart=\"always\"` while active (control)", "the first probe with restart=\"always\": restarted at 0.5",
     "running 1", svg(s("e", "0s; 0.5s", 'dur="2s"', restart="always")), "st('e')", 0.5),
    ("event-based chain", f"`prev.beginEvent+0.1s`, {HOPS} hops: an event's time is \"the earliest time that the event could be raised\" (largest error)",
     "chain", svg(s("e0", "0.2s", 'dur="30s"'), *(s(f"e{k}", f"e{k - 1}.beginEvent+0.1s", 'dur="30s"') for k in range(1, HOPS + 1))),
     None, 0),
    ("`getStartTime()` after the interval ends", "0.5 s long, read at 1 s: unspecified (SVG 1.1 throws without a \"current interval\")",
     "running 1", svg(s("e", "0s", 'dur="0.5s" fill="freeze"')), "st('e')", "unspecified"),
    ("syncbase timing inside `<img>`", "SVG Integration: \"declarative animation: yes\" in an image; the chain turns it red",
     "img", IMG.format("begin"), None, "red"),
    ("event-based timing inside `<img>`", "the same chain with `beginEvent`",
     "img", IMG.format("beginEvent"), None, "red"),
]

ST = "const st = id => { try { return document.getElementById(id).getStartTime(); } catch (e) { return null; } };"


def close(got, want):
    if isinstance(want, list):
        return isinstance(got, list) and len(got) == len(want) and all(close(g, w) for g, w in zip(got, want))
    if want is None or got is None:
        return got is want
    return isinstance(got, (int, float)) and abs(got - want) < 1e-6


def now(page):
    return page.evaluate("() => document.querySelector('svg').getCurrentTime()")


def measure(browser, server, kind, text, expr):
    if kind == "seek":   # both restart probes, each moved there by setCurrentTime()
        return [measure(browser, server, f"seek {at}", t, e)
                for at, t, e in ((1, text[0], "st('e')"), (3.5, text[1], "document.getElementById('target').width.animVal.value"))]
    page = browser.new_page()
    try:
        if kind == "img":
            name = f"probe{abs(hash(text))}.svg"
            (server.root / name).write_text(text)
            (server.root / f"{name}.html").write_text(f'<!doctype html><body style="margin:0"><img src="{name}"></body>')
            page.goto(f"http://127.0.0.1:{server.port}/{name}.html", timeout=10_000)
            time.sleep(1.5)
            from PIL import Image
            r, g, b = Image.open(io.BytesIO(page.screenshot())).convert("RGB").getpixel((20, 20))
            return "red" if r > 200 and g < 60 and b < 60 else "teal" if r < 60 and g > 100 and b > 100 else f"#{r:02x}{g:02x}{b:02x}"
        page.set_content(text)
        if kind == "chain":   # the largest error along the chain, read while it runs
            ids = [f"e{k}" for k in range(HOPS + 1)]
            got = [None] * len(ids)
            while True:
                t = now(page)
                fresh = page.evaluate(f"ids => {{ {ST} return ids.map(st); }}", ids)
                got = [n if n is not None else o for n, o in zip(fresh, got)]
                if t > 0.2 + 0.1 * HOPS + 0.5:
                    break
                time.sleep(1)
            if None in got:
                return f"{sum(g is not None for g in got[1:])} of {HOPS} hops ran"
            return round(max(abs(t - (0.2 + 0.1 * k)) for k, t in enumerate(got)) * 1000)
        if kind.startswith("running"):
            at = float(kind.split()[1])
            while now(page) < at:
                time.sleep(0.05)
        else:
            page.evaluate("() => document.querySelector('svg').pauseAnimations()")
            if kind.startswith("seek"):
                page.evaluate(f"() => document.querySelector('svg').setCurrentTime({float(kind.split()[1])})")
                time.sleep(0.1)   # give the engine a moment to sample the new time
        return page.evaluate(f"() => {{ {ST} return {expr}; }}")
    finally:
        page.close()


class Server:
    def __init__(self):
        self.root = Path(tempfile.mkdtemp())

        class Quiet(http.server.SimpleHTTPRequestHandler):
            def log_message(self, *a):
                pass
        srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(Quiet, directory=str(self.root)))
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        self.port = srv.server_port


def fmt(v):
    if isinstance(v, list):
        return ", ".join(fmt(x) for x in v)
    if v is None:
        return "none"
    if isinstance(v, float) and not v.is_integer():
        return f"{v:g}"
    return str(int(v)) if isinstance(v, float) else str(v)


def main():
    server = Server()
    results, versions = {}, {}
    with sync_playwright() as p:
        for engine in ENGINES:
            b = getattr(p, engine).launch()
            versions[engine] = b.version
            for name, _, kind, text, expr, _ in PROBES:
                try:
                    results[engine, name] = measure(b, server, kind, text, expr)
                except Exception as e:
                    results[engine, name] = f"error: {type(e).__name__}"
            b.close()
    print("| Probe | SMIL 3.0 | " + " | ".join(f"{ENGINES[e]} {versions[e].split('.')[0]}" for e in ENGINES) + " |")
    print("|---|---|" + "---|" * len(ENGINES))
    for name, rule, kind, _, _, want in PROBES:
        cells = []
        for e in ENGINES:
            got = results[e, name]
            if kind == "chain":
                cells.append(f"{got} ms" if isinstance(got, int) else got)
                wrong = not (isinstance(got, int) and got <= 1)
            else:
                cells.append(fmt(got))
                wrong = want != "unspecified" and not (got == want if kind == "img" else close(got, want))
            if wrong:
                cells[-1] = f"**{cells[-1]}**"
        print(f"| {name} | {rule} | " + " | ".join(cells) + " |")
    print(f"\nBold: differs from SMIL 3.0. Playwright builds: " + ", ".join(f"{ENGINES[e]} {versions[e]}" for e in ENGINES) + ".")


if __name__ == "__main__":
    sys.exit(main())
