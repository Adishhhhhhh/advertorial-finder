"""
qualify.py  -  Stage 2 (qualify) and Stage 3 (score) for the advertorial finder.

Stage 2 is binary and mechanical. It fetches every candidate URL and applies the
same seven checks the SOP already asks a human to apply. Everything that fails is
written out WITH THE REASON, so the filter itself can be audited: if the VSL check
starts eating good pages, the rejection log is how you find out.

Stage 3 ranks whatever passed. Scoring SORTS, it never FILTERS. A page with no
archive history is marked duration_unproven and stays in the list, because
longevity tells you what survived and not what is worth studying.

Usage:
    py qualify.py sweep_candidates.json
    py qualify.py urls.txt --workers 12
    py qualify.py sweep_candidates.json --limit 50 --no-score

Outputs (next to this script):
    qualified.jsonl   passers, scored, ranked best first
    rejected.jsonl    failures with the reason each one failed
"""

import os, re, sys, json, time, argparse, html as htmlmod, urllib.request, urllib.error, urllib.parse
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36")

# ---------------------------------------------------------------- stage 2 gates

DISCLAIMER = re.compile(
    r"not an actual news article|advertisement and not a news publication|"
    r"this is an advertisement|not a news publication|advertorial|"
    r"results may vary.{0,400}?advertis", re.I | re.S)

SOFT_CTA = re.compile(
    r"learn more|check availability|claim (?:your |my )?(?:discount|offer|spot)|"
    r"see if you qualify|find out (?:more|if)|get yours|read more|"
    r"check stock|see pricing|try it risk[- ]free", re.I)

HARD_ONLY = re.compile(r"add to cart|buy now", re.I)

BYLINE = re.compile(
    r"\bby\s+[A-Z][a-z]+(?:\s+[A-Z][a-z.]+)?|"
    r"\b(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.?\s+\d{1,2},?\s+20\d\d|"
    r"\b\d{1,2}\s+(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.?\s+20\d\d|"
    r"medical journalist|staff writer|contributor|health (?:desk|editor)", re.I)

VSL_TITLE = re.compile(r"video summary|watch (?:the )?(?:video|presentation)|"
                       r"\bvsl\b|presentation", re.I)
VSL_BODY = re.compile(
    r"watch the full presentation|click to watch|watch this (?:short )?video|"
    r"video time:|free (?:\d+[- ]minute )?presentation|"
    r"the presentation is free to watch", re.I)

TAG_STRIP = re.compile(r"<(script|style|noscript|svg)[^>]*>.*?</\1>", re.I | re.S)
TAGS = re.compile(r"<[^>]+>")

MIN_WORDS = 400


import threading

# Per-domain throttle. Candidates arrive grouped by brand, so a naive thread pool
# fires every request for one store at once and earns a 429 for the whole batch.
# On the first full run that silently rejected 253 of 343 candidates as if they
# had failed qualification, when they had never been fetched at all.
_DOMAIN_LOCKS = {}
_LOCKS_GUARD = threading.Lock()
DOMAIN_DELAY = 1.5


def _domain_lock(host):
    with _LOCKS_GUARD:
        if host not in _DOMAIN_LOCKS:
            _DOMAIN_LOCKS[host] = [threading.Lock(), 0.0]
        return _DOMAIN_LOCKS[host]


def fetch(url, timeout=20, throttle=True, retries=2):
    host = urllib.parse.urlparse(url).netloc
    req = urllib.request.Request(url, headers={"User-Agent": UA,
                                               "Accept-Language": "en-US,en;q=0.9"})
    for attempt in range(retries + 1):
        if throttle and host:
            lock, last = _domain_lock(host)
            with lock:
                wait = DOMAIN_DELAY - (time.time() - _DOMAIN_LOCKS[host][1])
                if wait > 0:
                    time.sleep(wait)
                _DOMAIN_LOCKS[host][1] = time.time()
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.geturl(), r.read().decode("utf-8", "replace")
        except urllib.error.HTTPError as e:
            if e.code in (429, 503) and attempt < retries:
                time.sleep(4 * (attempt + 1) + DOMAIN_DELAY)
                continue
            raise


def visible_text(html):
    h = TAG_STRIP.sub(" ", html)
    h = TAGS.sub(" ", h)
    h = re.sub(r"&[a-z]+;|&#\d+;", " ", h)
    return re.sub(r"\s+", " ", h).strip()


def page_title(html):
    m = re.search(r"<title[^>]*>(.*?)</title>", html, re.I | re.S)
    if not m:
        return ""
    # Titles are full of &ndash; &amp; &#39; and reading them raw is miserable.
    return re.sub(r"\s+", " ", htmlmod.unescape(m.group(1))).strip()


FIRST_PERSON = re.compile(r"\b(I|I'd|I'm|I've|my|me)\b")
# 15 rather than 25: advertorial pull-quotes are frequently short ("I was
# skeptical.", "It just works."), and the earlier floor missed all of them.
# We match against visible text with tags already stripped, so there are no
# HTML attribute values to false-positive on.
QUOTED = re.compile(r"[\"“][^\"”]{15,300}[\"”]")
EDITORIAL = re.compile(
    r"\d+\s+reasons|\breasons? why\b|here'?s (?:what|why|how)|"
    r"what (?:happened|nobody|doctors)|the (?:real|hidden) (?:reason|cause)|"
    r"most people|according to|studies show|it turns out", re.I)

# Hard gates fail outright. Format signals are scored against a threshold,
# because the SOP itself says "fewer than 4 of 5 checked, skip" rather than
# demanding every box. The disclaimer in particular is an artifact of the
# presell/affiliate ecosystem that channels A and B search; first-party brand
# advertorials found by the sitemap sweep frequently carry no fine print at
# all. Requiring it silently deletes everything channel D produces.
SIGNAL_THRESHOLD = 3


# Second line of defence. Even with the sweep's noise filter, utility pages
# arrive from other channels (a dork can surface a terms page). They are long,
# old, and stable, which is exactly the profile the scorer rewards, so they
# must be excluded on identity rather than left to the format threshold.
UTILITY = re.compile(
    r"/pages/[^/?#]*(privacy|terms|tracking|shipping|returns?|refund|"
    r"contact|faq|careers?|accessibility|cookie|legal|disclaimer|imprint|"
    r"wholesale|affiliate-program|sitemap|account|login|gift-card)",
    re.I,
)


def qualify(url, seen):
    """Return (verdict, record). verdict is 'pass' or a failure reason."""
    rec = {"url": url}

    if url.rstrip("/") in seen:
        return "already_in_ledger", rec

    if UTILITY.search(url):
        return "utility_page", rec

    try:
        final, html = fetch(url)
    except urllib.error.HTTPError as e:
        return f"http_{e.code}", rec
    except Exception as e:
        return f"unreachable:{type(e).__name__}", rec

    rec["final_url"] = final
    # a lander that redirects to the shop root is dead
    if urllib.parse.urlparse(final).path.strip("/") in ("", "index", "home"):
        return "redirected_to_homepage", rec

    title = page_title(html)
    text = visible_text(html)
    words = len(text.split())
    rec["title"] = title
    rec["words"] = words
    rec["_head"] = text[:3000]

    # VSL check runs before the word gate, because a VSL bridge is short by design
    if (VSL_TITLE.search(title) or VSL_BODY.search(text[:4000])) and words < 1200:
        return "vsl_bridge", rec

    if words < MIN_WORDS:
        return f"too_thin:{words}w", rec

    fp = len(FIRST_PERSON.findall(text)) / max(words, 1) * 1000

    sig = {
        "disclaimer": bool(DISCLAIMER.search(text)),
        "byline": bool(BYLINE.search(text[:3000])),
        "soft_cta": bool(SOFT_CTA.search(text)),
        "narrative": fp >= 8 or bool(QUOTED.search(text)),
        "editorial": bool(EDITORIAL.search(text)),
    }
    rec["signals"] = sig
    rec["first_person_per_1k"] = round(fp, 1)
    rec["signal_count"] = sum(sig.values())

    if HARD_ONLY.search(text) and not sig["soft_cta"] and rec["signal_count"] < 4:
        return "reads_as_product_page", rec

    if rec["signal_count"] < SIGNAL_THRESHOLD:
        missing = ",".join(k for k, v in sig.items() if not v)
        return f"below_threshold:{rec['signal_count']}of5_missing_{missing}", rec

    return "pass", rec


# ---------------------------------------------------------------- stage 3 score

CDX = "http://web.archive.org/cdx/search/cdx?url={}&output=json&fl=timestamp,statuscode&collapse=timestamp:6&limit=400"


def archive_months(url):
    """Months between first and last successful archive capture. None if never archived."""
    target = re.sub(r"^https?://", "", url).rstrip("/")
    try:
        _, body = fetch(CDX.format(urllib.parse.quote(target, safe="")), timeout=45)
        rows = json.loads(body or "[]")
    except Exception:
        return None
    stamps = [r[0] for r in rows[1:] if len(r) > 1 and r[1].startswith("2")]
    if not stamps:
        return None
    try:
        a = datetime.strptime(min(stamps)[:8], "%Y%m%d")
        b = datetime.strptime(max(stamps)[:8], "%Y%m%d")
    except Exception:
        return None
    return round((b - a).days / 30.44, 1), min(stamps)[:8], max(stamps)[:8]


VARIANT = re.compile(r"^(.*?)[-_]?(\d{1,4})$")


def neighbour_probe(url, span=5):
    """Probe numbered siblings. Live page + dead neighbours = it won its split test."""
    parts = url.rstrip("/").rsplit("/", 1)
    if len(parts) != 2:
        return None
    base, slug = parts
    m = VARIANT.match(slug)
    if not m:
        return None
    stem, num = m.group(1), int(m.group(2))
    width = len(m.group(2))
    live, dead = [], []
    for n in range(max(0, num - span), num + span + 1):
        if n == num:
            continue
        cand = f"{base}/{stem}{'' if stem.endswith('-') or stem.endswith('_') else ''}{str(n).zfill(width)}"
        try:
            req = urllib.request.Request(cand, headers={"User-Agent": UA}, method="HEAD")
            with urllib.request.urlopen(req, timeout=8) as r:
                (live if r.status == 200 else dead).append(n)
        except Exception:
            dead.append(n)
    return {"variant_number": num, "live_neighbours": live, "dead_neighbours": dead}


PAGE_DATE = re.compile(
    r"((?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.?\s+\d{1,2},?\s+(20\d\d))", re.I)


def score(rec, do_probe=True):
    pts, why = 0.0, []

    am = archive_months(rec["url"])
    if am:
        months, first, last = am
        rec["archive_months"] = months
        rec["archive_first"], rec["archive_last"] = first, last
        pts += min(months, 72) / 12 * 3          # capped at 6 years, weight x3
        why.append(f"archive {months}mo x3")
    else:
        rec["archive_months"] = None
        rec["duration_unproven"] = True
        why.append("duration unproven")

    if do_probe:
        nb = neighbour_probe(rec["url"])
        if nb:
            rec["neighbours"] = nb
            if nb["dead_neighbours"] and not nb["live_neighbours"]:
                pts += 2 * 2
                why.append("sole survivor x2")
            elif nb["dead_neighbours"]:
                pts += 1 * 2
                why.append("outlived siblings x2")
            pts += min(nb["variant_number"], 30) / 10
            why.append(f"variant {nb['variant_number']} x1")

    m = PAGE_DATE.search(rec.get("_head", "") or rec.get("title", ""))
    if m:
        rec["page_date"] = m.group(1)
        try:
            if int(m.group(2)) >= datetime.now().year - 1:
                pts += 1
                why.append("recent page date x1")
        except Exception:
            pass

    rec["score"] = round(pts, 2)
    rec["score_why"] = why
    return rec


# ---------------------------------------------------------------------- driver

LOCALE = re.compile(r"^/[a-z]{2}(?:-[a-z]{2})?(?=/)", re.I)


def canonical(url):
    """Locale-stripped form, so /de-de/pages/x and /pages/x are one page."""
    m = re.match(r"^(https?://[^/]+)(/.*)$", url)
    if not m:
        return url.rstrip("/")
    return (m.group(1) + LOCALE.sub("", m.group(2), count=1)).rstrip("/")


def load_candidates(path):
    if path.endswith(".json"):
        data = json.load(open(path, encoding="utf-8"))
        urls = []
        for row in data:
            urls += row.get("hits", [])
    else:
        urls = [l.strip() for l in open(path, encoding="utf-8")
                if l.strip() and not l.startswith("#")]

    # Collapse locale duplicates, keeping the shortest form of each page.
    best = {}
    for u in urls:
        c = canonical(u)
        if c not in best or len(u) < len(best[c]):
            best[c] = u.rstrip("/")
    return list(best.values())


HERE = os.path.dirname(os.path.abspath(__file__))
RUNS = os.path.join(HERE, "runs")
QUALIFIED = os.path.join(RUNS, "qualified.jsonl")
REJECTED = os.path.join(RUNS, "rejected.jsonl")


def load_ledger(path=QUALIFIED):
    seen = set()
    try:
        for line in open(path, encoding="utf-8"):
            try:
                seen.add(json.loads(line)["url"].rstrip("/"))
            except Exception:
                continue
    except FileNotFoundError:
        pass
    return seen


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("candidates")
    ap.add_argument("--workers", type=int, default=10)
    ap.add_argument("--limit", type=int)
    ap.add_argument("--no-score", action="store_true")
    ap.add_argument("--no-probe", action="store_true")
    ap.add_argument("--delay", type=float, default=DOMAIN_DELAY,
                    help="seconds between requests to the same domain (raise on 429s)")
    args = ap.parse_args()

    globals()["DOMAIN_DELAY"] = args.delay

    urls = load_candidates(args.candidates)
    if args.limit:
        urls = urls[:args.limit]

    seen = load_ledger()
    print(f"[qualify] candidates : {len(urls)}")
    print(f"[qualify] in ledger  : {len(seen)}\n")

    passed, rejected = [], []
    t0 = time.time()

    def work(u):
        try:
            return qualify(u, seen)
        except Exception as e:
            return f"crash:{type(e).__name__}", {"url": u}

    with ThreadPoolExecutor(max_workers=args.workers) as ex:
        for i, (verdict, rec) in enumerate(ex.map(work, urls), 1):
            if verdict == "pass":
                passed.append(rec)
            else:
                rec["reason"] = verdict
                rejected.append(rec)
            if i % 25 == 0:
                print(f"  ... {i}/{len(urls)}  pass {len(passed)}  reject {len(rejected)}")

    print(f"\n[qualify] STAGE 2 done in {time.time()-t0:.0f}s")
    print(f"[qualify] passed : {len(passed)}")
    print(f"[qualify] failed : {len(rejected)}")

    tally = {}
    for r in rejected:
        tally[r["reason"].split(":")[0]] = tally.get(r["reason"].split(":")[0], 0) + 1
    print("[qualify] rejection reasons:")
    for k, v in sorted(tally.items(), key=lambda x: -x[1]):
        print(f"    {v:>4}  {k}")

    if not args.no_score and passed:
        print(f"\n[qualify] STAGE 3 scoring {len(passed)} pages...")
        t1 = time.time()
        with ThreadPoolExecutor(max_workers=6) as ex:
            passed = list(ex.map(lambda r: score(r, not args.no_probe), passed))
        passed.sort(key=lambda r: -r["score"])
        print(f"[qualify] scored in {time.time()-t1:.0f}s")

    os.makedirs(RUNS, exist_ok=True)
    with open(QUALIFIED, "a", encoding="utf-8") as f:
        for r in passed:
            r.pop("_head", None)
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    with open(REJECTED, "w", encoding="utf-8") as f:
        for r in rejected:
            r.pop("_head", None)
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    print("\n" + "=" * 72)
    print("TOP FINDS  (score sorts, it never filters)")
    print("=" * 72)
    for r in passed[:30]:
        # --no-score leaves these keys absent; print the row anyway rather than
        # crashing on the last line after all the work is already done.
        dur = f"{r['archive_months']}mo" if r.get("archive_months") else "unproven"
        sc = f"{r['score']:>6.2f}" if r.get("score") is not None else "     -"
        print(f"{sc}  {dur:>9}  {r['words']:>5}w  {r['url']}")
        if r.get("title"):
            print(f"{'':>8}{r['title'][:88]}")

    print(f"\n[qualify] wrote runs/qualified.jsonl ({len(passed)}) and runs/rejected.jsonl ({len(rejected)})")


if __name__ == "__main__":
    main()
