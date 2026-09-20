# Manhattan linkage validation — September 19, 2026

**Readiness: Needs revision before declaring linkage accuracy validated.**
**Milestone completeness: Partial.** The reproducible sample audit and unresolved-record review are complete; independent ground-truth precision and exact CSCL 23C alignment remain open.

## What the audit established

| Check | Observed result |
| --- | --- |
| Random matched-record sample | 100 violations, 99 distinct addresses |
| Sample spatially corroborated | 94 / 100 |
| Sample requiring boundary/competing-segment review | 5 / 100 |
| Sample without an exact suffixed address point | 1 / 100 |
| Corroborated sample records with a field-validated source point | 25 / 100 |
| All matched records spatially corroborated | 1,729 / 1,922 (89.96%) |
| All matched records requiring spatial review | 115 |
| All matched records without an exact address point | 73 |
| Matched records with conflicting spatial evidence | 3 |
| Matched records whose ID is missing from current reference | 2 |
| Originally unresolved records reviewed | 106 / 106 |
| Unresolved records with a plausible spatial candidate | 74 / 106 |
| Unresolved records without an exact address point | 32 / 106 |

**94% is a corroboration rate, not measured accuracy.** AddressPoint and Centerline
share CSCL lineage. Field-validation codes describe the source agency's work, not
a new field visit. No independent imagery/address truth set was available in this
audit. Missing points and boundary flags are not automatically incorrect matches.
The full-population corroboration count is available, so the 100-record sample is
not used to estimate an overall accuracy rate.

All four letter-suffixed matched addresses were checked. Two fell within the
random sample; two were additional challenge cases. Two have exact corroborating
points (363B West 18 Street and 217A West 80 Street); two do not (2527 B and 2395 B
Frederick Douglass Boulevard). Letters were preserved during point lookup.

## Priority findings and next actions

### 1. Three assignments conflict with field-validated address points

At **541 and 545 West 125th Street**, three violation records were assigned to
PHYSICALID **19407** using its published house ranges. The exact address points
favor adjacent PHYSICALID **117672**. Assigned versus alternative distances are
100.79 vs 56.43 feet for 541, and 152.21 vs 54.88 feet for 545. The alternate segment
is at least 83.51 feet from its endpoint along the line. These cases also share
blockface IDs across the two segments, which is another reason to avoid confusing
blockface correctness with exact PHYSICALID correctness.

**Fixed:** the validation output now puts these records in `assignment_holds.csv`
with the competing evidence. The frozen pilot assignments were not overwritten.
**Proposed:** adjudicate against the historical segment geometry and a separate
address reference before changing IDs. A nearest-line suggestion alone is not a
replacement rule.

### 2. The reference really changes, even within this work session

The frozen pilot reference has 14,106 rows; the audit reference has 14,107.
Three IDs were added, two disappeared, and eight common IDs changed selected
name/range/ZIP attributes. One changed-attribute ID is used by the pilot.
PHYSICALID **81213** is absent from the new table. Two violations at **13 East 27th
Street** would now be assigned to **208230**. The same matcher on the refreshed
reference changes exactly these two assignments; aggregate coverage remains
1,922 / 2,028 and August sweep overlap remains 1,492 / 2,028. Neither of these two
records had recorded August overlap under either ID.

**Fixed:** snapshots are separate and checksummed; missing-current-ID cases are
classified as reference drift, not proven address errors. Baseline outputs remain
unchanged. **Still required:** exact CSCL 23C geometry or an official ID crosswalk.

### 3. Review suggestions exist for 74 of the 106 unresolved violations

| Diagnostic group | Records | Next action |
| --- | ---: | --- |
| Overlapping house ranges; spatial candidate found | 47 | Review candidate against version-aligned reference |
| Range/parity conflict; spatial candidate found | 27 | Investigate source ranges and exceptions |
| Uptown Seventh Avenue alias gap | 14 | Use official street-name/alias relationships |
| Other missing exact address point | 9 | Check range-based/alternative address records |
| Fraction written as `1 2` in house number | 3 | Parse fractions explicitly; do not strip them |
| Missing house number | 3 | Recover address from additional original evidence |
| Street-name/alias gap | 3 | Review the name against official alias records |

The 74 candidates are recorded in `possible_recoveries.csv`; none is promoted into
the production match count. The other 32 need more address evidence. Diagnostic
categories are mutually exclusive triage labels, not confirmed root causes.

## Method and sources

The sample is a simple random sample without replacement from the 1,922 frozen
matched violations, sorted by ticket number before sampling, seed **20260819**.
The same diagnostic was also run across all 2,028 eligible records. All 100 sample
map panels and five hold-record panels were visually inspected using retained
reference geometry. This is desk review of the same evidence, not independent
street-level verification.

The audit joins exact normalized house/street text to AddressPoint, preserving
letter suffixes and excluding explicitly proposed, permitted, under-construction
and retired points. Unknown status is retained and recorded. Address ranges are
not expanded. Segments are constructed streets with matching full/display street
names; bare street-name components are not used for the spatial test.

Coordinates are projected from longitude/latitude to **EPSG:2263 (US survey feet)**.
A point supports a segment only when the nearest same-street segment is within
150 feet, at least 20 feet nearer than its runner-up, and its projected position
is at least 20 feet along the line from either endpoint. Multiple exact points
must agree. These thresholds are conservative audit heuristics, not calibrated
accuracy cutoffs. The sample has 94 corroborations with a 100- or 200-foot cap;
changing the runner-up margin to 10 feet gives 95, and to 30 feet gives 90.
Full-population sensitivity results are in the verification JSON.

Source extracts are current-reference evidence, not historical truth:

- [AddressPoint table](https://data.cityofnewyork.us/d/uf93-f8nk): 63,245 Manhattan points; source rows updated July 7, 2026.
- [Centerline table](https://data.cityofnewyork.us/d/inkn-q76z): 14,107 Manhattan rows; source rows updated September 19, 2026.
- [Official AddressPoint definitions](https://github.com/CityOfNewYork/nyc-geo-metadata/blob/main/Metadata/Metadata_AddressPoint.md) explain point placement within building frontage and common lineage.
- [Official GIS field domains](https://services6.arcgis.com/yG5s3afENB5iO9fj/arcgis/rest/services/AddressPoint_view/FeatureServer/0?f=pjson) define Field validation, address status, and source codes.
- [SweepNYC metadata](https://data.cityofnewyork.us/d/c23c-uwsm) defines `cscl_version` as the reference used to generate IDs and records one GPS-associated observation per segment/day. It is not a measure of litter removed.

The source manifest stores exact queries, timestamps and SHA-256 hashes. July
address-point coverage may miss later changes; absence is treated as unverified.

## Historical 23C search outcome

No exact 23C release was located in the targeted NYC Open Data and official GIS
catalog checks. The available CSCL geodatabase is current; `CSCL_PlowNYC` is explicitly
for winter 2016/17 and was rejected as a substitute. A separately indexed archived
basemap was also not treated as a version-aligned centerline table. The legacy CSCL
endpoint returns 404 and the legacy planning/SweepNYC pages returned 403 to direct
fetches. This is an access/search outcome, not proof that an archive does not exist.

[The prepared data request](cscl-23c-data-request.md) specifies the needed release
and split/merge crosswalk. It has not been sent. Exact historical alignment remains
a release gate for an accuracy claim.

## Review coverage

Inventory: four evidence components—baseline counts, sample corroboration,
unresolved-record review, and version reconciliation. Three intended questions—
match correctness, unresolved cases, and historical alignment. Totals below are
scoped inventory counts, not claims of complete verification. A zero observed-defect
count does not turn missing independent evidence into a pass.

### Report quality and completeness

| Category | Observed defects | Assessment |
| --- | --- | --- |
| Usefulness/completeness | 2 / 3 | Independent correctness and historical alignment remain incomplete; unresolved-case triage is complete. |
| Analytical clarity | 0 / 4 | Coverage, corroboration and accuracy are distinguished. |
| Visual/interaction consistency | 0 / 6 | Five sample sheets and one hold sheet inspected; no interactive dashboard. |

### Analytical correctness and robustness

| Category | Observed defects | Assessment |
| --- | --- | --- |
| Source authority/confidence | 0 / 4 | Official sources; shared lineage and unavailable 23C evidence disclosed. |
| Value accuracy | 0 / 4 | Independent raw-record recount agrees; audit partitions reconcile. |
| Within-chart agreement | 0 / 6 | Diagnostic maps agree with retained points/segments and labels. |
| Complete source details | 0 / 4 | Queries/checksums retained; unavailable historical source explicitly named. |
| Cross-artifact consistency | 0 / 4 | Report, summaries and row-level evidence reconcile. |
| Data-quality controls | 0 / 4 | Suffixes, retired points, candidate ambiguity and reference absence tested; known issues remain held. |
| Conclusion support | 0 / 4 | No claim of measured accuracy or cleaning effectiveness. |

## Reproduce

Use the repository environment with its existing requirements installed:

```powershell
$env:PYTHONPATH = "src"
.venv/Scripts/python.exe -m pytest -q
# Requires the frozen original pilot inputs and matches.csv.
.venv/Scripts/python.exe scripts/fetch_validation_sources.py
.venv/Scripts/python.exe scripts/run_validation_audit.py
.venv/Scripts/python.exe scripts/render_validation_maps.py
.venv/Scripts/python.exe scripts/verify_validation.py
```

To reproduce this exact audit, restore the delivered archive and skip the fetch
step. The runner checks source checksums before using retained extracts. New live
reference data may change results. Read `assignment_holds.csv`, `sample_100.csv`,
`unresolved_106.csv`, the evidence JSON, and the map sheets together.

The next decision is to obtain the exact 23C reference and independently adjudicate
the flagged addresses. Building a before/after effectiveness analysis before those
checks would treat an unvalidated linkage as ground truth.
