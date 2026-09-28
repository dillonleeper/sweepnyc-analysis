# Methodology

## Project thesis

The project asks whether a documented NYC mechanical street-sweeping event is followed by measurable improvement in observable street-cleanliness indicators.

The analysis should distinguish three concepts:

1. **Treatment** — a SweepNYC traversal of a CSCL street segment.
2. **Outcome signals** — OATH sanitation violations and later 311 cleanliness complaints.
3. **Context/confounders** — factors that may affect both cleaning and cleanliness, such as neighborhood, street type, weather, seasonality, commercial activity, and cleaning schedule.

## Phase 1: linkage validation

The immediate task is not causal inference. It is entity resolution.

### Preferred linkage

```text
OATH sanitation record
    |
    +-- borough/block/lot and/or address
    v
NYC parcel/address reference
    |
    v
CSCL PHYSICALID
    |
    v
SweepNYC street segment
```

The matching pipeline should prefer deterministic identifiers over fuzzy text matching.

Suggested hierarchy:

1. borough + block + lot where sufficient;
2. exact address-point match;
3. normalized house number + street + borough;
4. geospatial fallback to a unique adjacent CSCL segment;
5. otherwise mark ambiguous/unmatched.

### Match-quality classes

- `exact` — deterministic identifier or unique exact address/segment match.
- `high_confidence` — unique geospatial/address match after normalization.
- `ambiguous` — multiple plausible segments.
- `unmatched` — no defensible segment assignment.

Do not silently force ambiguous records onto the nearest segment.

### Go/no-go metric

```text
match_rate =
(exact + high_confidence)
/
all eligible OATH cleanliness records
```

Initial project threshold: **>= 80%** for the pilot sample.

This is an engineering threshold chosen for the project, not a known property of the NYC datasets.

## Phase 2: descriptive event analysis

Once linkage is validated:

- construct segment-day panels;
- identify cleaning events;
- count relevant outcome events in windows before and after cleaning;
- inspect distributions and seasonality;
- estimate simple event-time curves.

Example windows:

- 24 hours before/after;
- 72 hours before/after;
- 7 days before/after.

## Phase 3: stronger inference

A naive before/after comparison is vulnerable to confounding.

Candidate approaches:

- matched street segments;
- segment fixed effects;
- date/time fixed effects;
- event-study specification;
- difference-in-differences where treatment timing permits;
- weather and seasonal controls;
- sensitivity analyses by violation category.

Results should be described as associations unless the identification strategy supports stronger causal language.

## Outcome selection

Start narrowly with violation categories most directly related to street/curb cleanliness. Broader sanitation categories should be added only after reviewing their definitions and physical relevance to mechanical sweeping.

Keep outcome families separate:

- roadway/curb cleanliness;
- sidewalk cleanliness;
- waste-container compliance;
- illegal dumping;
- citizen-reported dirty conditions.

## Reproducibility

Raw source extracts should not be committed to GitHub.

Each analysis dataset should be reproducible from:

- source dataset IDs;
- query parameters;
- extraction date;
- transformation code;
- documented filters.

## Implemented August 2026 pilot rules

The current implementation uses normalized street names, numeric house ranges,
and parity within Manhattan. A unique PHYSICALID is `exact`; a unique range match
whose house number has a letter suffix is `high_confidence` because the letter is
ignored. These are algorithmic labels, not independently verified accuracy.
ZIP narrows street candidates when a matching ZIP exists; absent or conflicting
ZIPs do not by themselves prevent a house-range match. Multiple qualifying IDs
remain ambiguous. A unique street without a valid house-range match is unmatched.
Reversed range endpoints are supported. Bare street-name aliases are included
alongside full street names and display labels from CSCL.

Eligibility uses the documented cleanliness phrases in violation_description or
any of the ten charge descriptions. The denominator is eligible source rows,
including ambiguous and missing-address records; the observed extract is also
checked for duplicate ticket numbers. This includes sidewalk/property categories,
so it is not limited to conditions mechanical sweeping directly addresses.

The SweepNYC extract is citywide for the month. Its IDs are intersected with
Manhattan matched IDs. Record counts and distinct segment counts are reported
separately. No visit in the monthly extract means no documented overlap, not
proof that a street was never cleaned. A visit can precede or follow the violation.
SweepNYC identifies CSCL version 23C; the current CSCL reference is not version
aligned, so identifier stability remains a validation limitation. Historical
reference matching and manual address review remain follow-up work.

Pagination uses ordered Socrata row IDs. The service does not provide transaction
isolation across pages: saved extracts and checksums define the reproducible
observation. The 80% rule assesses assignment coverage, not measured precision
or causal effectiveness.
