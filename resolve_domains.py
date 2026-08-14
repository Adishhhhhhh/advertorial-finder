"""
resolve_domains.py  -  Turn brand names into verified domains for brands.txt.

Naive guessing (brand.com) resolves under half of a real brand list. This tries a
wider pattern set and then VERIFIES each hit rather than trusting the 200, by
checking the brand's own tokens appear in the page title or og:site_name. An
unverified domain is worse than a missing one, because the sweep would then
harvest some unrelated company's sitemap and quietly pollute the candidate pool.

Usage:
    py resolve_domains.py names.txt --out resolved.txt
    py resolve_domains.py names.txt --out resolved.txt --workers 12
"""

import re, sys, json, argparse, urllib.request, urllib.error
from concurrent.futures import ThreadPoolExecutor

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36")

# Ordered by how often each shape wins on a DTC brand list.
PATTERNS = [
    "{b}.com", "the{b}.com", "get{b}.com", "{b}.co", "try{b}.com",
    "shop{b}.com", "{b}health.com", "drink{b}.com", "{b}.store",
    "{b}official.com", "my{b}.com", "{b}.shop", "buy{b}.com", "{b}.life",
]

STOPWORDS = {"co", "inc", "llc", "ltd", "the", "company", "brand", "official"}


def slug(name):
    return re.sub(r"[^a-z0-9]", "", name.lower())


def tokens(name):
    parts = re.split(r"[^a-z0-9]+", name.lower())
    return [p for p in parts if p and p not in STOPWORDS and len(p) > 2]


def variants(name):
    """Several slug spellings, because '40 Plus & Fabulous' has more than one."""
    out = []
    base = slug(name)
    if base:
        out.append(base)
    amp = slug(name.replace("&", "and"))
    if amp and amp not in out:
        out.append(amp)
    # drop a trailing corporate suffix: "PetLab Co." -> "petlab"
    trimmed = slug(re.sub(r"\b(co|inc|llc|ltd)\.?\s*$", "", name, flags=re.I))
    if trimmed and trimmed not in out:
        out.append(trimmed)
    # first two words only, for long descriptive names
    parts = tokens(name)
    if len(parts) > 2:
        two = "".join(parts[:2])
        if two not in out:
            out.append(two)
    return out


def fetch_head(url, timeout=12):
    req = urllib.request.Request(url, headers={"User-Agent": UA,
                                               "Accept-Language": "en-US,en;q=0.9"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        raw = r.read(180_000).decode("utf-8", "replace")
        return r.geturl(), raw


def identity_ok(name, html, final_url):
    """Verify the site belongs to this brand rather than merely answering."""
    title = ""
    m = re.search(r"<title[^>]*>(.*?)</title>", html, re.I | re.S)
    if m:
        title = m.group(1)
    site = ""
    m = re.search(r'property=["\']og:site_name["\'][^>]*content=["\']([^"\']+)', html, re.I)
    if m:
        site = m.group(1)
    hay = slug(title + " " + site + " " + final_url)

    tks = tokens(name)
    if not tks:
        return False
    # every meaningful token of the brand name must appear somewhere identifying
    hits = sum(1 for t in tks if t in hay)
    return hits == len(tks) or (len(tks) > 2 and hits >= len(tks) - 1)


def has_pages_sitemap(domain):
    for path in ("/sitemap_pages_1.xml", "/sitemap.xml"):
        try:
            _, body = fetch_head(f"https://{domain}{path}")
            if "<loc>" in body:
                return True
        except Exception:
            continue
    return False


def resolve(name):
    tried = []
    for v in variants(name):
        for pat in PATTERNS:
            d = pat.format(b=v)
            if d in tried:
                continue
            tried.append(d)
            try:
                final, html = fetch_head(f"https://{d}")
            except Exception:
                continue
            if not identity_ok(name, html, final):
                continue
            host = re.sub(r"^https?://", "", final).split("/")[0]
            return {"name": name, "domain": host, "verified": True,
                    "sitemap": has_pages_sitemap(host)}
    return {"name": name, "domain": None, "verified": False, "sitemap": False}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("names")
    ap.add_argument("--out", default="resolved.txt")
    ap.add_argument("--workers", type=int, default=10)
    args = ap.parse_args()

    names = [l.strip().lstrip("# ").strip() for l in open(args.names, encoding="utf-8")
             if l.strip() and not l.strip().startswith("##")]
    names = [n for n in names if n]
    print(f"[resolve] names in: {len(names)}")

    results = []
    with ThreadPoolExecutor(max_workers=args.workers) as ex:
        for i, r in enumerate(ex.map(resolve, names), 1):
            results.append(r)
            if i % 10 == 0:
                ok = sum(1 for x in results if x["domain"])
                print(f"  ... {i}/{len(names)}  resolved {ok}")

    got = [r for r in results if r["domain"]]
    withmap = [r for r in got if r["sitemap"]]
    print(f"\n[resolve] resolved      : {len(got)}/{len(names)}")
    print(f"[resolve] with sitemap  : {len(withmap)}")

    with open(args.out, "w", encoding="utf-8") as f:
        for r in got:
            flag = "" if r["sitemap"] else "  # no page sitemap"
            f.write(f"{r['domain']}{flag}\n")
    json.dump(results, open(args.out + ".json", "w", encoding="utf-8"), indent=1)

    print(f"[resolve] wrote {args.out}")
    print("\nunresolved:")
    for r in results:
        if not r["domain"]:
            print("   ", r["name"])


if __name__ == "__main__":
    main()
