# Manhattan August 2026 linkage pilot: observed results

Extracted 2026-09-19T16:00:28.605622+00:00. Full Manhattan month, not a random subsample.

**OATH to CSCL assignment coverage: 1,922 / 2,028 = 94.77%.**
This exceeds the project's 80% coverage threshold. It does not establish match precision or street-sweeping effectiveness.

| Measure | Observed count |
| --- | ---: |
| Manhattan OATH records in August | 5,793 |
| Eligible cleanliness records | 2,028 |
| Exact numeric street/range matches | 1,918 |
| High-confidence matches with ignored house-letter suffix | 4 |
| Ambiguous | 99 |
| Unmatched | 7 |
| Unique matched CSCL segments | 850 |
| Matched records with an August SweepNYC visit | 1,492 |
| Unique matched segments with an August visit | 659 |
| Manhattan CSCL reference rows | 14,106 |
| Citywide August SweepNYC visit rows | 464,418 |
| Citywide unique visited PHYSICALIDs | 38,627 |
| Duplicate OATH ticket rows | 0 |

**OATH to observed SweepNYC overlap: 1,492 / 2,028 = 73.57%** of all eligible records;
1,492 / 1,922 = 77.63% of CSCL-matched records.
The 80% decision rule applies to CSCL assignment coverage, not observed sweep overlap.

## Failure audit

52 records have multiple qualifying house-range segments; 47 have multiple street candidates but no qualifying house range.
Of seven unmatched records, three lack usable house numbers, three have no normalized street match, and one has a single street candidate but no qualifying range.
No street-only fallback is counted as confident.

## Sources and reproducibility

- OATH: https://data.cityofnewyork.us/d/r78k-82m3
- CSCL underlying table: https://data.cityofnewyork.us/d/inkn-q76z (the original 3mf9-qshr ID is a map).
- SweepNYC: https://data.cityofnewyork.us/d/c23c-uwsm

The committed `pilot-summary-2026-08.json` contains exact queries, extract counts,
source update timestamps, and SHA-256 checksums. Raw snapshots and row-level results
remain local and are included in the delivered reproducibility archive.
Run `python scripts/run_match_pilot.py` to refresh from live sources or append
`--replay` to use local snapshots, validating query parameters and checksums.
Live data revisions can change the result. Python 3.12.14 was used; exact installed
package versions are in `requirements-observed.txt`.

Validation: 15 tests passed; modules compile; a second offline replay reproduced
all result metrics and byte-identical matches/description CSV files.

## Interpretation limits

SweepNYC reports CSCL version 23C while the reference table is current. No historical
version crosswalk or manual address truth-set review was performed. `Exact` denotes
a unique algorithmic range assignment, not verified precision. House-letter suffixes
are ignored and labeled high-confidence; ZIP is a soft narrowing hint.
A monthly sweep visit can precede or follow a violation. No recorded visit is not
proof of no cleaning. Eligible categories include sidewalks and property areas as
well as the 18-inch curb strip. These results validate coverage only; they do not
measure whether sweeping works.

## Repairs made

Fixed the matcher syntax error; directional, ordinal, avenue-prefix and square
normalization; CSCL table/column mapping; reversed ranges; and unsafe street-only
assignments. Added indexed matching, ordered pagination, all ten charge-description
fields, null rates for empty samples, separate record/segment metrics, snapshots,
checksums and offline replay. CI now uses read-only pull-request permissions instead
of executing PR code under pull_request_target.
