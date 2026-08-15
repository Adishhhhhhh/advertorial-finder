"""
find.py  -  Find me an advertorial to study. Right now.

This is the whole tool for most people. No setup, no precompute, no waiting for
a corpus to build. It goes out, finds a few live advertorials, checks they are
real, ranks them, shows you why, and offers to keep them.

    python find.py                          1 to 3, any niche
    python find.py -n 1                      just one
    python find.py sleep                     constrain by niche
    python find.py "hair loss women over 50" constrain by anything
    python find.py --fresh                   skip the cache, go hunting

It works cache-first. Anything already qualified and unread is served
instantly; only when that runs dry does it go discover more. So the first run
takes a couple of minutes and later runs are usually immediate.

Discovery stops the moment it has enough. It never sweeps the whole corpus,
because you asked for three advertorials and not for two hundred.
"""

import os, re, sys, json, time, random, argparse, subprocess
from concurrent.futures import ThreadPoolExecutor

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import qualify as q
import sitemap_sweep as sw

RUNS = os.path.join(HERE, "runs")
QUALIFIED = os.path.join(RUNS, "qualified.jsonl")
FINDS = os.path.join(RUNS, "finds.jsonl")
SWEPT = os.path.join(RUNS, "swept.json")
REPO = os.path.join(HERE, "Advertorial-Repo")
PY = sys.executable

# Word-boundaried, always. Without \b the substring "ear" inside "Beard"
# classified a beard supplement as hearing, and "slim" inside "SLIMMEST"
# classified a wallet as weight loss.
NICHE_HINTS = {
    "sleep": r"\b(sleep|insomnia|mattress|bedsheet|grounding|melatonin|snor\w*)\b",
    "gut": r"\b(gut|bloat\w*|digest\w*|probiotic\w*|microbiome|colon)\b|leaky.?gut",
    "joint": r"\b(joint|knee|arthritis|mobility|posture|sciatica)\b",
    "hair": r"\b(hair|balding|thinning|scalp|regrow\w*|follicle\w*)\b",
    "skin": r"\b(skin|wrinkle\w*|collagen|serum|acne|cellulite)\b|anti.?aging",
    "weight": r"weight.?loss|body.?fat|belly.?fat|\b(metabolism|glp|appetite)\b",
    "energy": r"\b(energy|fatigue|nootropic\w*|mushroom\w*|adhd|focus)\b|brain.?fog",
    "hearing": r"\b(hearing|tinnitus|ears?|ringing)\b",
    "menopause": r"\b(menopause|perimenopause|hormone\w*)\b|hot.?flash\w*",
    "oral": r"\b(dental|teeth|tooth|gums?|whitening)\b|bad.?breath",
    "pet": r"\b(pet|pets|dog|dogs|cat|cats|puppy|kitten|vet)\b",
    "mens": r"\b(prostate|testosterone|beard|libido)\b",
    "beauty": r"\b(makeup|lipstick|lash\w*|brows?|foundation|mascara)\b",
    "immune": r"\b(immune|immunity|inflammation)\b",
}

# Slugs that look like editorial rather than a product page. Used only to
# decide what to check FIRST, never to exclude anything.
ADVERTORIAL_SHAPED = re.compile(
    r"advertorial|listicle|presell|\badv\d|-adv\b|\d-reasons|reasons-why|"
    r"story|why-|how-i|the-hidden|discover|breakthrough|secret|review",
    re.I)


def load_jsonl(path):
    out = {}
    try:
        for line in open(path, encoding="utf-8"):
            line = line.strip()
            if line:
                r = json.loads(line)
                out[r["url"].rstrip("/")] = r
    except FileNotFoundError:
        pass
    return out


def constraint_pattern(text):
    if not text:
        return None, None
    key = text.strip().lower()
    if key in NICHE_HINTS:
        return re.compile(NICHE_HINTS[key], re.I), key
    words = [w for w in re.split(r"[^a-z0-9]+", key) if len(w) > 2]
    if not words:
        return None, key
    return re.compile("|".join(re.escape(w) for w in words), re.I), key


def matches(rec, pat):
    if pat is None:
        return True
    return bool(pat.search(rec.get("url", "") + " " + (rec.get("title") or "")))


def guess_niche(rec):
    hay = (rec.get("url", "") + " " + (rec.get("title") or "")).lower()
    for niche, pat in NICHE_HINTS.items():
        if re.search(pat, hay):
            return niche
    return "unsorted"


def why(rec):
    bits = []
    if rec.get("archive_months"):
        bits.append(f"live {rec['archive_months']} months")
    else:
        bits.append("duration unproven")
    nb = rec.get("neighbours") or {}
    if nb.get("dead_neighbours") and not nb.get("live_neighbours"):
        bits.append(f"sole survivor of variant {nb.get('variant_number')}")
    elif nb.get("variant_number"):
        bits.append(f"variant {nb['variant_number']}")
    bits.append(f"{rec.get('words', 0):,} words")
    return " · ".join(bits)


def _read_list(name):
    try:
        return [l.strip().split("#")[0].strip()
                for l in open(os.path.join(HERE, name), encoding="utf-8")
                if l.strip() and not l.strip().startswith("#")]
    except FileNotFoundError:
        return []


def brand_pool(tier="both"):
    """Two corpora, deliberately different populations.

    brands.txt is a watchlist of notable DTC brands. It is curated precisely
    because those brands are worth following, which makes it the wrong place
    to look for strange advertorials: nobody curates the company selling a
    power-grid backup or a kids camera, and that is where the most instructive
    direct response tends to be.

    wildcards.txt is that other population. Small single-product brands and the
    fake-news aggregators that host advertorials for dozens of advertisers.
    Denser in advertorials per domain, and far stranger.

    Default samples both with a bias toward wildcards, because mainstream
    brands have longer archives and would otherwise win every ranking.
    """
    main = [(d, "mainstream") for d in _read_list("brands.txt")]
    wild = [(d, "wildcard") for d in _read_list("wildcards.txt")]
    if tier == "mainstream":
        return main
    if tier == "wildcard":
        return wild or main
    if not wild:
        return main

    random.shuffle(main)
    random.shuffle(wild)
    mixed, mi, wi = [], 0, 0
    # roughly 2 wildcards for every mainstream domain
    while mi < len(main) or wi < len(wild):
        for _ in range(2):
            if wi < len(wild):
                mixed.append(wild[wi]); wi += 1
        if mi < len(main):
            mixed.append(main[mi]); mi += 1
    return mixed


def shown_recently():
    try:
        return json.load(open(os.path.join(RUNS, "shown.json"), encoding="utf-8"))
    except Exception:
        return {}


def mark_shown(hosts):
    d = shown_recently()
    now = int(time.time())
    for h in hosts:
        d[h] = now
    os.makedirs(RUNS, exist_ok=True)
    json.dump(d, open(os.path.join(RUNS, "shown.json"), "w", encoding="utf-8"), indent=1)


def recently_swept():
    try:
        return json.load(open(SWEPT, encoding="utf-8"))
    except Exception:
        return {}


def mark_swept(domains):
    d = recently_swept()
    now = int(time.time())
    for x in domains:
        d[x] = now
    os.makedirs(RUNS, exist_ok=True)
    json.dump(d, open(SWEPT, "w", encoding="utf-8"), indent=1)


def discover(need, pat, want_label, budget_s=240, verbose=True, tier="both"):
    """Sweep a few brands and qualify until we have a decent shortlist.

    Deliberately collects more than asked for, then ranks. Taking the first
    N that pass gives you whatever happened to be checked first, which on the
    first cold run was two product pages from the same company. Over-collecting
    and sorting costs a little time and changes the quality of the answer.
    """
    pool_tiered = brand_pool(tier)
    if not pool_tiered:
        return []
    seen_before = recently_swept()
    # least recently swept first; the interleave from brand_pool is preserved
    # within equal timestamps, so the wildcard bias survives the sort
    pool_tiered.sort(key=lambda dt: seen_before.get(dt[0], 0))
    pool = [d for d, _ in pool_tiered]
    tier_of = dict(pool_tiered)

    started = time.time()
    passed, tried_domains = [], []
    already = set(load_jsonl(QUALIFIED)) | set(load_jsonl(FINDS))

    target = min(max(need * 2, 4), 8)    # shortlist to rank, not a quota to fill
    per_brand = {}
    i = 0
    while i < len(pool) and len(passed) < target and time.time() - started < budget_s:
        batch = pool[i:i + 3]
        i += 3
        if verbose:
            print(f"  looking at {', '.join(batch)}")
        with ThreadPoolExecutor(max_workers=3) as ex:
            results = list(ex.map(sw.probe, batch))
        tried_domains += [r["domain"] for r in results if r.get("domain")]

        cands = []
        for r in results:
            cands += r.get("hits", [])
        cands = [c for c in cands if c.rstrip("/") not in already]
        if pat is not None:
            narrowed = [c for c in cands if pat.search(c)]
            cands = narrowed or ([] if want_label else cands)
        if not cands:
            continue

        # Check editorial-shaped slugs first. Same candidates either way, but
        # the ones likely to be advertorials get fetched before the budget runs
        # out, instead of after a dozen product pages.
        random.shuffle(cands)
        cands.sort(key=lambda c: 0 if ADVERTORIAL_SHAPED.search(c) else 1)
        for c in cands[:10]:
            if len(passed) >= target or time.time() - started > budget_s:
                break
            host = c.split("/")[2].replace("www.", "")
            # One per brand until we have enough DISTINCT brands. Only after
            # that will a second page from the same brand be considered. A
            # brand with a deep advertorial library will otherwise supply the
            # whole shortlist, and three pages from one company is not three
            # advertorials to study.
            distinct = len({r["url"].split("/")[2].replace("www.", "") for r in passed})
            cap = 1 if distinct < need else 2
            if per_brand.get(host, 0) >= cap:
                continue
            verdict, rec = q.qualify(c, already)
            already.add(c.rstrip("/"))
            if verdict == "pass":
                rec.pop("_head", None)
                rec["tier"] = tier_of.get(host.replace("www.", ""), "unknown")
                passed.append(rec)
                per_brand[host] = per_brand.get(host, 0) + 1
                if verbose:
                    mark = "*" if rec["tier"] == "wildcard" else " "
                    print(f"   {mark}found: {(rec.get('title') or c)[:56]}")

    if tried_domains:
        mark_swept(tried_domains)
    return passed


def spread(records, need, max_per_brand=1):
    """Top N, spread across brands and away from brands shown recently.

    Two things this fixes. Ranking alone returned three pages from one company,
    because a brand with a deep advertorial library dominates the top of any
    sorted list. And consecutive runs returned the same brands, because nothing
    remembered what was shown last time.
    """
    recent = shown_recently()
    now = time.time()

    def rank(r):
        host = r["url"].split("/")[2].replace("www.", "")
        score = r.get("score") or 0
        # a brand shown in the last three days sinks unless nothing else exists
        age_days = (now - recent.get(host, 0)) / 86400 if host in recent else 999
        penalty = 6 if age_days < 3 else (2 if age_days < 10 else 0)
        return -(score - penalty)

    records.sort(key=rank)
    out, counts = [], {}
    # Strictly one per brand. Returning fewer results is better than padding
    # with a second page from a brand already shown, which is what "3 finds"
    # turning into 2 from one company actually was.
    for r in records:
        if len(out) == need:
            break
        h = r["url"].split("/")[2].replace("www.", "")
        if counts.get(h, 0) >= max_per_brand:
            continue
        out.append(r)
        counts[h] = counts.get(h, 0) + 1
    return out


def present(picked, pool_note):
    print()
    print("=" * 70)
    print(f"{len(picked)} ADVERTORIAL{'S' if len(picked) != 1 else ''} TO STUDY")
    if pool_note:
        print(pool_note)
    print("=" * 70)
    for i, r in enumerate(picked, 1):
        print()
        print(f"{i}. {(r.get('title') or 'untitled').strip()[:66]}")
        print(f"   {r['url']}")
        tier = r.get("tier", "")
        badge = "  [wildcard]" if tier == "wildcard" else ""
        print(f"   niche: {guess_niche(r)}   score {r.get('score') or 0:.2f}{badge}")
        print(f"   {why(r)}")
    print()


def save_text(rec, niche):
    """Fallback capture with no dependencies at all.

    PDF needs Playwright, which is a 150MB browser download most people will
    not have on a first run. Failing to save at that point is the worst
    possible moment to fail: the page was found, judged, and chosen, and
    presell domains rotate within weeks. So always keep something. The copy is
    the part worth studying anyway; the PDF only adds layout.
    """
    from datetime import date
    try:
        _, html = q.fetch(rec["url"])
    except Exception as e:
        print(f"    could not fetch: {type(e).__name__}")
        return False

    slug = re.sub(r"[^a-z0-9]+", "-", rec["url"].split("/")[2] + "-" +
                  rec["url"].rstrip("/").rsplit("/", 1)[-1].lower())[:70].strip("-")
    stem = f"{date.today().isoformat()}_{niche}_{slug}"
    text = q.visible_text(html)

    with open(os.path.join(REPO, stem + ".txt"), "w", encoding="utf-8") as f:
        f.write(f"{rec.get('title') or ''}\n{rec['url']}\n")
        f.write(f"captured {date.today().isoformat()}  ·  {why(rec)}\n")
        f.write("=" * 70 + "\n\n")
        # one sentence per line, so the structure is readable in a diff or an editor
        f.write(re.sub(r"(?<=[.!?]) +", "\n", text))
    with open(os.path.join(REPO, stem + ".html"), "w", encoding="utf-8") as f:
        f.write(html)
    print(f"    saved copy + html: {stem}.txt")
    return True


def save(picked, auto_yes, mobile=False):
    if auto_yes:
        answer = "y"
    else:
        try:
            answer = input(f"Save {'these' if len(picked) > 1 else 'this'} "
                           f"to Advertorial-Repo/? [y/N] ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            print()
            return
    if answer not in ("y", "yes"):
        print("Not saved. They stay in the list for next time.")
        return

    os.makedirs(REPO, exist_ok=True)
    ok = 0
    for r in picked:
        niche = guess_niche(r)
        print(f"\ncapturing {r['url']}")
        cmd = [PY, os.path.join(HERE, "pdf_save.py"), r["url"], niche]
        if mobile:
            cmd.append("--both")
        p = subprocess.run(cmd, cwd=HERE, capture_output=True, text=True,
                           encoding="utf-8", errors="replace")
        out = (p.stdout or "") + (p.stderr or "")
        if "SUCCESS" in out:
            ok += 1
            print("  saved as PDF")
        else:
            if "playwright" in out.lower():
                print("  Playwright not installed, saving the copy instead.")
            else:
                print(f"  PDF failed ({out.strip()[-90:]}), saving the copy instead.")
            if save_text(r, niche):
                ok += 1
        subprocess.run([PY, os.path.join(HERE, "ledger.py"), "add", r["url"],
                        niche, "--score", str(r.get("score") or 0)],
                       cwd=HERE, capture_output=True)
    print(f"\n{ok} saved to Advertorial-Repo/")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("constraint", nargs="*", help="niche or free text, optional")
    ap.add_argument("-n", "--count", type=int, default=3)
    ap.add_argument("--fresh", action="store_true", help="ignore the cache, go hunting")
    ap.add_argument("--yes", action="store_true")
    ap.add_argument("--no-save", action="store_true")
    ap.add_argument("--mobile", action="store_true")
    ap.add_argument("--budget", type=int, default=240, help="seconds to spend hunting")
    ap.add_argument("--tier", choices=["both", "wildcard", "mainstream"], default="both",
                    help="wildcard = small odd single-product brands and aggregators")
    args = ap.parse_args()

    text = " ".join(args.constraint).strip()
    pat, label = constraint_pattern(text)
    need = max(1, args.count)

    cached = load_jsonl(QUALIFIED)
    saved = set(load_jsonl(FINDS))
    picked, note = [], ""

    if not args.fresh:
        pool = [r for u, r in cached.items()
                if u not in saved and matches(r, pat)]
        if args.tier != "both":
            pool = [r for r in pool if r.get("tier", "mainstream") == args.tier]
        picked = spread(pool, need)
        if picked:
            note = f"from {len(pool)} already qualified" + (f" in '{label}'" if label else "")

    if len(picked) < need:
        short = need - len(picked)
        print(f"Hunting for {short} more{' in ' + label if label else ''}. "
              f"This takes a minute or two.")
        found = discover(short, pat, bool(label), budget_s=args.budget, tier=args.tier)
        if found:
            print(f"\n  scoring {len(found)} candidates and taking the best...")
            with ThreadPoolExecutor(max_workers=4) as ex:
                found = list(ex.map(lambda r: q.score(r, True), found))
            os.makedirs(RUNS, exist_ok=True)
            # everything found goes in the cache, so nothing is wasted; only the
            # best are shown now and the rest wait for the next run
            with open(QUALIFIED, "a", encoding="utf-8") as f:
                for r in found:
                    f.write(json.dumps(r, ensure_ascii=False) + "\n")
            picked += spread(found, short)

    if not picked:
        print("\nNothing found this run.")
        print("Widen it: drop the constraint, raise --budget, or use the dorks")
        print("in SOP.md, which reach niches no brand list covers.")
        sys.exit(1)

    picked = spread(picked, need)
    if len(picked) < need:
        print(f"\nFound {len(picked)} rather than {need}, one per brand.")
        print("Raise --budget to sweep more brands, or run again later.")
    mark_shown([r["url"].split("/")[2].replace("www.", "") for r in picked])
    present(picked, note)
    if not args.no_save:
        save(picked, args.yes, args.mobile)


if __name__ == "__main__":
    main()
