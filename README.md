# Advertorial Finder

[![smoke](https://github.com/Adishhhhhhh/advertorial-finder/actions/workflows/ci.yml/badge.svg)](https://github.com/Adishhhhhhh/advertorial-finder/actions/workflows/ci.yml)

**There is an ad library for creative. There is nothing equivalent for landing pages.**

You can study a thousand competitor ads in an afternoon. Studying advertorials is harder: the good ones are unlisted `/pages/` slugs reached only through paid traffic, the public swipe files are frozen snapshots of what worked years ago, and the live chumboxes that carry them are geo-locked to a US IP.

This finds live ones, qualifies them, and ranks them by how long they have survived.

---

## What it produces

A ranked reading list of real, currently-live advertorials, each one verified to be story-led long-form rather than a product page or a video bridge, scored by measured duration rather than by how fresh it looks.

A single run against 165 known DTC brands produced **136 qualified advertorials across 24 brands**, including two 8,000-word variants from a brand whose advertorials were already being tracked one page at a time.

---

## The idea it runs on

**Presence is not evidence. Duration is.**

A live page proves nothing, the same way an active ad proves nothing: an ad spending fifty dollars a day at 0.7 ROAS looks identical to one spending five thousand at 3.0. What you can measure from outside is how long something has survived, and survival is a repeated decision by someone with money at stake.

So every find gets a duration measured against the Wayback Machine's archive, which is a third-party record the advertiser cannot edit. A page live and archived continuously for four years has outlasted every split test since. A page with no archive history is marked `duration_unproven` and **stays in the list**, because longevity tells you what survived and not what is worth studying.

Scoring sorts. It never filters.

---

## The six channels

| | Channel | The move | Needs |
|---|---|---|---|
| A | Brand dork | `"not an actual news article" "results may vary" [keyword]` | Real Google in a logged-in browser |
| B | Presell dork | `"an advertisement and not a news publication" [story phrase]` | Real Google in a logged-in browser |
| C | Ad Library | Search ad copy for a story phrase, follow the ad to its lander | Nothing. Free. |
| D | Sitemap sweep | `py sitemap_sweep.py brands.txt` | Nothing. Free. Highest volume. |
| E | Wayback CDX | Duration lookup. Scoring, not discovery. | Nothing. Free. |
| F | Local-news chumbox | Pick any US city, open its news site, scroll to Sponsored Content | **A US IP** |

A and B carry the two disclaimer strings advertisers are legally required to publish, and they route to two different ad ecosystems. C hunts the ad rather than the page, and is the only channel that hands you run duration without inference. D is the volume channel and needs no search engine at all.

Full method, including the query taxonomy and every failure mode paid for in a real session, is in [SOP.md](SOP.md).

---

## Quickstart

> Commands below use `py`, the Windows Python launcher. On macOS and Linux use `python3` instead. Nothing else changes.

```bash
py sitemap_sweep.py brands.txt --out runs/candidates.json
py qualify.py runs/candidates.json
```

That is the whole thing, and it needs no dependencies. Outputs land in `runs/`.

Then read `runs/qualified.jsonl`, top of the list first, and capture what you want to keep:

```bash
py pdf_save.py "URL" "niche-slug"
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
| `selftest.py` | Offline checks on the decision logic. No network, so it gives the same answer on your machine as on mine. Run it if anything behaves oddly. |

---

## Two things this deliberately does not do

**It does not tear down the copy.** The pipeline produces a reading list. Reading is the part that needs a copywriter, and automating it would defeat the purpose of finding these at all.

**It does not redistribute what it finds.** Every saved page is somebody else's live advertising, held for study. The method is shared; the captures stay on your machine. `runs/` and `Advertorial-Repo/` are gitignored for that reason and should stay that way.

---

## Credit

The judging lens comes from two practitioners, both worth reading directly. Alex Cooper's Adcrate newsletter supplied the Facebook Group test, funnel congruence, and the observation that native ads carry paragraphs of story in the primary copy, which is what makes ad copy searchable at all. Stefan Georgi's RMBC II advertorial training supplied the ad-to-lander method, the local-news chumbox method, and the congruence argument for why one product page carries many advertorials.
