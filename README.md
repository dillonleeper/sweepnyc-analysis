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
| NYC Street Centerline (CSCL) | Street-segment geometry and `PHYSICALID` | `3mf9-qshr` |
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
