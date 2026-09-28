# Phase 2: does a recorded sweep reduce violations or complaints?

This is the project's first effectiveness analysis, built on top of the
Phase 1 linkage validated at 94.77% coverage
([`segment-analysis-2026-08.md`](segment-analysis-2026-08.md)). It asks the
project's actual research question for the first time: **does a documented
SweepNYC visit predict fewer OATH cleanliness violations, or fewer 311
dirty-condition complaints, on that street segment?**

**Headline: still no on the day-level question, with one genuinely new
wrinkle.** Against OATH violations (the primary outcome), this finds no
statistically significant relationship, in either direction, between a
recorded sweep and eligible violation counts. Against 311 complaints (added
in a second pass, once this session solved its NYC Open Data network-access
blocker — see below), the August-only same-day model initially looked
suggestive (p=0.093, in the expected direction), but a follow-up pass adding
July 2026 found that result **moved toward null rather than strengthening**
(p=0.291) — see "Follow-up: does the 311 signal hold up with more data?"
below. Adding a daily rain control didn't change any of that (see "Design-gap
remediation" below) — the day-level null is not a weather artifact.

The one new wrinkle: once real street-type covariates (width, lane count,
one-way/two-way, functional-class proxy) were fetched, a genuine
covariate-matched comparison — segments that are *ever* swept vs.
structurally similar segments that are *never* swept — found swept segments
have fewer violations and fewer 311 complaints. That result is significant
in the naive version of the test, but drops to non-significant (violations)
or borderline (311, p=0.087) once corrected for how few distinct "donor"
segments the matching actually drew from. See "Design-gap remediation"
below — this is a different question from the day-level models above (does
sweeping happen on structurally different streets, not does a given day's
sweep reduce that day's violations), and neither confirms nor overturns the
day-level null. Nothing in this document should be read as a settled
verdict on whether sweeping works; see Limitations for why the scope here
is too narrow for that.

## Data and population

Same population as the segment-analysis milestone: the 851 Manhattan street
segments linked to at least one eligible August 2026 OATH cleanliness
violation, using the reviewed PhysicalIDs from Phase 1. Built into a panel
with **one row per (segment, calendar day)** for all 31 days of August 2026
— 26,381 segment-days total.

| Column | Meaning |
| --- | --- |
| `physical_id` | Reviewed CSCL PhysicalID |
| `date` | Calendar date, 2026-08-01 to 2026-08-31 |
| `swept` | 1 if SweepNYC recorded a visit to this segment this day |
| `violation_count` | Eligible OATH cleanliness violations recorded this segment-day |
| `day_of_week` | For day-of-week fixed effects |
| `segment_ever_swept_in_august` | 1 if the segment has any recorded August visit at all |
| `complaint_311_count` | Eligible 311 complaints ("Dirty Condition", "Street Sweeping Complaint") on this segment-day, address-matched to the same 851-segment population |

Built by [`scripts/build_event_panel.py`](../scripts/build_event_panel.py)
from `reviewed_matches.csv` (violations), `sweepnyc.json` (visits), and
`matched_311.json` (311 complaints), all fetched and checksummed. The OATH
and sweep data were fetched during Phase 1; the 311 data is new to this pass.

**How the 311 data was fetched.** The original version of this document
reported that this session's shell had no network route to NYC Open Data
(the proxy returned a 403). That's still true for the shell — but this
session is also linked to the user's own computer, and its browser pane
*does* have working network access. `scripts/match_311_to_segments.py`
reflects the fix: 1,380 Manhattan "Dirty Condition"/"Street Sweeping
Complaint" 311 records for August 2026 were fetched by running real
`fetch()` calls against the Socrata API (`erm2-nwe9`) from that browser,
paginated in 300-record pages, and saved into
[`data/raw/phase2/`](../data/raw/phase2/) with a manifest and checksum. They
were then address-matched to the 851-segment population using the same
street-normalization and house-range logic Phase 1 validated for OATH
(`scripts/match_311_to_segments.py`, reusing `src/sweepnyc/matching.py`).
Of the 1,380 fetched records, 394 (28.6%) matched a Phase-1-population
segment; 718 were on Manhattan segments outside that population (a real,
expected result — the 851 segments are the minority of Manhattan blocks
that already had an OATH violation, not a random sample), and 268 were
unmatched or ambiguous by address. Weather data has not yet been pursued
the same way — see Suggested next steps.

Panel-level facts: 663 of 851 segments have at least one recorded August
visit (188 have none); 10,078 of 26,381 segment-days are swept days. The
**median gap between two recorded sweep-days on the same segment is 1
day** — sweeps are frequent on this population, which shapes the method
choice below.

## Method

A classic before/after event window (e.g., violations in the 3 days before
a sweep vs. the 3 days after) doesn't work well here: with a 1-day median
gap between sweeps, that window mostly overlaps the *next* sweep, not a
clean "before" period. Instead this uses two complementary approaches:

**1. Segment fixed-effects panel regression** (the main result):

```
violation_count[i,t] ~ swept[i,t] + segment_i + day_of_week_t
```

run twice — once with same-day violations as the outcome, once with the
*next day's* violation count as the outcome (does today's sweep predict
tomorrow's violations?). Standard errors are clustered by segment. Segment
fixed effects mean every segment is compared only against its own other
days, controlling for anything about that block that doesn't change during
August (width, traffic, baseline enforcement attention). This is the
project's substitute for covariate-matched controls — see below for why.

**2. Days-since-last-sweep chart** (descriptive): for every segment-day,
how many days has it been since that segment's most recent recorded sweep
(0 = swept today), and what's the average violation count at each value.
Rendered by
[`scripts/render_effect_charts.py`](../scripts/render_effect_charts.py).

**3. Same two fixed-effects models, repeated with 311 complaints as the
outcome** instead of OATH violations
(`complaint_311_count[i,t] ~ swept[i,t] + segment FE + day-of-week FE`, and
the next-day lead version). 311 and OATH are independent signals with
different noise sources — 311 depends on a resident noticing and reporting,
OATH depends on an inspector being present — so running the same design on
both is a mild form of triangulation, not just more of the same data.

**Why fixed effects instead of matched controls.** The plan
([`README.md`](../README.md)) called for comparing swept segments against
similar *unswept* segments. Building real matched controls needs covariates
this project hasn't joined in — street width, class, typical foot traffic —
CSCL's fields alone (address ranges, ZIP) aren't a service-need proxy. The
188 segments with zero recorded August visits are not a valid substitute
control group: a segment with no recorded visit may simply not be on an
active sweeping route, not because it's already clean, so comparing it to a
swept segment mixes the sweep effect with "why does this segment get swept
at all." Segment fixed effects sidestep that by never comparing across
segments at all — only a segment against its own other days.

## Results

**OATH violations:**

| Model | Coefficient (extra violations per segment-day) | p-value | n |
| --- | --- | --- | --- |
| Same-day: `violations[t] ~ swept[t]` | +0.0057 | 0.378 | 26,381 |
| Next-day: `violations[t+1] ~ swept[t]` | +0.0017 | 0.798 | 25,530 |

Both coefficients are small, positive (the *wrong* direction if sweeping
helps), and not statistically distinguishable from zero. The unadjusted
descriptive numbers tell the same story: 0.084 violations/day on swept days
vs. 0.066 on unswept days (raw, uncontrolled — segments that get swept more
also tend to be busier corridors with more enforcement attention, which is
exactly what the fixed-effects model is trying to net out).

**311 complaints** (394 eligible complaints matched into the panel, 202
distinct segments with at least one):

| Model | Coefficient (extra 311 complaints per segment-day) | p-value | n |
| --- | --- | --- | --- |
| Same-day: `complaints_311[t] ~ swept[t]` | -0.0044 | 0.093 | 26,381 |
| Next-day: `complaints_311[t+1] ~ swept[t]` | +0.0016 | 0.574 | 25,530 |

The same-day 311 coefficient runs in the direction sweeping would predict —
fewer complaints on swept days — and is closer to conventional significance
than anything in the OATH models, but p=0.093 is above the standard p<0.05
threshold, so this reads as **suggestive, not confirmed**. The next-day 311
result is null, same as OATH's. The unadjusted numbers point the same way:
0.013 complaints/day on swept days vs. 0.016 on unswept days.

Worth naming plainly: this is one weakly-suggestive coefficient out of four
models tested here (two outcomes x two horizons), which is within the range
a null underlying effect could produce by chance alone, especially without
a multiple-comparisons correction. It is a reason to look harder with more
data, not a result to lead with.

![Violations by days since last recorded sweep](../data/processed/effect_analysis/violations_by_days_since_sweep.png)

The days-since-sweep chart shows no clean rising or falling pattern —
day-0 and day-1 sit around 0.08, day-2 dips to 0.04, day-4 rises back to
0.09, with wide, overlapping error bars throughout. It reads as noise
around a flat line, not a decay curve.

Full numeric output: `data/processed/effect_analysis/effect_analysis_results.json`.

## Follow-up: does the 311 signal hold up with more data?

The suggested next step above was to extend the panel and see whether the
same-day 311 result strengthens or dissolves. It's now been done: July 2026
was fetched and matched the same way as August (same browser-fetch pipeline,
same 851-segment population, same 311 matching method), and the two months'
segment-days were combined into
`data/processed/effect_analysis/segment_day_panel_multi_month.csv`
(52,762 rows) via
[`scripts/build_multi_month_panel.py`](../scripts/build_multi_month_panel.py),
with the same fixed-effects models (now also holding month fixed) re-run by
[`scripts/run_effect_analysis_multi_month.py`](../scripts/run_effect_analysis_multi_month.py).

**One important asymmetry, read before comparing the numbers below:**
August's OATH violations are Phase 1's fully manually reviewed
`reviewed_matches.csv` (case review, LION-gap resolution, spatial
corroboration). July's OATH violations are automated-match-only
([`scripts/match_oath_month.py`](../scripts/match_oath_month.py)) — the same
first-pass method Phase 1 started from *before* its human review — so July's
OATH counts are lower-confidence than August's. **311 matching used the
identical automated method for both months**, so the 311 comparison below
is apples-to-apples in a way the OATH comparison isn't.

**Answer: the suggestive 311 result did not hold up — it moved toward null.**

| Model | August only (n=26,381) | July+August (n=52,762) |
| --- | --- | --- |
| Same-day 311: coefficient | -0.0044 | -0.0018 |
| Same-day 311: p-value | 0.093 | 0.291 |
| Next-day 311: coefficient | +0.0016 | +0.0008 |
| Next-day 311: p-value | 0.574 | 0.696 |

![Same-day 311 coefficient, August-only vs two-month](../data/processed/effect_analysis/same_day_311_coefficient_comparison.png)

Doubling the sample cut the same-day 311 coefficient by more than half and
pushed its p-value from "close to conventional significance" to
comfortably-not-significant. That is exactly the outcome a real null effect
produces when more data reduces sampling noise around zero — the opposite of
what a real effect would do (which typically holds its estimate steady or
sharpens as noise shrinks). **This is the honest result of following up on
the earlier finding, not a disappointing one to downplay: the whole point of
flagging p=0.093 as "suggestive, not confirmed" was that it needed exactly
this kind of check before anyone treated it as evidence.**

The OATH same-day coefficient also stayed small and non-significant
(+0.0025, p=0.602, vs. August-only's +0.0057, p=0.378) — consistent with the
311 story, for what a lower-confidence July OATH match is worth. Full output:
`data/processed/effect_analysis/effect_analysis_results_multi_month.json`.

## Design-gap remediation: weather and a real matched-control design

The two design gaps named as this project's highest-value next moves (see
the previous version of "Suggested next steps") were: (1) a weather control,
to rule out rain as a hidden common cause of sweep timing and 311/OATH
reporting; and (2) a genuine matched-control design using real street-type
covariates, instead of the segment-fixed-effects substitute used above.
Both are now done.

**Weather.** Daily precipitation/temperature for Central Park
(station `USW00094728`, NOAA NCEI GHCN-Daily, fetched via the same
browser-fetch technique used for 311/OATH/sweep — see
`data/raw/phase2/design_gap_manifest.json`) was joined onto every panel day
by date (`scripts/build_weather_features.py`), and the four two-month
fixed-effects models were rerun with a `rained` (>=1.0mm) control added
(`scripts/run_effect_analysis_with_weather.py`):

| Model | Swept coefficient, no weather control | Swept coefficient, with rain control | `rained` coefficient (own effect) |
| --- | --- | --- | --- |
| Same-day OATH | +0.0025 (p=0.602) | +0.0023 (p=0.630) | -0.0062 (p=0.050) |
| Next-day OATH | +0.0037 (p=0.373) | +0.0033 (p=0.436) | -0.0144 (p<0.001) |
| Same-day 311 | -0.0018 (p=0.291) | -0.0018 (p=0.276) | -0.0020 (p=0.099) |
| Next-day 311 | +0.0008 (p=0.696) | +0.0007 (p=0.716) | -0.0016 (p=0.147) |

Rain itself has a real, mostly statistically significant negative
association with both outcomes (fewer violations and complaints on and
after rainy days — plausibly less litter accumulation, fewer inspectors and
residents out) — so it was worth controlling for. But the swept coefficients
barely move at all once it's added. **Rain was not hiding or distorting the
day-level swept effect; the null result is robust to it.** Full output:
`data/processed/effect_analysis/effect_analysis_results_with_weather.json`.

**Real matched controls.** A fuller extract of the CSCL street-centerline
table (`inkn-q76z`, not the address-range-only fields Phase 1 originally
pulled) was fetched with genuine street-type fields — roadbed width, travel/
park/total lane counts, one-way vs. two-way, DSNY snow-plow priority tier
(used as a functional-class proxy, since CSCL's own `fcc` field is null for
every Manhattan row in this extract), and truck-route designation
(`scripts/build_street_covariates.py`). This finally makes possible the
matched-control design the original plan called for and the fixed-effects
section above explained wasn't yet buildable: for each of the 186
never-swept segments with usable covariates, `scripts/run_matched_control_analysis.py`
finds its closest structurally-similar *swept* segment (exact match on
one-way + snow-priority tier, nearest-neighbor by standardized width/lane
counts within that group) and compares their two-month outcome rates.

| Outcome | Never-swept mean/day | Matched-swept mean/day | Naive paired-t p (n=186) | Donor-collapsed paired-t p (n=52 unique donors) |
| --- | --- | --- | --- | --- |
| Eligible violations | 0.0656 | 0.0472 | 0.009 | 0.175 |
| 311 complaints | 0.0143 | 0.0054 | 0.0003 | 0.087 |

Read the right-hand column, not the naive one: only **52 distinct swept
segments** end up serving as the nearest match for all 186 never-swept
segments (the three busiest donors alone cover 64 of the 186 pairs), so the
"186 independent pairs" the naive test assumes isn't real — those repeated
donors make many pairs non-independent draws. Collapsing to one row per
unique donor is the honest sample size, and at that size the violations
result is not significant (p=0.175) and the 311 result is borderline
(p=0.087, same direction as the naive result but well short of
conventional significance).

**How to read this alongside the day-level null above:** this is a
different comparison — *do segments that ever get swept differ from
structurally similar segments that never do*, not *does a given day's sweep
reduce that day's violations*. It's still confounded by anything the
covariates don't capture (why DSNY put a segment on a sweep route in the
first place is itself unobserved) and by reverse causality. Taken together
with the day-level result: there's a hint that swept and never-swept
streets look different beyond street width/lanes/one-way-ness, but it's not
strong enough, at this sample size, to call it a sweeping effect rather
than an artifact of which streets get put on a route. Full output:
`data/processed/effect_analysis/matched_control_results.json`,
`data/processed/effect_analysis/matched_control_pairs.csv`.

## What this does and doesn't show

**It does not show that sweeping doesn't work.** A null result from two
months, one borough, and a small, non-random population (851 segments, all
selected *because* they already had a violation) has limited power to
detect a real effect even if one exists. What it does show is that the
plan's simplest test — recorded sweep vs. next-day violations, and the same
test against 311 — doesn't turn up an effect in this two-month slice, and
that the one earlier hint of a possible effect did not survive a direct
follow-up test built to check exactly that. The project's next moves (below)
are designed to address the remaining reasons a real effect could still be
hiding.

## Limitations (read before presenting this)

- **Weather and street-type covariates are now joined in — see "Design-gap
  remediation" above — but neither closes the gap it was meant to close.**
  The rain control leaves the day-level null unchanged; the street-type
  matched-control result is directionally interesting but not robust to the
  donor-reuse correction, so it's a lead, not a finding.
- **The matched-control donor pool is thin and reused.** Only 52 distinct
  swept segments end up matched to all 186 never-swept segments; the
  effective sample size for that comparison is much smaller than 186 pairs
  suggests, and the busiest 3 donors alone cover a third of the pairs.
- **Weather is one station applied city-wide.** Central Park's daily
  reading stands in for every Manhattan segment; it can't capture a
  localized downpour hitting one neighborhood and not another.
- **The 311 match rate to this project's population is low by design, and
  the resulting sample is small.** Only 394 of 1,380 fetched August 311
  complaints (28.6%) landed on one of the 851 Phase-1-population segments;
  most Manhattan 311 activity is simply on other blocks. That's expected,
  not a matching failure, but it means the 311 models are working with a
  much thinner sample (394 events across 851 segments x 31 days) than the
  OATH models (1,922 events on the same panel), so they have less power to
  detect a real effect — worth keeping in mind when the same-day 311
  coefficient came closer to significance than any OATH result did.
- **Two months, one borough, non-random segments.** All 851 segments were
  selected because they already had an August violation; the panel says
  nothing about segments that never get a violation, or about any other
  borough.
- **July's OATH matches are automated-only, not manually reviewed like
  August's.** See "Follow-up" above. This doesn't change the 311-based
  conclusion (311 matching is identical across months) but means the
  two-month OATH numbers specifically should be read as lower-confidence
  than August-only.
- **No real matched-control group**, as explained above. Fixed effects
  control for time-invariant segment traits, not for anything that varies
  within August (e.g., a targeted enforcement push on one corridor).
- **OATH violations require an inspector to be present.** A day with a
  sweep and no violation could mean the block was actually clean, or just
  that no inspector walked it that day. This affects both models equally
  (it's noise, not a bias toward one conclusion), but it does mean weak
  power — real effects can hide inside inspector-visit noise.
- **The sweep-frequency structure itself is unusual and worth a second
  look.** A median 1-day gap between recorded sweep-days is very frequent
  for mechanical broom service and should be sanity-checked against DSNY's
  published ASP sweeping schedule before leaning on it — see next steps.

## Suggested next steps

1. **Get August's manual-review rigor applied to July's OATH matches**, so
   the two-month OATH comparison isn't asymmetric — currently the 311
   comparison is the trustworthy apples-to-apples one, and OATH isn't.
2. **Grow the matched-control donor pool before trusting its result either
   way.** The 311 signal there (p=0.087 donor-collapsed) is the closest
   thing to a live lead this project has — widening the population beyond
   "851 segments that already had an August violation" (e.g., a random
   sample of swept AND never-swept Manhattan segments, not just
   violation-linked ones) would both grow the never-swept side and give the
   matcher more distinct swept donors to draw from, rather than reusing the
   same handful repeatedly.
3. Sanity-check the 1-day median sweep gap against DSNY's published ASP
   schedule for a handful of these segments — confirm it reflects real
   service frequency rather than a data artifact.
4. Extend the day-level panel further (beyond July+August) if there's still
   appetite to chase statistical power on the fixed-effects question — two
   months of null results is more informative than one, but still not
   enough to rule out a real, smaller effect than this design has power to
   detect. This is now the lower-priority of the two extensions (see #2).
5. If pursuing the matched-control lead further, consider PLUTO land-use
   fields (commercial vs. residential frontage, building density) as
   additional match covariates — CSCL's street-geometry fields say nothing
   about what's actually on the block, which is plausibly closer to why
   DSNY routes a sweeper there at all.
