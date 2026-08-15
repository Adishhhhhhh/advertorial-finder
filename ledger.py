"""
ledger.py  -  Session state for the advertorial swiper.

State lives in files, never in an agent's memory, because memory does not survive
an install on somebody else's machine and the whole point of a ledger is that it
accumulates. Three of them, written at three different moments:

    runs/finds.jsonl     every page you saved, with niche, score, and date
    runs/niches.json     when each niche was last worked, so rotation is computed
    runs/recheck.jsonl   dated re-probes of saved finds, alive or dead

The third one is the only outcome data this system can ever produce about itself.
A page that dies eight months after you saved it tells you something a page that
stays live does not, and neither fact is available any other way.

Usage:
    py ledger.py status
    py ledger.py niche                      suggest the next niche to work
    py ledger.py add <url> <niche> [--score N] [--pdf FILE]
    py ledger.py recheck [--older-than 30]  re-probe saved finds
"""

import os, re, sys, json, argparse, urllib.request, urllib.error
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
RUNS = os.path.join(HERE, "runs")
FINDS = os.path.join(RUNS, "finds.jsonl")
NICHES = os.path.join(RUNS, "niches.json")
RECHECK = os.path.join(RUNS, "recheck.jsonl")

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36")

# Rotation pool. Extend freely; anything never worked sorts to the front.
NICHE_POOL = [
    "sleep", "joint-mobility", "gut-bloating", "hair-loss", "skin-aging",
    "menopause", "mens-prostate", "tinnitus-hearing", "weight-loss",
    "foot-ankle", "pet-joint", "pet-dental", "vision", "energy-fatigue",
    "memory-focus", "oral-dental", "circulation-legs", "blood-sugar",
    "anxiety-stress", "lung-respiratory", "posture-neck", "earthing-grounding",
    "parasite-gut", "immune", "thyroid", "liver-detox", "household-cleaning",
    "kitchen-gadget", "home-security", "financial", "hearing-aid",
]


def now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def today():
    return datetime.now(timezone.utc).date().isoformat()


def ensure():
    os.makedirs(RUNS, exist_ok=True)


def read_jsonl(path):
    out = []
    try:
        for line in open(path, encoding="utf-8"):
            line = line.strip()
            if line:
                try:
                    out.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    except FileNotFoundError:
        pass
    return out


def append_jsonl(path, row):
    ensure()
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")


def load_niches():
    try:
        return json.load(open(NICHES, encoding="utf-8"))
    except Exception:
        return {}


def save_niches(d):
    ensure()
    json.dump(d, open(NICHES, "w", encoding="utf-8"), indent=1, sort_keys=True)


# ------------------------------------------------------------------ commands

def cmd_status(_):
    finds = read_jsonl(FINDS)
    rech = read_jsonl(RECHECK)
    worked = load_niches()

    print(f"saved finds     : {len(finds)}")
    print(f"niches worked   : {len(worked)} of {len(NICHE_POOL)} in the pool")
    print(f"recheck records : {len(rech)}")

    if finds:
        scored = [f for f in finds if f.get("score") is not None]
        if scored:
            top = sorted(scored, key=lambda f: -f["score"])[:5]
            print("\nhighest scored:")
            for f in top:
                print(f"  {f['score']:>6}  {f.get('niche','?'):<20} {f['url']}")

    dead = [r for r in rech if not r.get("alive")]
    if dead:
        print(f"\ndied since capture: {len(dead)}")
        for r in dead[-5:]:
            print(f"  {r['checked']}  {r['url']}")
        print("\nA page that died is a data point, not a loss. It bounds how long")
        print("that offer ran, which is the number this system otherwise guesses at.")


def cmd_niche(_):
    worked = load_niches()
    never = [n for n in NICHE_POOL if n not in worked]
    if never:
        print("never worked, pick any:")
        for n in never[:10]:
            print("   ", n)
        return
    order = sorted(NICHE_POOL, key=lambda n: worked.get(n, ""))
    print("least recently worked:")
    for n in order[:8]:
        print(f"    {worked.get(n, 'never'):<12} {n}")


def cmd_add(args):
    row = {
        "url": args.url.rstrip("/"),
        "niche": args.niche,
        "score": args.score,
        "pdf": args.pdf,
        "saved": now(),
    }
    existing = {f["url"] for f in read_jsonl(FINDS)}
    if row["url"] in existing:
        print("already in the ledger, nothing written")
        return
    append_jsonl(FINDS, row)
    worked = load_niches()
    worked[args.niche] = today()
    save_niches(worked)
    print(f"recorded: {row['url']}")
    print(f"niche '{args.niche}' marked worked {today()}")


def probe(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA}, method="HEAD")
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            return r.status == 200, r.status
    except urllib.error.HTTPError as e:
        return False, e.code
    except Exception as e:
        return False, type(e).__name__


def cmd_recheck(args):
    finds = read_jsonl(FINDS)
    if not finds:
        print("no saved finds to recheck")
        return

    seen = {}
    for r in read_jsonl(RECHECK):
        seen[r["url"]] = r["checked"]

    cutoff = args.older_than
    due = []
    for f in finds:
        last = seen.get(f["url"])
        if not last:
            due.append(f)
        else:
            age = (datetime.now(timezone.utc).date()
                   - datetime.fromisoformat(last).date()).days
            if age >= cutoff:
                due.append(f)

    print(f"due for recheck: {len(due)} of {len(finds)}")
    if not due:
        return

    alive = dead = 0
    with ThreadPoolExecutor(max_workers=6) as ex:
        for f, (ok, code) in zip(due, ex.map(lambda x: probe(x["url"]), due)):
            append_jsonl(RECHECK, {"url": f["url"], "niche": f.get("niche"),
                                   "alive": ok, "code": code, "checked": today()})
            if ok:
                alive += 1
            else:
                dead += 1
                print(f"  DEAD {code}  {f['url']}")

    print(f"\nalive {alive}   dead {dead}")
    if dead:
        print("Dead pages bound the run length of an offer. Keep the PDF; it is")
        print("now the only copy, and the capture date is the lower bound.")


def cmd_harvest(args):
    """Feed domains from finds back into brands.txt.

    The sitemap sweep is the only channel bounded by a list, and left alone
    that bound never moves. The dorks and the ad library are bounded by
    nothing but your keywords, so every advertorial they turn up is a brand
    the sweep did not know about. Running this after a session makes the
    bounded channel less bounded, permanently.
    """
    sources = []
    for path in (os.path.join(RUNS, "qualified.jsonl"), FINDS):
        sources += read_jsonl(path)
    if not sources:
        print("nothing to harvest yet. Qualify or save some finds first.")
        return

    found = set()
    for r in sources:
        m = re.match(r"^https?://([^/]+)", r.get("url", ""))
        if m:
            found.add(m.group(1).lower().replace("www.", ""))

    # New domains go to wildcards: anything discovered through a keyword
    # channel is by definition not on a curated watchlist.
    brands_path = os.path.join(HERE, "wildcards.txt")
    existing, lines = set(), []
    try:
        lines = open(brands_path, encoding="utf-8").read().splitlines()
        for l in lines:
            l = l.strip()
            if l and not l.startswith("#"):
                existing.add(l.split("#")[0].strip().lower())
    except FileNotFoundError:
        pass

    new = sorted(d for d in found if d not in existing)
    print(f"domains in finds : {len(found)}")
    print(f"already listed   : {len(found) - len(new)}")
    print(f"new              : {len(new)}")
    if not new:
        return
    for d in new:
        print("   ", d)

    if args.dry_run:
        print("\ndry run, nothing written. Drop --dry-run to append.")
        return

    with open(brands_path, "a", encoding="utf-8") as f:
        f.write(f"\n# harvested from finds, {today()}\n")
        for d in new:
            f.write(d + "\n")
    print(f"\nappended {len(new)} domains to brands.txt")
    print("Next sweep will cover them.")


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)

    sub.add_parser("status").set_defaults(fn=cmd_status)
    sub.add_parser("niche").set_defaults(fn=cmd_niche)

    h = sub.add_parser("harvest", help="feed find domains back into brands.txt")
    h.add_argument("--dry-run", action="store_true")
    h.set_defaults(fn=cmd_harvest)

    a = sub.add_parser("add")
    a.add_argument("url")
    a.add_argument("niche")
    a.add_argument("--score", type=float)
    a.add_argument("--pdf")
    a.set_defaults(fn=cmd_add)

    r = sub.add_parser("recheck")
    r.add_argument("--older-than", type=int, default=30,
                   help="recheck finds not probed in this many days")
    r.set_defaults(fn=cmd_recheck)

    args = ap.parse_args()
    args.fn(args)


if __name__ == "__main__":
    main()
