# Manhattan August 2026: historical map and five case reviews

Three violations at 541/545 West 125th Street have sufficient corroborating evidence to use segment **117672** in a separate reviewed output, replacing the range match to 19407. Two violations at 13 East 27th Street retain **81213**. These are case-specific analyst decisions, not a new global matching rule.

The reviewed pilot still has **1,922/2,028 matched violations (94.77%)** and **1,492/2,028 with an August sweep record (73.57%; 77.63% of matched records)**. Changing three assignments does not change these totals. Original outputs and classifications remain intact; `reviewed_matches.csv` adds reviewed IDs and overlap flags.

## Evidence and decisions

| Address | Tickets | Original ID | Reviewed ID | Evidence |
|---|---|---|---|---|
| 541 West 125 Street | 049853638J | 19407 | 117672 | Address point inside ticket's tax lot and building; historical geometry is 57.8 feet away versus 103.8 for original ID; public SweepNYC lookup returns 117672 |
| 545 West 125 Street | 049886175N, 049918725M | 19407 | 117672 | Address point inside ticket's tax lot and building; historical geometry is 56.25 feet away versus 155.22 for original ID; public SweepNYC lookup returns 117672 |
| 13 East 27 Street | 049909531J, 049909538M | 81213 | 81213 | Address point inside ticket's tax lot and building; ID exists in 23C LION and public SweepNYC lookup still returns it |

The OATH block and lot agree with DOF tax-lot identifiers and building footprint base BBLs for all five records. This is a separate property check on the previously used address-point location. It is not independent field inspection. PLUTO lists 543 West 125 Street as the primary address for the parcel containing 545, and 10 East 28 Street for the parcel containing 13 East 27; a parcel's primary address alone does not establish or refute a secondary frontage address.

## Historical archive: substantial progress, limited scope

The official **LION 23C** archive is available using the download pattern in [NYC Planning's ingestion configuration](https://github.com/NYCPlanning/data-engineering/blob/main/ingest_templates/dcp_lion.yml): [download 23C](https://s-media.nyc.gov/agencies/dcp/assets/files/zip/data-tools/bytes/lion/nyclion_23c.zip). It is a historical street network with PhysicalID fields, **not proof of the exact CSCL 23C file used by DSNY**.

846 of the pilot's 850 distinct matched IDs appear in this archive. Four IDs affecting eight violations do not: 204036 (1), 206391 (5), 206394 (1), and 206507 (1). ID presence verifies namespace coverage only, not address accuracy or equivalent geometry. No automatic replacement is made for these eight violations.

LION contains alias rows and multiple component segments for a PhysicalID. The replay script unions their geometry before calculating distances in EPSG:2263 feet. It does not count alias rows as separate matches. The original 81213 exists in 23C; the modern reference's replacement ID is unnecessary for this historical case.

## Sources and remaining limits

Property evidence comes from [DOF tax lots](https://data.cityofnewyork.us/resource/i38t-6if2.json), [NYC building footprints](https://data.cityofnewyork.us/resource/5zhs-2jue.json), and [PLUTO](https://data.cityofnewyork.us/resource/64uk-42ks.json). Current operational IDs come from the public lookup used by [SweepNYC](https://sweepnyc.nyc.gov/). Saved responses include their exact request URLs. Live lookup visit times are **not** used to infer August service: overlap is recalculated exclusively from the frozen August extract.

Exact DSNY CSCL 23C alignment remains open. This review does not resolve the earlier sample's boundary ambiguities, missing letter-suffixed addresses, or all unmatched cases. Neither 94.77% coverage nor the earlier 94/100 spatial corroboration is a measured accuracy rate. No agency request has been sent.

## Reproduction

Install the repository requirements. To refresh public case evidence, run `python scripts/fetch_case_sources.py`; source URLs, retrieval times, and hashes are saved. For exact replay, restore the supplied raw snapshots and original pilot files, then run:

```text
python scripts/fetch_case_sources.py --replay
python scripts/adjudicate_cases.py
```

The first command safely extracts the saved archive without network access. The second checks ticket/parcel/building identifiers, calculates historical distances, and writes reviewed matches, summary, and input checksums to `data/processed/adjudication/`. Source changes can alter a fresh run; preserve the checksummed bundle for the observed result.
