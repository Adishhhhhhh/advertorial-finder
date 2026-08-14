# Install, and what it can honestly do

Read the capability ladder before installing anything. Most of this system needs nothing at all, and the two channels with real requirements are the two most people will reach for first.

**Python 3.9 or newer.** Commands here use `py`, the Windows Python launcher. On macOS and Linux substitute `python3`. Verified on Windows with 3.14; the code avoids syntax newer than 3.9 on purpose, so older interpreters work.

---

## The capability ladder

Ordered by payoff, not by difficulty. You can stop at any rung and still have a working system.

### Rung 1 — nothing installed
**Works:** Channel D (sitemap sweep), stages 2 and 3 (qualify and score), Wayback duration lookup, domain resolution.
**Needs:** Python 3.9+. Standard library only.

This is most of the value. The sweep produced 343 candidates and 136 qualified pages on a stock Python install with no dependencies and no accounts.

```bash
py sitemap_sweep.py brands.txt --out runs/candidates.json
py qualify.py runs/candidates.json
```

### Rung 2 — Playwright
**Adds:** PDF capture, so a page you found today still exists when you read it next year.
**Needs:** `pip install -r requirements.txt` then `py -m playwright install chromium` (one time, ~150MB).

Presell domains rotate every few weeks. If you find something good on a throwaway domain, capture it the same day or lose it.

### Rung 3 — a browser you are signed into
**Adds:** Channels A and B, the two disclaimer dorks.
**Needs:** Google, in a normal browser session.

**Read this before you conclude the dorks are broken.** Google serves a bot check to fresh or automated browser profiles and returns nothing. This is not a bad query. Run the dorks in a browser you actually use.

Substituting a different search engine does not work and has been tested. Bing silently strips the phrase quotes and returns dictionary definitions. DuckDuckGo honours the quotes and returns zero results, because its index does not reach these pages. **The fix is a different browser, never a different engine.**

### Rung 4 — a US IP
**Adds:** Channel F, the live chumbox, and the only view of what is being bought right now.
**Needs:** A VPN or US residency.

Outside the US, native widgets fill with locally targeted ads and no amount of trying other publishers fixes it, because every site pulls the same geo-keyed inventory. Channels A and B reach much of the same pages through Google's index, which is not geo-locked, so this rung is a luxury rather than a requirement.

---

## What this cannot do

**It cannot tell you whether a page is profitable.** No outside tool can. Ad platforms return null spend for commercial advertisers. Duration is the best available proxy and it is a proxy: a page can stay live because nobody got round to deleting it.

**It cannot judge copy.** Qualification checks format, not quality. A page can pass every check and still be badly written. Ranking answers "what has survived longest," never "what is best."

**It has no outcome data about itself.** Whether high scores actually predict which advertorials teach you the most is unmeasured, and measuring it takes months of using the thing. `ledger.py` records re-checks so that data can accumulate, and until it does, treat the weights as reasoned rather than validated.

**The sweep only sees brands you give it.** `brands.txt` ships with a verified list, and the system is exactly as good as that list is long. Adding brands is the highest-yield way to improve your results.

**Some sites will rate-limit you.** Candidates arrive grouped by brand, so hitting one store hard earns a 429 for the whole batch. `qualify.py` throttles per domain by default; raise it with `--delay 5` if you still see 429s in the rejection log. **Check that log.** A rejection that reads `http_429` means the page was never tested, not that it failed.

---

## Verifying the install works

```bash
py sitemap_sweep.py --domain groundingwell.com
```

Expect roughly 30 candidate pages and several variant families, including a `sheet-adv` family numbered into the teens.

**If you instead get zero with `http_429` in the reason tally, that is not a broken install.** You are rate-limited, and Shopify's block persists for a while after it is tripped. Wait, then retry with `--delay 3`. The tool tells you this because the alternative was worse: earlier versions reported a clean zero and every rate-limited brand looked like a brand with no sitemap.

If you get zero with a network error, your Python cannot reach the internet. If you get a traceback, open an issue with it.

Then:

```bash
py qualify.py runs/candidates.json --limit 10 --no-probe
```

Expect a mix of passes and rejections with a reason on every rejection. If everything fails with one identical reason, that is the signal something is misconfigured rather than that the pages are bad. It has happened before: an early version rejected every candidate for having no legal disclaimer, and the pages were fine.

---

## Cost of a run

The sweep across 165 brands takes about four minutes and makes roughly 500 requests. Qualification of 343 candidates takes about 25 minutes with throttling on, most of which is waiting politely. Scoring adds one Wayback call per qualified page.

Nothing here costs money. Budget attention instead: 136 qualified advertorials is far more than anyone can actually read, which is why the ranking exists.
