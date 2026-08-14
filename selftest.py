"""
selftest.py  -  Offline checks on the logic that decides things.

No network. Everything here runs against fixtures, so it gives the same answer
on a stranger's laptop as on the machine that wrote it. That is the point: the
bugs this catches are the ones that only appear on somebody else's install
(import errors, syntax too new for their Python, argparse typos, a regex that
silently matches nothing).

    py selftest.py

Exits non-zero on the first failure so CI catches it.
"""

import sys, importlib

FAILURES = []


def check(name, got, want):
    if got == want:
        print(f"  ok   {name}")
    else:
        print(f"  FAIL {name}\n         got:  {got!r}\n         want: {want!r}")
        FAILURES.append(name)


def section(title):
    print(f"\n{title}")


# --------------------------------------------------------------- imports

section("imports (catches syntax too new, missing stdlib, typos)")
for mod in ["sitemap_sweep", "qualify", "ledger", "resolve_domains"]:
    try:
        importlib.import_module(mod)
        print(f"  ok   import {mod}")
    except Exception as e:
        print(f"  FAIL import {mod}: {type(e).__name__}: {e}")
        FAILURES.append(f"import {mod}")

# pdf_save imports playwright, which is optional. It must fail with a readable
# message rather than a traceback, so we only check it parses.
try:
    import ast
    ast.parse(open("pdf_save.py", encoding="utf-8").read())
    print("  ok   parse pdf_save.py")
except SyntaxError as e:
    print(f"  FAIL parse pdf_save.py: {e}")
    FAILURES.append("parse pdf_save")

if FAILURES:
    print("\nimports failed; stopping here")
    sys.exit(1)

import sitemap_sweep as sw
import qualify as q
import resolve_domains as rd

# --------------------------------------------------------------- sweep logic

section("sitemap_sweep: slug matching")
check("advertorial slug matches",
      bool(sw.SLUG.search("/pages/herby-lung-cleanse-advertorial")), True)
check("listicle slug matches",
      bool(sw.SLUG.search("/pages/5-reasons-why-women")), True)
check("numbered adv slug matches",
      bool(sw.SLUG.search("/pages/sheet-adv-14")), True)
check("plain product slug does not match",
      bool(sw.SLUG.search("/pages/shipping-policy")), False)
check("our-story is filtered as noise",
      bool(sw.NOISE.search("/pages/our-story")), True)
check("privacy policy is filtered as noise",
      bool(sw.NOISE.search("/pages/privacy-policy-v2")), True)
check("tracking page is filtered as noise",
      bool(sw.NOISE.search("/pages/tracking-v2")), True)
check("real advertorial is not filtered as noise",
      bool(sw.NOISE.search("/pages/5-reasons-why-women-need-meno-gut")), False)

section("sitemap_sweep: locale deduplication")
check("locale prefix stripped",
      sw.canonical("https://spacegoods.com/de-de/pages/rainbow-dust-review-2026"),
      "https://spacegoods.com/pages/rainbow-dust-review-2026")
check("short locale stripped",
      sw.canonical("https://spacegoods.com/nl/pages/x"),
      "https://spacegoods.com/pages/x")
check("non-locale path untouched",
      sw.canonical("https://x.com/pages/sheet-adv-14"),
      "https://x.com/pages/sheet-adv-14")

section("sitemap_sweep: domain candidates")
check("bare domain passes through",
      sw.candidate_domains("groundingwell.com"), ["groundingwell.com"])
check("brand name expands",
      sw.candidate_domains("Grounding Well")[:2],
      ["groundingwell.com", "thegroundingwell.com"])

section("sitemap_sweep: variant families")
fam = sw.variant_families([
    "https://x.com/pages/sheet-adv-4",
    "https://x.com/pages/sheet-adv-5",
    "https://x.com/pages/sheet-adv-14",
    "https://x.com/pages/lonely-page",
])
check("family detected", sorted(fam.get("sheet-adv", [])),
      ["sheet-adv-14", "sheet-adv-4", "sheet-adv-5"])
check("singleton is not a family", "lonely-page" in fam, False)

# --------------------------------------------------------------- qualify logic

section("qualify: format signals")
ADVERTORIAL = """
<html><head><title>How I Fixed It &ndash; Brand</title></head><body>
<p>By Maria Noman | March 4, 2026</p>
<p>I was skeptical at first. My husband noticed before I did.
"I could not believe it," she said. Here is what happened next.</p>
<p>5 reasons why most people never fix this. The real reason has
nothing to do with what your doctor told you.</p>
<a href="#">Check Availability</a>
<small>THIS IS AN ADVERTISEMENT AND NOT AN ACTUAL NEWS ARTICLE.</small>
</body></html>
"""
text = q.visible_text(ADVERTORIAL)
check("disclaimer detected", bool(q.DISCLAIMER.search(text)), True)
check("byline detected", bool(q.BYLINE.search(text[:3000])), True)
check("soft CTA detected", bool(q.SOFT_CTA.search(text)), True)
check("editorial framing detected", bool(q.EDITORIAL.search(text)), True)
check("quoted speech detected", bool(q.QUOTED.search(text)), True)
check("title extracted", q.page_title(ADVERTORIAL), "How I Fixed It &ndash; Brand")

section("qualify: VSL detection")
check("video-summary title flagged",
      bool(q.VSL_TITLE.search("Lung Health Report - Video Summary")), True)
check("watch CTA flagged",
      bool(q.VSL_BODY.search("WATCH THE FULL PRESENTATION now")), True)
check("ordinary advertorial not flagged",
      bool(q.VSL_TITLE.search("How I Fixed It")), False)

section("qualify: variant parsing")
m = q.VARIANT.match("boldhealth020")
check("variant stem", m.group(1) if m else None, "boldhealth")
check("variant number", m.group(2) if m else None, "020")
check("non-numbered slug is not a variant",
      q.VARIANT.match("miracle-joint-drops"), None)

section("qualify: utility pages are excluded on identity")
check("privacy policy rejected",
      bool(q.UTILITY.search("https://x.com/pages/privacy-policy-v2")), True)
check("tracking page rejected",
      bool(q.UTILITY.search("https://x.com/pages/tracking-v2")), True)
check("advertorial not rejected",
      bool(q.UTILITY.search("https://x.com/pages/5-reasons-why")), False)
check("locale duplicates collapse to one",
      q.canonical("https://s.com/en-nl/pages/x"), "https://s.com/pages/x")

section("qualify: threshold is 3 of 5, and never all-or-nothing")
check("threshold value", q.SIGNAL_THRESHOLD, 3)
check("threshold is below the signal count", q.SIGNAL_THRESHOLD < 5, True)

# --------------------------------------------------------------- resolver

section("resolve_domains: name handling")
check("tokens drop corporate suffixes", rd.tokens("PetLab Co."), ["petlab"])
check("slug strips punctuation", rd.slug("MUD\\WTR"), "mudwtr")
check("ampersand variant produced",
      "40plusandfabulous" in rd.variants("40 Plus & Fabulous"), True)
check("identity rejects a mismatched site",
      rd.identity_ok("Serene Herbs", "<title>Acme Plumbing</title>", "https://acme.com"),
      False)
check("identity accepts a matching site",
      rd.identity_ok("Serene Herbs", "<title>Serene Herbs</title>", "https://sereneherbs.com"),
      True)

# --------------------------------------------------------------- verdict

print()
if FAILURES:
    print(f"{len(FAILURES)} FAILED: {', '.join(FAILURES)}")
    sys.exit(1)
print("all checks passed")
