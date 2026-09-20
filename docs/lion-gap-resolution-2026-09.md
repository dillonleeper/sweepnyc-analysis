# Manhattan August 2026: resolving the four LION-23C-absent PhysicalIDs

The case review found 846 of 850 distinct matched PhysicalIDs present in the
official LION 23C archive. Four IDs, affecting eight violations, were absent:
204036 (1 violation), 206391 (5), 206394 (1), 206507 (1). This resolves all
eight.

## Root cause

`data/raw/pilot/sweepnyc.json` — the frozen August SweepNYC extract — tags
every one of its 464,418 records with `cscl_version: "23C"`. SweepNYC's own
PhysicalID field is keyed to that vintage of the street centerline, not to
whatever CSCL snapshot is current when a query runs. The pilot matcher, by
contrast, assigned violations to street segments using a current (September
2026) CSCL snapshot.

For 1,914 of the 1,922 matched violations, the PhysicalID happens to be
unchanged between the 23C vintage and the current snapshot, so matching
directly on ID against `sweepnyc.json` worked correctly. For these four
segments, the PhysicalID was renumbered between vintages. The current-vintage
ID the matcher assigned does not appear in LION 23C (because that ID did not
exist yet in 2023) and also does not appear in the 23C-keyed SweepNYC
extract — even where an August sweep of that street segment actually was
recorded, under the older ID.

**Scope check:** re-matching all 1,922 matched violations' street/house/zip
against LION 23C address ranges confirms the ID-vintage mismatch is confined
to exactly these four segments and these eight violations. No other matched
violation's ID differs between vintages. This does not, on its own, rule out
segments among the 850 whose ID happens to be numerically unchanged between
vintages but attached to a different real segment (an ID-reuse scenario);
address-range identity for the 846 present-in-LION-23C IDs was not
individually re-verified beyond the original case review's five addresses.

## Resolution

Each of the eight violations' street, house number, and ZIP was matched
against LION 23C address ranges using the same matcher used for CSCL
(`sweepnyc.matching.match_oath_to_cscl`), and corroborated by the distance
from the address point (from the saved AddressPoint extract) to the unioned
LION 23C segment geometry in EPSG:2263 feet. All eight matches were
unambiguous (`exact` quality, single candidate) and well within the
distances (26–66 ft) accepted as corroborating in the five-case review.

| Address | Tickets | Original (current-CSCL) ID | Reviewed (23C-vintage) ID | Distance (ft) | August sweep observation? |
|---|---|---:|---:|---:|---|
| 51 Bayard Street | 046898837M | 204036 | 140952 | 26.02 | No |
| 600 West 157 Street | 049994082M | 206507 | 26986 | 35.51 | Yes |
| 229 Henry Street | 049935143R, 049906526L, 049968594R | 206391 | 4251 | 40.24 | Yes |
| 231 Henry Street | 049906527N, 049968595Z | 206391 | 4251 | 40.50 | Yes |
| 25 Montgomery Street | 049961979X | 206394 | 80069 | 65.63 | Yes |

Seven of the eight violations recover an August sweep observation that the
original current-CSCL-keyed match missed. The Bayard Street segment has no
record under either ID vintage in the frozen August extract; that is treated
as a genuine absence of an August observation for that segment, not a
matching artifact.

All eight are marked `case_reviewed = True` in `reviewed_matches.csv`
alongside the five-case review's three corrections (13 total). Reviewed
sweep overlap across the full reviewed population is now **1,499 / 2,028
(73.92% of eligible; 78.0% of matched)**, up from 1,492 / 1,922 (73.57%;
77.63%) before this correction. Original assignments, quality labels, and
the 1,922/2,028 coverage figure are unchanged; only the reviewed columns for
these eight rows changed.

## An informal, unreproducible check

The public SweepNYC lookup (`sweepnyc.nyc.gov/mappingapi/api/highlight/sweepinfo`)
was queried for these five addresses' coordinates to see which ID vintage
the live operational system currently reports. It returned the 23C-vintage
ID for Henry Street, Montgomery Street, and West 157 Street, but the
current-vintage ID (204036) for Bayard Street — an inconsistency this
document does not attempt to explain. This check was made through a tool
without exact byte-level request/response logging or checksums (unlike
`fetch_case_sources.py`'s pattern), so it is not reproducible and is not
used as evidence for the resolution above; it is noted only as corroborating
context. It does not change the conclusion, since the frozen August extract
— not the live lookup — is what determines the reviewed sweep-overlap flag.

## Limitations

LION 23C is not verified to be the exact CSCL 23C snapshot DSNY/SweepNYC use
internally — the same open question the five-case review left unresolved.
`docs/cscl-23c-data-request.md` remains unsent. Address-range identity was
checked for these eight violations' four segments specifically; it was not
re-verified for the remaining 846 present-in-LION-23C matched IDs.

## Reproduction

```text
PYTHONPATH=src python scripts/resolve_lion_gap_cases.py
```

Requires the case-review bundle's extracted `data/raw/adjudication/lion_23c/`
archive (see `scripts/fetch_case_sources.py --replay`) and the pilot's
`data/processed/pilot/matches.csv` and `data/raw/pilot/sweepnyc.json`. Writes
`data/processed/adjudication/lion_gap_resolution_summary.json` and updates
`reviewed_matches.csv` in place (extending, not replacing, the five-case
review's corrections). Input checksums are saved to
`data/processed/adjudication/lion_gap_resolution_checksums.json`.
