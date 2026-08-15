"""
study.py  -  Give me advertorials to study today.

The one command most sessions need. It picks a fresh niche, pulls the highest
ranked finds you have not already saved, shows you what they are and why they
ranked, then asks whether to keep them. Answering yes captures each page as a
PDF into Advertorial-Repo/ and records it, so nothing is lost when the page
rotates off the internet, which presell pages do within weeks.

    python study.py                 3 finds, asks before saving
    python study.py -n 1            just one
    python study.py --niche sleep   from a niche you choose
    python study.py --yes           save without asking (for scripted runs)
    python study.py --no-save       just show them, never save

If runs/qualified.jsonl is empty it tells you which command fills it, rather
than failing with an empty list.
"""

import os, re, sys, json, argparse, subprocess
from datetime import datetime, timezone

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
RUNS = os.path.join(HERE, "runs")
QUALIFIED = os.path.join(RUNS, "qualified.jsonl")
REPO = os.path.join(HERE, "Advertorial-Repo")
PY = sys.executable

NICHE_HINTS = {
    "sleep": r"sleep|insomnia|rest|night|mattress|bedsheet|grounding",
    "gut": r"gut|bloat|digest|probiotic|microbiome|leaky",
    "joint": r"joint|knee|back|arthritis|mobility|posture",
    "hair": r"hair|bald|thinning|scalp|regrow",
    "skin": r"skin|wrinkle|collagen|aging|serum|acne",
    "weight": r"weight|fat|slim|metabolism|glp|appetite",
    "energy": r"energy|fatigue|tired|focus|brain|nootropic|mushroom",
    "hearing": r"hearing|tinnitus|ear|ringing",
    "menopause": r"menopause|hormone|hot flash|perimenopause",
    "oral": r"dental|teeth|gum|breath|whiten",
    "pet": r"pet|dog|cat|paw|vet",
    "mens": r"prostate|testoster|men|beard",
    "beauty": r"beauty|makeup|lip|balm|lash|brow",
}


def load_finds():
    rows = {}
    try:
        for line in open(QUALIFIED, encoding="utf-8"):
            line = line.strip()
            if line:
                r = json.loads(line)
                rows[r["url"]] = r
    except FileNotFoundError:
        return []
    return list(rows.values())


def already_saved():
    saved = set()
    try:
        for line in open(os.path.join(RUNS, "finds.jsonl"), encoding="utf-8"):
            line = line.strip()
            if line:
                saved.add(json.loads(line)["url"].rstrip("/"))
    except FileNotFoundError:
        pass
    return saved


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


def ask(prompt):
    try:
        return input(prompt).strip().lower()
    except (EOFError, KeyboardInterrupt):
        print()
        return "n"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("-n", "--count", type=int, default=3)
    ap.add_argument("--niche")
    ap.add_argument("--yes", action="store_true", help="save without asking")
    ap.add_argument("--no-save", action="store_true", help="show only")
    ap.add_argument("--mobile", action="store_true", help="capture mobile layout too")
    args = ap.parse_args()

    finds = load_finds()
    if not finds:
        print("Nothing qualified yet. Fill the list first:\n")
        print("    python sitemap_sweep.py brands.txt --out runs/candidates.json")
        print("    python qualify.py runs/candidates.json\n")
        print("Or work a specific niche with the dorks in SOP.md, which reach")
        print("any category rather than only the brands in brands.txt.")
        sys.exit(1)

    saved = already_saved()
    pool = [f for f in finds if f["url"].rstrip("/") not in saved]

    if args.niche:
        pat = NICHE_HINTS.get(args.niche.lower(), re.escape(args.niche))
        pool = [f for f in pool
                if re.search(pat, (f["url"] + " " + (f.get("title") or "")).lower())]
        if not pool:
            print(f"Nothing left in '{args.niche}'. Try another, or widen the corpus:")
            print("    python study.py            (any niche)")
            sys.exit(1)

    pool.sort(key=lambda r: -(r.get("score") or 0))

    # Spread across brands so three finds are not three pages from one company.
    picked, seen_hosts = [], set()
    for r in pool:
        host = r["url"].split("/")[2]
        if host in seen_hosts:
            continue
        picked.append(r)
        seen_hosts.add(host)
        if len(picked) == args.count:
            break
    for r in pool:
        if len(picked) == args.count:
            break
        if r not in picked:
            picked.append(r)

    print()
    print("=" * 70)
    print(f"{len(picked)} ADVERTORIAL{'S' if len(picked) != 1 else ''} TO STUDY")
    print(f"{len(pool)} unread in the list, {len(saved)} already saved")
    print("=" * 70)
    for i, r in enumerate(picked, 1):
        print()
        print(f"{i}. {(r.get('title') or 'untitled').strip()[:66]}")
        print(f"   {r['url']}")
        print(f"   niche: {guess_niche(r)}   score {r.get('score', 0):.2f}")
        print(f"   {why(r)}")
    print()

    if args.no_save:
        return

    if args.yes:
        answer = "y"
    else:
        answer = ask(f"Save {'these' if len(picked) > 1 else 'this'} to Advertorial-Repo/? [y/N] ")

    if answer not in ("y", "yes"):
        print("Not saved. They stay in the list for next time.")
        return

    os.makedirs(REPO, exist_ok=True)
    ok = 0
    for r in picked:
        niche = guess_niche(r)
        print(f"\ncapturing {r['url']}")
        cmd = [PY, os.path.join(HERE, "pdf_save.py"), r["url"], niche]
        if args.mobile:
            cmd.append("--both")
        p = subprocess.run(cmd, cwd=HERE, capture_output=True, text=True,
                           encoding="utf-8", errors="replace")
        out = (p.stdout or "") + (p.stderr or "")
        if "SUCCESS" in out:
            ok += 1
            print("  saved")
            subprocess.run([PY, os.path.join(HERE, "ledger.py"), "add", r["url"],
                            niche, "--score", str(r.get("score") or 0)],
                           cwd=HERE, capture_output=True)
        elif "playwright" in out.lower():
            print("  cannot capture: Playwright is not installed.")
            print("    pip install -r requirements.txt")
            print("    python -m playwright install chromium")
            print("  Recording the find anyway so it is not offered again.")
            subprocess.run([PY, os.path.join(HERE, "ledger.py"), "add", r["url"],
                            niche, "--score", str(r.get("score") or 0)],
                           cwd=HERE, capture_output=True)
            break
        else:
            print(f"  failed: {out.strip()[-140:]}")

    print(f"\n{ok} saved to Advertorial-Repo/")
    if ok:
        print("Verify a capture before trusting it: open the PDF and confirm the")
        print("pages differ rather than showing one repeated popup.")


if __name__ == "__main__":
    main()
