# Manhattan August 2026: violations against recorded sweeper visits, by street segment

This looks at the 851 Manhattan street segments linked to at least one
eligible August 2026 sanitation violation, comparing how many violations
each carries against how many days SweepNYC recorded a mechanical-broom
visit there in August. **It does not test whether sweeping reduces
violations, and it is not a citywide picture of street cleanliness** — see
Limitations.

## What a "street segment" is

A CSCL/LION `PhysicalID` covers one street's stretch between two consecutive
cross streets (an intersection-to-intersection run), for both curb sides and
both travel directions together. It is **not** a whole city block: the block
bounded by four streets is made of up to four separate segments, one per
side. "229 Henry Street" and "231 Henry Street" share one segment because
they sit on the same stretch of the same street, but a segment on Henry
Street and a segment on the cross street at the same corner are different
records entirely.

## What "eligible violations" and "visit" mean here

- **Eligible violations**: the pilot's 2,028 relevant DSNY OATH cleanliness
  violations for August 2026 in Manhattan (unchanged from the original pilot
  and validation milestones).
- **Reviewed PhysicalID**: the segment ID after the five-case review (three
  West 125th/East 27th Street corrections) and the four-ID LION-23C-vintage
  correction (see [`lion-gap-resolution-2026-09.md`](lion-gap-resolution-2026-09.md)).
  Using the reviewed ID, rather than the original current-CSCL-vintage ID,
  matters here specifically: it recovers 7 real August observations that
  the original ID vintage missed.
- **Visit**: SweepNYC's raw August extract (`data/raw/pilot/sweepnyc.json`)
  has 464,418 records, each a GPS association between a `PhysicalID` and a
  timestamp, all tagged `cscl_version: 23C`. 13,333 of those records
  (about 2.9%) share a segment and calendar date with another record from
  minutes to a few hours later that same day — plausibly two curb-side
  passes sharing one ID, or an artifact of the GPS-association process; the
  data doesn't say which. Per this project's standing instruction that
  duplicate observations must not inflate visit counts, **a visit here means
  a distinct (segment, calendar day) pair** — 451,085 of them citywide in
  August. A same-day second GPS association is counted once, not twice.

## The table

`data/processed/segment_analysis/manhattan_segment_table.csv` has one row
per violation-linked segment: the reviewed and original PhysicalID (and
whether it was corrected), a representative street name, the eligible
violation count and ticket numbers, the August visit-day count, and the
first/last visit date. 851 segments carry the pilot's 1,922 matched
violations; 663 have at least one recorded August visit-day, 188 have none.

## Segments worth a closer look

**Frequent violations despite a recorded sweep.** These 15 segments have the
most violations among segments SweepNYC did record visiting in August. A
recorded visit is evidence a broom passed by, not evidence the street stayed
clean or that enforcement activity tracks litter volume — see Limitations.

![Top violation segments with a sweep observation](../data/processed/segment_analysis/top_violations_with_sweep_observation.png)

**No recorded August observation.** These 15 segments have violations but no
SweepNYC record at all in August. Absence of a record does not prove no
sweeper visited — see Limitations — but a segment with several violations
and zero recorded service is a reasonable starting point for someone
checking SweepNYC's coverage.

![Top violation segments with no sweep observation](../data/processed/segment_analysis/top_violations_no_sweep_observation.png)

**How concentrated is this?** Most violation-linked segments have only one
or two violations in August; a small number carry far more.

![Violation count distribution](../data/processed/segment_analysis/violation_count_distribution.png)

## Limitations

- **This is not causal, and it is not a cleanliness measurement.** A
  violation reflects DSNY enforcement activity, not a direct litter count;
  a SweepNYC record reflects a GPS-tracked broom pass, not a verified
  cleaning outcome. Neither the "frequent violations despite sweeps" list
  nor the "no observation" list says whether sweeping helped, whether
  enforcement targeted these blocks more heavily, or whether violations
  happened before or after the recorded visits within the month.
- **Violation-linked population only.** These 851 segments are the ones
  with at least one matched violation; they are a small, non-random slice
  of Manhattan's several thousand street segments, and nothing here
  describes segments outside this set.
- **No citywide rate or ranking is computed.** Counts here are absolute, not
  normalized by segment length, traffic volume, or population — a
  denominator this data does not support.
- **"No August observation" is a data-absence label, not a service-absence
  claim.** SweepNYC's own record could be incomplete for operational
  reasons unrelated to whether the street was actually swept.
- **Exact CSCL 23C alignment is still open.** As in the case review and
  validation milestones, LION 23C is not verified to be byte-identical to
  whatever CSCL 23C snapshot SweepNYC's backend used to generate these
  PhysicalIDs; the correction relies on address-range and geometric
  corroboration, not a confirmed authoritative crosswalk.
- **99 ambiguous and 7 unmatched violations are excluded** from this table
  entirely, as in the original pilot; they carry no PhysicalID to join on.

## Reproduction

```text
PYTHONPATH=src python scripts/build_segment_table.py
```

Requires `data/processed/adjudication/reviewed_matches.csv` (from the case
review and LION-gap resolution scripts) and `data/raw/pilot/sweepnyc.json`.
Writes `data/processed/segment_analysis/manhattan_segment_table.csv`,
`summary.json`, and `checksums.json`. Charts were generated separately with
matplotlib from the same CSV; regenerating them does not require new data.
