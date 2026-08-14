# Advertorial Finder

Find live DTC advertorials worth studying, qualify them by format, rank them by how long they have survived.

**Start here:** `SKILL.md` is the operating loop. `SOP.md` is the full method, including the query corpus and every failure mode. `INSTALL.md` states what works without which dependency and what this cannot do.

## Working directory

This directory. All scripts resolve paths relative to themselves, so run them from here and outputs land in `runs/`.

## The tools

```
py sitemap_sweep.py brands.txt --out runs/candidates.json   # harvest
py qualify.py runs/candidates.json                          # filter + rank
py pdf_save.py "URL" "niche-slug"                           # capture
py ledger.py niche | add | recheck | status                 # session state
py resolve_domains.py names.txt --out resolved.txt          # grow the corpus
```

## Three things to hold

**Presence is not evidence, duration is.** Rank on measured archive span, not on how fresh a page looks.

**Scoring sorts, it never filters.** `duration_unproven` stays in the list.

**Read the rejection tally, every run.** If one reason dominates, suspect the filter before the pages. A rejection reading `http_429` means the page was never tested.

## Never

Do not redistribute captures. Saved pages are other people's live advertising held for study. `runs/` and `Advertorial-Repo/` are gitignored and stay that way.
