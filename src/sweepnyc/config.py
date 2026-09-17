"""Project-wide source configuration."""

SOCRATA_DOMAIN = "data.cityofnewyork.us"

DATASETS = {
    "sweepnyc": "c23c-uwsm",
    "oath": "r78k-82m3",
    "cscl": "3mf9-qshr",
    "address_points": "6xyb-j5pk",
}

# A project decision for the Phase 1 go/no-go pilot.
MIN_ACCEPTABLE_MATCH_RATE = 0.80
