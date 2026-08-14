---
name: advertorial-finder
description: Find live, currently-running DTC advertorials and listicles worth studying, qualify them by format, and rank them by how long they have survived. Use when the user asks for advertorials to swipe or study, native-ad landing pages, presell pages, listicle funnels, or wants to know what advertorial copy is working right now in a given niche. Also use to expand the brand corpus or to re-check whether previously saved finds are still live.
---

# Advertorial Finder

Find live advertorials worth studying. Six channels, a format filter, and a duration-based ranking.

Read `SOP.md` for the full method before a first run in a session. Everything below is the operating loop.

---

## The one idea to hold

**Presence is not evidence. Duration is.** A live page proves nothing on its own. What survives proves something, because survival is a repeated decision by someone spending money. So rank on measured duration, and treat a stale on-page date as evidence rather than a defect once the page is confirmed live.

**Scoring sorts, it never filters.** A page with no archive history is `duration_unproven` and stays in the list. Longevity says what survived; it does not say what is worth reading.

---

## Pick the channel from what the user asked for

| They want | Run | Needs |
|---|---|---|
| Volume, or a corpus to work from | **D**, sitemap sweep | nothing |
| A specific niche, today | **A/B**, the disclaimer dorks | logged-in browser |
| What is being actively bought, with run duration | **C**, Ad Library | nothing |
| The live chumbox | **F**, local news sites | US IP |

Default to D when the user has no specific niche, because it is unattended and highest volume. Default to A/B when they name a niche.

---

## The loop

**1. Choose a niche.** `py ledger.py niche` returns the least recently worked. Never repeat a niche two sessions running.

**2. Harvest.**

```
py sitemap_sweep.py brands.txt --out runs/candidates.json
```

For channels A and B, run the dorks in the user's own browser. Google bot-checks fresh automated profiles and returns nothing, which looks exactly like a dead query. Do not substitute another engine; Bing strips phrase quotes and DuckDuckGo has no index depth here. Both strings, `&gl=us&hl=en` appended:

```
"not an actual news article" "results may vary" [KEYWORD]
"an advertisement and not a news publication" [STORY PHRASE]
```

Story phrases outperform niche keywords. Witness phrases most of all: `"my husband noticed"`, `"my daughter asked"`, `"people started asking"`. No product page contains narrative, so these cut straight to story-led creative. Full corpus in `SOP.md`.

**3. Qualify and score.**

```
py qualify.py runs/candidates.json
```

**Always read the rejection tally it prints.** If one reason dominates, suspect the filter before the pages. A rejection reading `http_429` means the page was never tested; re-run those with `--delay 5`.

**4. Read down the ranked list**, capture what is worth keeping, and record it.

```
py pdf_save.py "URL" "niche-slug"
py ledger.py add "URL" "niche-slug" --score N
```

Capture is desktop by default. Use `--mobile` when the question is layout or CTA placement, `--both` for a page being torn down properly.

**5. Verify the capture, never the exit code.** The save script can report success while producing a PDF that shows one popup on every page. Extract text from three spread pages and confirm they differ.

---

## Rules that were paid for

**One find is a lead on a set.** A brand runs different landers for different ad types, because the lander is calibrated to what the ad already did. A static ad goes to a long story advertorial; a two-minute video ad goes to a short product-forward page. When something qualifies, check that brand's other pages and its ad library.

**A short advertorial is not a weak one.** Long advertorials feed product pages, short ones feed VSLs. Record the destination type rather than judging length in isolation. Still skip pure VSL bridges; the target is written long-form.

**The disclaimer can never be a hard gate.** It is a legal artifact of the presell and affiliate ecosystem. First-party brand advertorials frequently carry none. Qualify on a threshold of format signals, never on any single one.

**Numbered slugs carry survivorship.** Probe the neighbours of `page-12`: dead siblings around a live number mean it won its split test. High numbers are also where the brand iterated to, so they tend to be the longest and most fully built pages.

**Capture same-day.** Presell domains rotate every few weeks. The PDF becomes the only copy.

---

## What not to do

Do not tear down the copy automatically. The pipeline produces a reading list; reading is the part that needs a copywriter.

Do not redistribute captures. Saved pages are other people's live advertising held for study. `runs/` and `Advertorial-Repo/` are gitignored and stay that way.

Do not present a score as a quality judgement. It measures survival.

---

## Growing it

The sweep is exactly as good as `brands.txt` is long. To add brands:

```
py resolve_domains.py names.txt --out resolved.txt
```

It verifies identity rather than trusting a 200, because an unverified domain quietly pollutes the candidate pool with some unrelated company's sitemap.

Re-check saved finds periodically. A page that died bounds how long that offer ran, which is the number this system otherwise has to guess at.

```
py ledger.py recheck
```
