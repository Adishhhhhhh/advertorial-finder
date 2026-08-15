# Advertorial Swiper

Finds live DTC advertorials worth studying, ranks them by how long they have survived, and keeps the ones you want.

## If you were asked to find advertorials, run this

```
python find.py -n 3
```

That is the entire tool. Nothing to install, nothing to configure, no API key, no account. It uses the Python standard library only.

Add a niche or any phrase to constrain it:

```
python find.py -n 3 sleep
python find.py -n 5 "hair loss women over 50"
python find.py -n 1 --tier wildcard
```

**Do not run `verify.py` first unless the user asks.** It is an install check that makes live network calls and takes about 90 seconds. `find.py` works without it.

**Do not run `sitemap_sweep.py` or `qualify.py` directly** unless the user wants a bulk corpus. `find.py` calls what it needs. The bulk path takes half an hour.

On Windows use `py` instead of `python` if `python` is not found.

## What it prints

Each result carries the reason it ranked, which is the part worth relaying to the user:

```
1. I Was Skeptical Too - Then I Tried the Mat 300,000 People Swear By
   https://www.groundingwell.com/pages/sheet-adv-14
   niche: sleep   score 5.40  [wildcard]
   duration unproven · sole survivor of variant 14 · 7,798 words
```

`sole survivor of variant 14` means every other numbered version of that page is dead and this one is live. It won its own split test.

`live 45.3 months` is measured against the Wayback Machine, not guessed.

## Saving

It asks before keeping anything. Answering yes writes into `Advertorial-Repo/`. If Playwright is installed it saves a PDF; if not it saves the copy as text plus the raw HTML, so **saving always works**.

Pass `--yes` to skip the prompt in a scripted run, `--no-save` to browse only.

## Timing

First run takes one to three minutes because it goes out and hunts. Later runs are usually instant, because anything found and not shown is cached.

## The rest

`SOP.md` is the full method, including the query corpus and the manual channels that reach niches no brand list covers. `README.md` is the overview. `INSTALL.md` states what this cannot do.

## Never

Do not commit anything from `Advertorial-Repo/` or `runs/`. Those are other people's live advertising, held for study. The method is shared; the captures are not.
