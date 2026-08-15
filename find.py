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


def brand_pool():
    try:
        return [l.strip().split("#")[0].strip()
                for l in open(os.path.join(HERE, "brands.txt"), encoding="utf-8")
                if l.strip() and not l.strip().startswith("#")]
    except FileNotFoundError:
        return []


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


def discover(need, pat, want_label, budget_s=240, verbose=True):
    """Sweep a few brands and qualify until we have a decent shortlist.

    Deliberately collects more than asked for, then ranks. Taking the first
    N that pass gives you whatever happened to be checked first, which on the
    first cold run was two product pages from the same company. Over-collecting
    and sorting costs a little time and changes the quality of the answer.
    """
    pool = brand_pool()
    if not pool:
        return []
    seen_before = recently_swept()
    # least recently swept first, with a shuffle so two runs differ
    random.shuffle(pool)
    pool.sort(key=lambda d: seen_before.get(d, 0))

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
            host = c.split("/")[2]
            # never let one brand fill the shortlist
            if per_brand.get(host, 0) >= max(2, need):
                continue
            verdict, rec = q.qualify(c, already)
            already.add(c.rstrip("/"))
            if verdict == "pass":
                rec.pop("_head", None)
                passed.append(rec)
                per_brand[host] = per_brand.get(host, 0) + 1
                if verbose:
                    print(f"    found: {(rec.get('title') or c)[:58]}")

    if tried_domains:
        mark_swept(tried_domains)
    return passed


def spread(records, need):
    """Top N, at most one per brand until brands run out."""
    records.sort(key=lambda r: -(r.get("score") or 0))
    out, hosts = [], set()
    for r in records:
        h = r["url"].split("/")[2]
        if h in hosts:
            continue
        out.append(r)
        hosts.add(h)
        if len(out) == need:
            return out
    for r in records:
        if len(out) == need:
            break
        if r not in out:
            out.append(r)
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
        print(f"   niche: {guess_niche(r)}   score {r.get('score') or 0:.2f}")
        print(f"   {why(r)}")
    print()


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
            print("  saved")
        elif "playwright" in out.lower():
            print("  cannot capture: Playwright is not installed.")
            print("    pip install -r requirements.txt")
            print("    python -m playwright install chromium")
        else:
            print(f"  failed: {out.strip()[-140:]}")
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
        pool.sort(key=lambda r: -(r.get("score") or 0))
        seen_hosts = set()
        for r in pool:
            host = r["url"].split("/")[2]
            if host in seen_hosts:
                continue
            picked.append(r)
            seen_hosts.add(host)
            if len(picked) == need:
                break
        if picked:
            note = f"from {len(pool)} already qualified" + (f" in '{label}'" if label else "")

    if len(picked) < need:
        short = need - len(picked)
        print(f"Hunting for {short} more{' in ' + label if label else ''}. "
              f"This takes a minute or two.")
        found = discover(short, pat, bool(label), budget_s=args.budget)
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

    picked = picked[:need]
    present(picked, note)
    if not args.no_save:
        save(picked, args.yes, args.mobile)


if __name__ == "__main__":
    main()
