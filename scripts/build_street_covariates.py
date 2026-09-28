"""Design-gap fix #1: real street-type covariates for the 851-segment population.

Phase 1/2's original CSCL extract (data/raw/pilot/cscl.json) only pulled address-range
fields needed for matching (house numbers, street names) -- it has no street-type
information at all. This script uses a separate, fuller extract of the same CSCL
table (inkn-q76z) pulled via the browser-fetch technique
(data/raw/phase2/cscl_covariates.json, see data/raw/phase2/design_gap_manifest.json)
that includes genuine street-type fields: width, lane counts, one-way/two-way,
snow-plow priority (used here as a functional-class proxy, since `fcc` is null for
every Manhattan row in this extract), and truck-route designation.

Output: data/processed/effect_analysis/segment_covariates.csv, one row per
physical_id in the Phase 1/2 population (851 segments), with:
  - streetwidth_ft (float, roadbed width)
  - travel_lanes, park_lanes, total_lanes (int)
  - one_way (1 if trafdir is FT/TF, 0 if TW -- two-way)
  - snow_priority (H = major/highway, C = collector/local, S = secondary)
  - truck_route (1 if truck_route_type is set, else 0)

6 of 851 segments have no covariate record in the CSCL extract (likely renumbered
IDs, the same class of gap LION-gap-resolution-2026-09.md found for a different
purpose) and are dropped with a note in the summary rather than imputed.
"""
import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PROCESSED_ADJ = ROOT / "data/processed/adjudication"
RAW_PHASE2 = ROOT / "data/raw/phase2"
OUT = ROOT / "data/processed/effect_analysis"


def main():
    OUT.mkdir(parents=True, exist_ok=True)

    matches = list(csv.DictReader((PROCESSED_ADJ / "reviewed_matches.csv").open(encoding="utf-8")))
    segments = sorted({r["reviewed_physical_id"] for r in matches if r["reviewed_physical_id"]})

    cscl = {r["physicalid"]: r for r in json.loads((RAW_PHASE2 / "cscl_covariates.json").read_text())}

    rows = []
    missing = []
    for pid in segments:
        rec = cscl.get(pid)
        if rec is None:
            missing.append(pid)
            continue
        trafdir = rec.get("trafdir")
        width = rec.get("streetwidth")
        travel = rec.get("number_travel_lanes")
        park = rec.get("number_park_lanes")
        total = rec.get("number_total_lanes")
        if not (width and travel):
            missing.append(pid)
            continue
        rows.append({
            "physical_id": pid,
            "streetwidth_ft": float(width),
            "travel_lanes": int(travel),
            "park_lanes": int(park) if park not in (None, "") else None,
            "total_lanes": int(total) if total not in (None, "") else None,
            "one_way": 0 if trafdir == "TW" else 1,
            "trafdir": trafdir,
            "snow_priority": rec.get("snow_priority"),
            "truck_route": 1 if rec.get("truck_route_type") else 0,
        })

    fieldnames = list(rows[0])
    out_csv = OUT / "segment_covariates.csv"
    with out_csv.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    summary = {
        "population_segments": len(segments),
        "segments_with_covariates": len(rows),
        "segments_missing_covariates": len(missing),
        "missing_physical_ids": missing,
        "source": "data/raw/phase2/cscl_covariates.json (full CSCL table extract, inkn-q76z)",
        "note": (
            "fcc (standard functional-classification field) is null for every "
            "Manhattan row in this extract, so snow_priority (H=highway/major, "
            "C=collector/local, S=secondary -- DSNY's snow-plow priority tier) is "
            "used as the functional-class proxy instead."
        ),
    }
    (OUT / "segment_covariates_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
