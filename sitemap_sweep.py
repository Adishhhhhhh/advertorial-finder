"""
sitemap_sweep.py  -  Channel D: harvest advertorial candidates from known brands' page sitemaps.

Most DTC brands run on Shopify, which exposes every /pages/ URL at
/sitemap_pages_1.xml. Brands do not delete losing advertorial variants, they
just stop sending traffic. So the sitemap is a public archive of every
advertorial and listicle a brand has ever tested, including the numbered
variant families that reveal which one won.

This produces CANDIDATES, not verified finds. Every hit still goes through the
qualification checklist (story lead, named persona, soft CTA, disclaimer, live,
not a VSL) before it is worth saving.

Usage:
    py sitemap_sweep.py brands.txt
    py sitemap_sweep.py brands.txt --out candidates.json
    py sitemap_sweep.py --domain groundingwell.com

brands.txt: one per line. Either a bare domain (groundingwell.com) or a brand
name (Grounding Well), in which case candidate domains are guessed. Lines
starting with # are ignored. Domains are far more reliable than names; roughly
half of naive name guesses resolve.
"""

import os, re, sys, json, time, threading, argparse, urllib.request, urllib.error, urllib.parse
from concurrent.futures import ThreadPoolExecutor

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"

# Shopify rate-limits hard and the block PERSISTS for a while after you trip it.
# An unthrottled sweep does not merely fail; it poisons the next several runs and
# every failure looks like "this brand has no sitemap". Throttle per host, back
# off on 429, and keep worker counts modest.
_LOCKS = {}
_GUARD = threading.Lock()
DOMAIN_DELAY = 1.0


def _host_lock(host):
    with _GUARD:
        if host not in _LOCKS:
            _LOCKS[host] = [threading.Lock(), 0.0]
        return _LOCKS[host]

# Slug patterns that mark an advertorial, a listicle, or a presell.
# Tuned on 343 real hits across 50 brands; see docs for what each catches.
SLUG = re.compile(
    r"advertorial|presell|listicle|"
    r"/adv\d|-adv\d|-adv$|_adv|adv-|"
    r"review-\d|-v\d$|"
    r"\d-reasons|reasons-why|\d-signs|signs-|"
    r"why-|how-i-|how-this|the-hidden|hidden-|the-real-reason|"
    r"doctors|breakthrough|discovery|secret|testimonial|"
    r"funnel|story",
    re.I,
)

# Slugs that match the pattern but are almost never advertorials.
NOISE = re.compile(r"our-story|why-buy-from-us|brand-story|why-us|our-mission|success-story", re.I)


def fetch(url, timeout=20, retries=2):
    host = urllib.parse.urlparse(url).netloc
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    for attempt in range(retries + 1):
        if host:
            lock, _ = _host_lock(host)
            with lock:
                wait = DOMAIN_DELAY - (time.time() - _LOCKS[host][1])
                if wait > 0:
                    time.sleep(wait)
                _LOCKS[host][1] = time.time()
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.read().decode("utf-8", "replace")
        except urllib.error.HTTPError as e:
            if e.code in (429, 503) and attempt < retries:
                time.sleep(5 * (attempt + 1))
                continue
            raise


def candidate_domains(entry):
    entry = entry.strip()
    if "." in entry and " " not in entry:
        return [entry.replace("https://", "").replace("http://", "").strip("/")]
    base = re.sub(r"[^a-z0-9]", "", entry.lower())
    if not base:
        return []
    return [f"{base}.com", f"the{base}.com", f"get{base}.com", f"{base}.co"]


def page_locs(domain):
    """Return (locs, reason). reason is None on success, else why it failed.

    Distinguishing "this brand has no page sitemap" from "we got rate limited"
    matters more than it looks. A log that collapses them reports a clean-looking
    zero and hides the fact that nothing was ever actually checked.
    """
    reason = None
    try:
        body = fetch(f"https://{domain}/sitemap_pages_1.xml")
        locs = re.findall(r"<loc>([^<]+)</loc>", body)
        if locs:
            return locs, None
    except urllib.error.HTTPError as e:
        reason = f"http_{e.code}"
    except Exception as e:
        reason = type(e).__name__

    try:
        body = fetch(f"https://{domain}/sitemap.xml")
        nested = [l for l in re.findall(r"<loc>([^<]+)</loc>", body) if "sitemap_pages" in l]
        out = []
        for n in nested[:5]:
            try:
                out += re.findall(r"<loc>([^<]+)</loc>", fetch(n))
            except Exception:
                continue
        if out:
            return out, None
        return None, reason or "no_pages_sitemap"
    except urllib.error.HTTPError as e:
        return None, f"http_{e.code}"
    except Exception as e:
        return None, reason or type(e).__name__


def probe(entry):
    last = None
    for d in candidate_domains(entry):
        locs, reason = page_locs(d)
        last = reason
        if not locs:
            continue
        hits = [
            l for l in locs
            if "/pages/" in l and SLUG.search(l) and not NOISE.search(l)
        ]
        return {"entry": entry, "domain": d, "pages": len(locs), "hits": sorted(hits)}
    return {"entry": entry, "domain": None, "pages": 0, "hits": [], "reason": last}


def variant_families(hits):
    """Group hits that share a stem and differ by a trailing number.

    A numbered family is the strongest signal on the page: the brand ran a
    split test and the surviving high numbers are what it kept iterating.
    """
    fams = {}
    for h in hits:
        slug = h.rstrip("/").rsplit("/", 1)[-1]
        stem = re.sub(r"[-_]?\d+$", "", slug)
        if stem != slug:
            fams.setdefault(stem, []).append(slug)
    return {k: sorted(v) for k, v in fams.items() if len(v) > 1}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("brands", nargs="?", help="file with one brand or domain per line")
    ap.add_argument("--domain", help="sweep a single domain instead of a file")
    ap.add_argument("--out", default="sweep_candidates.json")
    ap.add_argument("--workers", type=int, default=6,
                    help="keep this modest; Shopify 429s persist after you trip them")
    ap.add_argument("--delay", type=float, default=DOMAIN_DELAY,
                    help="seconds between requests to the same host")
    args = ap.parse_args()

    globals()["DOMAIN_DELAY"] = args.delay

    if args.domain:
        entries = [args.domain]
    elif args.brands:
        entries = [
            l.strip() for l in open(args.brands, encoding="utf-8")
            if l.strip() and not l.startswith("#")
        ]
    else:
        ap.error("give a brands file or --domain")

    print(f"[sweep] entries: {len(entries)}")
    results = []
    with ThreadPoolExecutor(max_workers=args.workers) as ex:
        for r in ex.map(probe, entries):
            results.append(r)

    resolved = [r for r in results if r["domain"]]
    withhits = [r for r in resolved if r["hits"]]
    total = sum(len(r["hits"]) for r in withhits)

    print(f"[sweep] domains resolved : {len(resolved)}/{len(entries)}")
    print(f"[sweep] brands with hits : {len(withhits)}")
    print(f"[sweep] candidate pages  : {total}\n")

    tally = {}
    for r in results:
        if not r["domain"]:
            tally[r.get("reason") or "unknown"] = tally.get(r.get("reason") or "unknown", 0) + 1
    if tally:
        print("[sweep] unresolved, by reason:")
        for k, v in sorted(tally.items(), key=lambda x: -x[1]):
            print(f"    {v:>4}  {k}")
        if any(k.startswith("http_429") for k in tally):
            print("    NOTE: 429 means never checked, not 'no sitemap'. Re-run those")
            print("          later with --delay 3. The block persists for a while.")
        print()

    for r in sorted(withhits, key=lambda x: -len(x["hits"])):
        fams = variant_families(r["hits"])
        r["families"] = fams
        flag = f"  [{len(fams)} variant famil{'y' if len(fams)==1 else 'ies'}]" if fams else ""
        print(f"### {r['entry']} ({r['domain']}) - {len(r['hits'])} hits of {r['pages']} pages{flag}")
        for h in r["hits"][:8]:
            print("   ", h)
        if len(r["hits"]) > 8:
            print(f"    ... +{len(r['hits']) - 8} more")
        for stem, members in list(fams.items())[:3]:
            print(f"    FAMILY {stem}: {', '.join(members)}")
        print()

    # runs/ is gitignored, so it does not exist in a fresh clone and the
    # quickstart writes straight into it. Create it rather than crashing.
    outdir = os.path.dirname(os.path.abspath(args.out))
    os.makedirs(outdir, exist_ok=True)
    json.dump(results, open(args.out, "w", encoding="utf-8"), indent=1)
    print(f"[sweep] written to {args.out}")
    print("[sweep] these are CANDIDATES. Qualify each one before saving.")


if __name__ == "__main__":
    main()
