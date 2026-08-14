# The method

Everything the finder knows. Read once; the operating loop is in `SKILL.md`.

---

## What counts as a find

A page that reads like a news article, a health blog, or a personal story, and sells a DTC product.

Byline and date. A lead that is a personal story, a shocking statistic, or a suppressed discovery. An invented mechanism with a scientific-sounding name. An authority persona. One physical analogy. A soft CTA (*Learn More*, *Check Availability*, *Claim Discount*) rather than *Add to Cart*. A money-back guarantee. Fine print somewhere near the bottom.

**Siblings worth saving:** listicles ("7 Reasons Why..."), fake-masthead presell pages, and interstitial pages that sit between an ad and a product page.

**Not a find:** a VSL bridge. If the page is a short wrapper around a video player with a *Watch The Presentation* CTA, skip it. The target is written long-form.

---

## The judging lens

Three tests, from Alex Cooper's Adcrate newsletter and Stefan Georgi's RMBC II training.

**The Facebook Group test.** Would it look out of place posted in a Facebook Group? Winning natives look ugly: grainy photos, basic fonts, made by someone's dad rather than by a creative agency. Polish is a losing tell.

**Funnel congruence.** A converting native never sends traffic straight to a product page. The chain runs ad → advertorial or listicle or quiz, and the editorial illusion holds the whole way. A page that shouts BUY NOW breaks the trust the creative just built.

**Story-led before product.** The copy educates and agitates the problem long before the product appears.

Hottest niches: health and wellness, supplements and beauty, financial, anything aimed at 45+, and embarrassing problems.

---

## Presence is not evidence

A live page proves nothing on its own, for the same reason an active ad proves nothing: an ad spending fifty dollars a day at 0.7 ROAS looks identical to one spending five thousand at 3.0. Spend data is not available to outsiders and never will be.

**Duration is what you can measure.** A page live and continuously archived for four years has outlasted every split test since. That is a repeated decision by somebody with money at stake, and the Wayback Machine is a third-party custodian the advertiser cannot edit.

Two consequences that reverse ordinary instinct:

- A five-year-old page with a stale on-page date **outranks** a fresh one, once both are confirmed live.
- A find with no archive history is not disqualified. It is marked `duration_unproven` and stays in the list.

**Scoring sorts. It never filters.** Longevity tells you what survived, not what is worth studying, and a new advertorial from a sharp operator can teach more than a five-year control.

---

## The six channels

### A — the brand dork

```
"not an actual news article" "results may vary" [KEYWORD]
```

Finds brand and Shopify advertorials on `/pages/` slugs. Append `&gl=us&hl=en` for US results.

### B — the presell dork

```
"an advertisement and not a news publication" [KEYWORD or STORY PHRASE]
```

A different disclaimer string, which routes to a different ad ecosystem: the presell networks running in US Taboola and Outbrain chumboxes. Google's index is not geo-locked, so this reaches US inventory from anywhere.

**Both A and B need a browser you are signed into.** Google bot-checks fresh automated profiles and returns nothing, which looks exactly like a dead query. Do not substitute another engine: Bing silently strips the phrase quotes and returns dictionary definitions; DuckDuckGo honours the quotes and returns zero because its index does not reach these pages. The fix is a different browser, never a different engine.

**Bonus dorks to rotate:**
```
inurl:advertorial [KEYWORD]
inurl:/pages/ "not an actual news article" [KEYWORD]
inurl:presell "not an actual news article"
"health & wellness journal" [KEYWORD]        ← fake-masthead search
```

### C — Ad Library

The dorks hunt the landing page. This hunts the ad.

Search ad copy for a story phrase, country US, active only. Every result card carries a start date and an active flag, which makes this the only channel that hands you run duration without inference. Sort by impressions in the URL. Then follow the ad's link to its lander.

This is Georgi's method, done by hand.

### D — the sitemap sweep

Most DTC brands run Shopify, which publishes every `/pages/` URL at `/sitemap_pages_1.xml`. Brands do not delete losing advertorial variants; they stop sending traffic to them. **The sitemap is therefore a public archive of every advertorial a brand has ever tested, with the numbered variant families intact.**

```
py sitemap_sweep.py brands.txt --out runs/candidates.json
```

Highest volume of any channel, needs no search engine, and is not geo-locked.

### E — Wayback CDX

Not discovery. This is the scoring input.

```
http://web.archive.org/cdx/search/cdx?url=DOMAIN/PATH&output=json&fl=timestamp,statuscode
```

Returns every capture with a date and status. First-to-last span is the duration. `qualify.py` does this automatically.

### F — the local-news chumbox

**US IP only.** The move is not a fixed site list: pick any US city, search for its local news site, click any article, scroll to *Sponsored Content*. Georgi picks Tampa at random off a map and works Tampa Bay Times, Fox 13, and ABC Action News alongside weather.com, Forbes, and Fortune.

Two things make it worth a VPN:

- **Publisher tier predicts how aggressive the advertorial is.** Local news and mainstream run more white hat. The weather.com tier runs the black hat, up to deepfaked doctors. The publisher is a targeting lever.
- **A few networks serve nearly all the inventory**, so the same ads repeat across sites. That is exactly why channels A and B reach the same pages from outside the US. One pool, many publishers.

From a non-US IP, native widgets fill with locally targeted ads and no amount of trying other publishers fixes it, because every site pulls the same geo-keyed fill.

---

## Query types: seven, and they reach different populations

The query decides who you find, not just what.

| Type | Example | Reaches |
|---|---|---|
| **Witness phrase** | `"my husband noticed"` | Story-led creative, any niche. Highest yield. |
| Category | `gut health supplements` | Who is in a market |
| Symptom | `bloated by noon` | The buyer's own words |
| Mechanism | `NLRP3 inflammasome` | Root-cause pitches that never name the category |
| Ingredient | `thymoquinone` | The same, one level more specific |
| Lab marker | `hs-CRP`, `HOMA-IR` | Clinical-framing funnels |
| TOFU hook | `one weird trick` | Unaware-stage creative directly |

Pairing a TOFU signal with a niche term filters a crowded category down to the advertorials inside it.

### Witness phrases

Start here. Someone else noticing is the most reliable marker of a story-led ad and it is niche-independent, because no product page contains narrative.

```
"my husband noticed"   "my wife noticed"      "my daughter asked"
"my son asked me"      "my granddaughter"     "my grandson said"
"my sister asked"      "my mother told me"    "my best friend asked"
"my neighbor asked"    "my coworker asked"    "people started asking"
"everyone keeps asking" "my doctor asked me"  "my hairdresser noticed"
"my kids noticed"      "nobody believed me"   "my friends noticed"
```

### Turning point and discovery

```
"that's when I"      "then one day"        "until one morning"
"everything changed when"  "I was skeptical"   "I didn't believe"
"I almost didn't"    "she handed me"       "he handed me"
"a friend gave me"   "someone told me about"  "I stumbled across"
"the moment I"       "within days"         "within two weeks"
"by the third night" "on the seventh day"  "I had nothing to lose"
```

### Rock bottom and shame

```
"I was embarrassed"  "I stopped going"     "I avoided"
"I couldn't even"    "I gave up on"        "I was too ashamed"
"I hid it"           "I stopped wearing"   "I cancelled"
"I said no to"       "I overheard"         "I felt invisible"
```

### Failed solutions

```
"I tried everything" "nothing worked"      "I wasted"
"I spent hundreds"   "I spent thousands"   "the pills didn't"
"surgery was the only option"  "they told me it was just"
"I was told it was normal"     "just part of getting older"
```

### Authority

```
"my doctor said"     "the doctor asked"    "top doctor"
"a specialist told me"  "my dermatologist" "my dentist said"
"a pharmacist"       "my vet told me"      "the surgeon said"
"a clinical trial"   "what doctors won't"  "a retired"
```

### Mechanism and relocation

```
"the real reason"    "the root cause"      "what nobody tells you"
"the hidden"         "the real culprit"    "actually starts in"
"has nothing to do with"   "never in your"  "the missing piece"
```

### Per-niche symptom fragments

| Niche | Phrases |
|---|---|
| Sleep | `wake up at 3`, `3am every`, `couldn't fall back asleep`, `wide awake at` |
| Joint | `getting out of bed`, `climbing stairs`, `couldn't kneel`, `stiff every morning` |
| Gut | `bloated by noon`, `after every meal`, `my pants didn't fit`, `looked six months` |
| Hair | `my part was getting wider`, `in the shower drain`, `my ponytail`, `on my pillow` |
| Skin | `in photos`, `in the mirror`, `my jawline`, `I didn't recognize` |
| Menopause | `night sweats`, `hot flashes`, `since menopause`, `soaked through` |
| Prostate | `up three times a night`, `the stream`, `barely make it` |
| Hearing | `the ringing`, `asking people to repeat`, `turning up the tv` |
| Weight | `the scale`, `my clothes stopped fitting`, `the last 20 pounds` |
| Feet | `on my feet all day`, `my arches`, `first steps in the morning` |
| Pets | `my dog stopped`, `my vet said`, `he couldn't jump`, `her breath` |
| Vision | `reading glasses`, `the fine print`, `driving at night` |
| Energy | `by 2pm`, `the afternoon crash`, `dragging myself` |
| Memory | `walked into a room`, `forgetting names`, `brain fog` |
| Oral | `my gums`, `bleeding when I brush`, `the dentist told me` |
| Legs | `swollen ankles`, `my socks left marks` |
| Blood sugar | `my a1c`, `my numbers`, `my last blood test` |
| Anxiety | `racing thoughts`, `my chest tightens`, `couldn't switch off` |
| Household | `my house smelled`, `guests were coming`, `too embarrassed to have` |

### Live chumbox headlines

Read off a real weather.com chumbox in the Georgi training. Useful as phrases to search, as formulas to model, and as a calibration set for what a qualified find looks like.

```
Top doctor: if you eat eggs every day, this is what happens
She took one teaspoon on an empty stomach, now they call it...
This spray is helping thousands hear clearly
The green ginger mix being called the homemade bariatric drink
Why are so many older adults switching to grounded sleep?
Shoppers say this thin hairspray is a lifesaver
If you knew this oven cleaning trick, no scrubbing
These are the Rolls Royce of hearing aids, under $100
Costco shoppers say this wrinkle cream is actually worth it
Endocrinologist tries 57-second trick at home every morning
The Germans have done it again
How I revived a 20-year-old greasy oven in 20 seconds without scrubbing
Breathing issues? This moves the mucus out of your lungs
Discover the sneaky deficiency silently robbing 1 in 45
```

Four formulas carry all of them: **authority plus shocking claim**, **she took X and now they call it Y**, **social proof by retailer**, and **why are so many people switching to X**. Note how many name a specific dollar figure or a number of seconds.

### Using them without burning the well

One phrase per query; combining two narrows to nothing. Rotate the phrase, not only the niche keyword. Log which phrase produced which find, and within a few sessions you will know which twenty carry the corpus.

---

## Reading a URL

**Presell footprints:** subdomains `offer.` `get.` `about.` `tick.` `track.`; slugs `pre6`, `view8208`, `epc-` (earnings per click), `advertorial`, and high variant numbers; throwaway TLDs `.online` `.life` `.club`.

**Media buyers publish their own taxonomy.** Slugs like `mb-lbwf-adv3-funnel-index-lq-adv` expose product code, template version, traffic segment, and format. Title tags sometimes state the funnel position outright ("TOF - Beauty Listicle"). Read the title tag before the copy.

**Fake mastheads** are the durable footprint of a presell network, because the domains rotate weekly and the masthead does not. Google the masthead name to find every advertorial using that template.

---

## Qualification

Hard gates, which fail outright: page live, not a VSL bridge, over the word floor, not already in the ledger.

Then **five format signals against a threshold of three**: disclaimer, byline or date, soft CTA, narrative voice, editorial framing.

**The disclaimer can never be a hard gate.** It is a legal artifact of the presell and affiliate ecosystem. A brand selling its own product has no referral relationship to disclose, so first-party advertorials routinely carry no fine print at all. Requiring it silently deletes everything the sitemap sweep produces. This was found the hard way: an early qualifier rejected 25 consecutive candidates for having no disclaimer and every one of those pages was fine.

**Always read the rejection tally.** If one reason dominates, suspect the filter before the pages.

---

## Scoring

| Signal | Source | Weight |
|---|---|---|
| Archive span in months | Wayback CDX | ×3 |
| Ad run duration, still active | Ad Library | ×2, optional |
| Live variant with dead neighbours | URL probe | ×2 |
| High variant number | Slug | ×1 |
| Recent page date | On page | ×1 |
| Fake "updated N hours ago" | On page | ×0 |

Ad duration is enrichment, never a gate, so no channel becomes a dependency.

**Probe the variant neighbours.** On a numbered slug, fetch N±1 through N±5. A live page surrounded by dead siblings won its own split test, which is harder evidence than the variant number alone. High numbers are also where the brand iterated to, so they tend to be the longest and most fully built pages in a family.

---

## Patterns worth recognising

**One destination, many entry stories.** A single product page carries many advertorials, one per pain point. Georgi's example: the ad names a greasy oven, the advertorial is about reviving an oven, the product page sells an all-purpose cleaner for every stain, and by the time the reader arrives they have been told it cleans other things too. The advertorial is what lets a specific pain land on a general product. Jones Road runs the same shape with one listicle re-angled to busy mothers, professionals, aging skin, minimalists, and skincare buyers.

**One find is a lead on a set.** A brand runs different landers for different ad types, because the lander is calibrated to what the ad already did. A static ad goes to a long story advertorial; a two-minute video ad goes to a short product-forward page that opens directly on the product. When something qualifies, check that brand's other pages and its ad library.

**A short advertorial is not a weak one.** Long advertorials feed product pages, because the product page does no selling. Short ones feed VSLs, because the VSL does the educating and the page only has to carry congruence. Record the destination type rather than judging length in isolation.

**Length is where they iterated to.** In a numbered family, the highest variants tend to be the longest. GroundingWell's `sheet-adv-14` runs 8,357 words while its lower siblings are shorter.

---

## Failure modes, all paid for

**The geo trap.** Live chumbox browsing only works from a US IP. From elsewhere, widgets fill with locally targeted ads and no publisher choice fixes it. Use the indexed disclaimer dorks instead; they reach the same inventory.

**Trusting a save exit code.** The capture script can report success while producing a PDF that shows one popup repeated on every page, because a `position:fixed` overlay prints on every page. Verify the artifact: extract text from three or four spread pages and confirm the content differs.

**Rate limits that masquerade as absence.** Shopify 429s hard and the block persists after you trip it. An unthrottled sweep does not merely fail, it poisons the next several runs, and every failure then reads as "this brand has no sitemap". Both `sitemap_sweep.py` and `qualify.py` throttle per host and report 429 as its own reason. **A log that cannot distinguish "failed the test" from "never took the test" will lie to you.**

**Presell domains rotate weekly.** Save same-day; the capture becomes the only copy. Dork the masthead and the slug pattern rather than the domain.

**Substitute search engines.** Covered above. They do not work.

---

## Keyword buckets, for channel A and B rotation

Never work the same niche two sessions running.

**Supplements:** gut health, probiotics, digestive health, collagen, anti-aging, longevity, greens powder, multivitamin, metabolism, weight loss, adaptogens, nootropics, brain fog, sleep, stress relief, energy, fatigue

**Condition:** bloating, inflammation, joint health, skin health, hair growth, hormone balance, cortisol

**Device and biohacking:** grounding mat, earthing, red light therapy, PEMF, posture corrector, neck massager

**Men's health:** prostate ritual, urinary flow, bathroom trips at night, old pipes toxin, male vitality tonic, calcium buildup

**Respiratory:** mullein extract, lung detox, smokers cough, mucus clearance, heavy chest, bronchial soothe, clear airways

**Sleep and cellular:** transdermal absorption, cortisol killer, magnesium deficiency, deep sleep protocol, mitochondrial energy, photobiomodulation

**Spinal:** cervical traction, tech neck, dowager's hump, forward head posture, nerve compression, decompression

**Parasite and fungal:** thymoquinone, volcanic soil, parasite shell, fungal overgrowth, sugar cravings, gut invaders

**Lectin:** plant paradox, lectin shield, gut lining, holobiotics, postbiotics

**Metabolism:** inner body temperature, metabolic furnace, ice hack, alpine secret, thermogenesis

**Clinical markers:** NAD+, NMN, sirtuin, AMPK, mTOR, leptin, berberine, NLRP3, CRP, TNF-alpha, zonulin, butyrate, Akkermansia, glutathione, NAC, sulforaphane, Nrf2, HPA axis, BDNF, telomere, autophagy, nitric oxide, HOMA-IR, HbA1c

**TOFU hooks:** one weird trick, doctors hate this, ancient secret, 5-second trick, miracle ingredient, nobody tells you, do this before breakfast, what your doctor won't tell you, this little-known
