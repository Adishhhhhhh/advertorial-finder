# Advertorial Finder

[![smoke](https://github.com/Adishhhhhhh/advertorial-finder/actions/workflows/ci.yml/badge.svg)](https://github.com/Adishhhhhhh/advertorial-finder/actions/workflows/ci.yml)

**There is an ad library for creative. There is nothing equivalent for landing pages.**

You can study a thousand competitor ads in an afternoon. Studying advertorials is harder: the good ones are unlisted `/pages/` slugs reached only through paid traffic, the public swipe files are frozen snapshots of what worked years ago, and the live chumboxes that carry them are geo-locked to a US IP.

This finds live ones, qualifies them, and ranks them by how long they have survived.

---

## What it produces

A ranked reading list of real, currently-live advertorials, each one verified to be story-led long-form rather than a product page or a video bridge, scored by measured duration rather than by how fresh it looks.

A single `find.py` run returns one to three. An optional bulk pass across the 159 shipped brand domains returns a couple of hundred in one go, if you would rather have a library than a reading list.

Either way the unit of value is the same: a page you can open, read, and steal a structure from, with a measured reason it was worth your time.

---

## The idea it runs on

**Presence is not evidence. Duration is.**

A live page proves nothing, the same way an active ad proves nothing: an ad spending fifty dollars a day at 0.7 ROAS looks identical to one spending five thousand at 3.0. What you can measure from outside is how long something has survived, and survival is a repeated decision by someone with money at stake.

So every find gets a duration measured against the Wayback Machine's archive, which is a third-party record the advertiser cannot edit. A page live and archived continuously for four years has outlasted every split test since. A page with no archive history is marked `duration_unproven` and **stays in the list**, because longevity tells you what survived and not what is worth studying.

Scoring sorts. It never filters.

---

## The six channels

**Four of them are unbounded. One is not, and that difference matters more than the volume numbers.**

| | Channel | Bounded by | The move | Needs |
|---|---|---|---|---|
| A | Brand dork | **your keywords only** | `"not an actual news article" "results may vary" [keyword]` | Google, in a browser you're signed into |
| B | Presell dork | **your keywords only** | `"an advertisement and not a news publication" [story phrase]` | Google, in a browser you're signed into |
| C | Ad Library | **your keywords only** | Search ad copy for a story phrase, follow the ad to its lander | Nothing |
| F | Local-news chumbox | **nothing** | Pick any US city, open its news site, scroll to Sponsored Content | A US IP |
| D | Sitemap sweep | a brand list | `py sitemap_sweep.py brands.txt` | Nothing |
| E | Wayback CDX | n/a | Duration lookup. Scoring, not discovery. | Nothing |

A, B, C and F reach **any niche, however obscure**, because they are driven by what you search rather than by who you already know about. That is where versatility comes from, and it is the point: direct response principles are worth studying precisely where they show up in odd, unglamorous categories, not only in the mainstream supplement brands everybody already watches.

D is different. It is bounded by `brands.txt` by construction. It earns its place because it runs unattended and produces hundreds of candidates at once, which makes it the fastest way to build a standing corpus. **It is a volume channel, not the system.** Treating it as the system would silently cap you at whatever list you started with.

### Two corpora, because the interesting advertorials are not on anyone's watchlist

`brands.txt` holds notable DTC brands. It is curated because those brands are worth following, which makes it exactly the wrong place to look for strange advertorials. Nobody curates the company selling a power-grid backup, a kids camera, or a mindfulness box aimed at people going through a divorce, and those are the pages worth reading, because direct response principles are easiest to see when the product is odd and the operator has no brand equity to hide behind.

`wildcards.txt` is that other population: small single-product brands, plus the fake-news aggregator domains that host advertorials for dozens of unrelated advertisers. **Denser in advertorials per domain than the mainstream list, and far stranger.**

`find.py` samples both by default, biased roughly two-to-one toward wildcards, because mainstream brands have longer archives and would otherwise win every ranking on duration alone.

```bash
py find.py --tier wildcard      # only the odd corner
py find.py --tier mainstream    # only the known brands
```

### The brand list is an output, not an input

```bash
py ledger.py harvest
```

Every advertorial found through a keyword-driven channel is a brand the sweep did not know about. `harvest` reads your finds, extracts their domains, and appends the new ones to `brands.txt`. Run it after a session and the bounded channel is permanently less bounded. The list ships with 159 domains so the tool works on day one; it is a floor, never a ceiling.

Full method, including the query taxonomy and every failure mode paid for in a real session, is in [SOP.md](SOP.md).

---

## Quickstart

> Commands below use `py`, the Windows Python launcher. On macOS and Linux use `python3` instead. Nothing else changes.

There is no setup step. Clone it, then:

```bash
py find.py
```

That is the whole tool. It goes out, finds a few live advertorials, checks they are real, ranks them, and shows you why each one ranked. First run takes a couple of minutes; later runs are usually instant, because anything it found and did not show you is kept for next time.

```bash
py find.py -n 1                        # just one
py find.py sleep                       # constrain by niche
py find.py "hair loss women over 50"   # constrain by anything
py find.py --fresh                     # ignore the cache, go hunting
```

It asks before keeping anything. Answering `y` captures each page as a PDF into `Advertorial-Repo/` and records it, so you are never shown the same page twice and nothing is lost when the page rotates off the internet.

```
1. I Was Skeptical Too - Then I Tried the Mat 300,000 People Swear By
   https://www.groundingwell.com/pages/sheet-adv-14
   niche: sleep   score 5.40
   duration unproven · sole survivor of variant 14 · 7,798 words

Save these to Advertorial-Repo/? [y/N]
```

That one is worth reading twice. It is variant fourteen of a family whose lower numbers are all shorter and all dead, which is what iterating toward a winner looks like from outside the ad account.

Finding needs no dependencies at all. Only the PDF capture needs Playwright.

**If you want bulk instead of a few at a time**, the batch path is still there: `sitemap_sweep.py` harvests hundreds of candidates across the whole brand list and `qualify.py` filters and ranks them in one pass. That takes about half an hour unattended and fills the cache, so `find.py` is instant afterwards. Most people should not bother.

To check the install works before trusting any of it:

```bash
py verify.py
```

See [INSTALL.md](INSTALL.md) for what works without which dependency, and for what this cannot do.

---

## The tools

| File | Does |
|---|---|
| `sitemap_sweep.py` | Channel D. Harvests advertorial candidates from known brands' page sitemaps, with variant-family detection. |
| `qualify.py` | Stages 2 and 3. Fetches each candidate, applies the format threshold, then scores by duration. Writes an auditable rejection log. |
| `pdf_save.py` | Captures a live page as a popup-free PDF before it disappears. |
| `resolve_domains.py` | Turns a list of brand names into verified domains for `brands.txt`. |
| `ledger.py` | Session state: niche rotation, dedupe, and re-checking whether saved finds are still alive. |
| `find.py` | **The command.** Finds a few live advertorials on demand, ranks them, offers to keep them. Cache-first, so repeat runs are instant. |
| `study.py` | Same presentation, but reads only from what is already qualified. Pulls the top unread finds, spread across brands, and offers to capture them. |
| `selftest.py` | Offline checks on the decision logic. No network, so it gives the same answer on your machine as on mine. Run it if anything behaves oddly. |

---

## Two things this deliberately does not do

**It does not tear down the copy.** The pipeline produces a reading list. Reading is the part that needs a copywriter, and automating it would defeat the purpose of finding these at all.

**It does not redistribute what it finds.** Every saved page is somebody else's live advertising, held for study. The method is shared; the captures stay on your machine. `runs/` and `Advertorial-Repo/` are gitignored for that reason and should stay that way.

---

## Credit

The judging lens comes from two practitioners, both worth reading directly. Alex Cooper's Adcrate newsletter supplied the Facebook Group test, funnel congruence, and the observation that native ads carry paragraphs of story in the primary copy, which is what makes ad copy searchable at all. Stefan Georgi's RMBC II advertorial training supplied the ad-to-lander method, the local-news chumbox method, and the congruence argument for why one product page carries many advertorials.
