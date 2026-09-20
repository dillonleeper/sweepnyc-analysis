# SweepNYC Analysis

## Does street sweeping actually work?

This project investigates whether documented NYC mechanical street-sweeping events are associated with measurable improvements in street-cleanliness indicators.

The core idea is to treat each recorded sweeper traversal as an observed intervention, then compare subsequent cleanliness signals on the same street segment and against appropriate comparison segments.

## Current status

**Phase 1: data-linkage validation**

Before doing any effectiveness analysis, the project needs to answer one basic question:

> Can NYC sanitation violations be reliably assigned to the same CSCL street segments used by SweepNYC?

The initial go/no-go target is **at least 80% high-confidence matches** for the pilot sample. The threshold is a project decision, not a claim about the data.

## Primary data sources

| Source | Role | NYC Open Data ID |
| --- | --- | --- |
| SweepNYC Street Cleaning | Treatment: documented mechanical-sweeper visits by street segment/day | `c23c-uwsm` |
| DSNY Sanitation OATH Database | Enforcement-observed sanitation conditions | `r78k-82m3` |
| NYC Street Centerline (CSCL) | Street-segment geometry and `PHYSICALID` | `inkn-q76z` (table; map: `3mf9-qshr`) |
| NYC Address Points | Address/location bridge to street segments | `6xyb-j5pk` |
| 311 Service Requests | Citizen-reported cleanliness signal | added after Phase 1 |

## Research questions

1. Does the rate of relevant sanitation complaints or violations change after a documented sweeper visit?
2. If an effect exists, how long does it persist?
3. Does effectiveness vary by neighborhood, street type, cleaning frequency, weather, or other contextual factors?
4. Are some streets repeatedly dirty soon after cleaning?

## Important limitation

A 311 complaint or OATH violation is **not a direct measurement of litter volume**.

- 311 reflects both street conditions and resident reporting behavior.
- OATH reflects both street conditions and enforcement activity.
- Mechanical sweeping primarily cleans the roadway/curb area, while some sanitation violations concern adjacent sidewalks or property responsibilities.

The project will therefore keep separate outcome signals rather than treating any one of them as ground truth.

## Planned analysis

```text
SweepNYC cleaning event
        |
        +--> OATH sanitation violations
        |
        +--> 311 dirty-condition complaints
        |
        +--> contextual controls
                 |
                 v
      street-segment event panel
                 |
        +--------+--------+
        |                 |
   event study      matched controls /
                    difference-in-differences
```

## Repository structure

```text
sweepnyc-analysis/
├── data/                  # local data only; raw extracts are not committed
├── docs/
│   └── methodology.md
├── scripts/
│   └── inspect_sources.py
├── src/
│   └── sweepnyc/
│       ├── __init__.py
│       ├── config.py
│       └── socrata.py
├── requirements.txt
└── README.md
```

## Phase 1 acceptance criteria

The first pilot should use one Manhattan area and one recent complete month.

For relevant OATH sanitation records, report:

- total candidate records;
- exact/high-confidence segment matches;
- ambiguous matches;
- unmatched records;
- match rate;
- reasons for failure.

No causal conclusions should be drawn until this linkage is validated.

## Setup

```bash
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python scripts/inspect_sources.py
```

## License

MIT.

## Run the Manhattan pilot

```powershell
.venv/Scripts/python.exe -m pip install -r requirements.txt pytest
$env:PYTHONPATH = "src"
.venv/Scripts/python.exe -m pytest -q
.venv/Scripts/python.exe scripts/run_match_pilot.py
# Reproduce matching from the saved, checksummed extracts without network access:
.venv/Scripts/python.exe scripts/run_match_pilot.py --replay
```

On other platforms, use `python` in the activated environment and `PYTHONPATH=src` for tests.
The default interval is August 1 inclusive through September 1 exclusive, 2026.
`PILOT_START` and `PILOT_END` override it; only Manhattan is supported currently.
An empty eligible sample produces a null rate and no threshold decision, not a 0% rate.

Raw extracts, source schemas, and a query/checksum manifest are saved in
`data/raw/pilot/`. Results and their manifest are saved in `data/processed/pilot/`.
These directories are ignored by Git. Aggregate observed results are recorded in
[the pilot report](docs/pilot-results-2026-08.md). `requirements-observed.txt`
records the exact installed Windows/Python 3.12 environment; use the general
requirements file on other platforms (the snapshot includes Windows-only packages).
Live sources can change; use the saved extracts for exact reproduction.

## Validation milestone

The [September 2026 validation report](docs/validation-report-2026-08.md) audits
100 sampled matches, all four suffixed matches, and all 106 unresolved violations.
It also checks the entire matched population against saved address points.
94/100 sample records are spatially corroborated; this is **not measured accuracy**.
Three records have conflicting spatial evidence and two use an ID missing from the
refreshed reference. Historical CSCL 23C alignment remains unresolved.

The [follow-up case review](docs/case-review-2026-08.md) locates official LION 23C,
checks five violations against parcels, buildings, and the public SweepNYC lookup,
and records three corrected assignments in a separate reviewed output. Coverage
and August sweep overlap are unchanged. LION covers 846/850 matched IDs; the exact
DSNY CSCL snapshot and eight violations on four absent IDs remain unverified.

Run `scripts/fetch_validation_sources.py` once to save current reference evidence,
then `scripts/run_validation_audit.py` and `scripts/render_validation_maps.py`.
Audit results live under `data/processed/validation/`; raw sources under
`data/raw/validation/`. The original pilot snapshot is retained. Candidate recoveries
are review suggestions and never silently alter the original match rate.
