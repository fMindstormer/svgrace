# web-platform-tests drafts

Tests for [web-platform-tests](https://github.com/web-platform-tests/wpt), in its `svg/animations/`
directory, for the two clearest disagreements found by [`tools/engines.py`](../../tools/engines.py). Each
quotes the SMIL 3.0 rule it checks. Run them locally in all three engines with
[`tools/wpt.py`](../../tools/wpt.py).

| Test | Chromium 156 | Firefox 157 | WebKit 27.2 | Safari 27.2 |
|---|---|---|---|---|
| `syncbase-zero-duration-interval-end.html`: from offsets, from syncbases | FAIL, FAIL | PASS, PASS | PASS, PASS | PASS, PASS |
| `syncbase-pruned-interval-removes-dependents.html`: chain after, before the gate | FAIL, PASS | PASS, PASS | FAIL, PASS | FAIL, PASS |

The same results in three runs, in Playwright's builds and in Safari (`python tools/wpt.py --engines
safari`), on an Apple-silicon Mac.

**Status:** not submitted yet.
