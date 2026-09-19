"""Run the first Manhattan OATH -> CSCL/SweepNYC linkage pilot.\n\nThis script is intentionally a linkage-validation experiment, not an effectiveness analysis.

Default pilot:
- Borough: Manhattan
- Period: August 2026
- Outcomes: narrowly selected street-cleanliness violation descriptions

Outputs are written to data/processed/pilot/.
"""

from __future__ import annotations

import csv
import json
import os
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from sweepnyc.config import DATASETS, MIN_ACCEPTABLE_MATCH_RATE  # noqa: E402
from sweepnyc.matching import match_oath_to_cscl  # noqa: E402
from sweepnyc.socrata import fetch_rows  # noqa: E402

START = os.getenv("PILOT_START", "2026-08-01T00:00:00")
END = os.getenv("PILOT_END", "2026-09-01T00:00:00")
BOROUGH = os.getenv("PILOT_BOROUGH", "MANHATTAN")
OUTDIR = ROOT / "data" / "processed" / "pilot"

CLEANLINESS_TERMS = (
    "DIRTY SIDEWALK",
    "DIRTY AREA",
    "18 INCH",
    "18"",
    "EIGHTEEN INCH",
)

OATH_SELECT = ",".join(
    [
        "ticket_number",
        "violation_date",
        "violation_time",
        "issuing_agency",
        "violation_location_borough",
        "violation_location_block_no",
        "violation_location_lot_no",
        "violation_location_house",
        "violation_location_street_name",
        "violation_location_zip_code",
        "violation_description",
        "charge_1_code",
        "charge_1_code_description",
        "charge_2_code",
        "charge_2_code_description",
        "charge_3_code",
        "charge_3_code_description",
    ]
)

CSCL_SELECT = ",".join(
    [
        "physicalid",
        "l_low_hn",
        "l_high_hn",
        "r_low_hn",
        "r_high_hn",
        "l_zip",
        "r_zip",
        "borocode",
        "full_stree",
        "st_name",
        "st_label",
    ]
)


def fetch_all(dataset_id: str, *, where: str, select: str, page_size: int = 50000) -> list[dict]:
    rows: list[dict] = []
    offset = 0
    while True:
        page = fetch_rows(
            dataset_id,
            limit=page_size,
            offset=offset,
            where=where,
            select=select,
        )
        rows.extend(page)
        if len(page) < page_size:
            break
        offset += page_size
    return rows


def cleanliness_text(row: dict) -> str:
    pieces = [
        row.get("violation_description"),
        row.get("charge_1_code_description"),
        row.get("charge_2_code_description"),
        row.get("charge_3_code_description"),
    ]
    return " | ".join(str(x or "").upper() for x in pieces)


def is_cleanliness_candidate(row: dict) -> bool:
    text = cleanliness_text(row)
    return any(term in text for term in CLEANLINESS_TERMS)


def main() -> int:
    OUTDIR.mkdir(parents=True, exist_ok=True)

    oath_where = (
        f"violation_location_borough='{BOROUGH}' "
        f"AND violation_date >= '{START}' AND violation_date < '{END}'"
    )
    oath_all = fetch_all(DATASETS["oath"], where=oath_where, select=OATH_SELECT)
    candidates = [r for r in oath_all if is_cleanliness_candidate(r)]

    # Manhattan CSCL rows only.
    cscl = fetch_all(
        DATASETS["cscl"],
        where="borocode='1'",
        select=CSCL_SELECT,
    )

    sweep = fetch_all(
        DATASETS["sweepnyc"],
        where=f"date_visited >= '{START}' AND date_visited < '{END}'",
        select="physical_id,date_visited",
    )
    swept_ids = {str(r["physical_id"]) for r in sweep if r.get("physical_id") is not None}

    results = []
    quality_counts = Counter()
    method_counts = Counter()

    for row in candidates:
        match = match_oath_to_cscl(row, cscl)
        quality_counts[match.quality] += 1
        method_counts[match.method] += 1
        results.append(
            {
                **row,
                "matched_physical_id": match.physical_id or "",
                "match_quality": match.quality,
                "match_method": match.method,
                "candidate_count": match.candidate_count,
                "swept_during_pilot_month": bool(match.physical_id and match.physical_id in swept_ids),
            }
        )

    eligible = len(candidates)
    confident = quality_counts["exact"] + quality_counts["high_confidence"]
    match_rate = confident / eligible if eligible else 0.0
    exact_rate = quality_counts["exact"] / eligible if eligible else 0.0

    summary = {
        "generated_at_utc": datetime.utcnow().isoformat() + "Z",
        "pilot_start": START,
        "pilot_end": END,
        "borough": BOROUGH,
        "oath_rows_in_period": len(oath_all),
        "cleanliness_candidate_rows": eligible,
        "cscl_rows": len(cscl),
        "sweepnyc_rows_in_period": len(sweep),
        "unique_swept_physical_ids": len(swept_ids),
        "quality_counts": dict(quality_counts),
        "method_counts": dict(method_counts),
        "exact_rate": exact_rate,
        "confident_match_rate": match_rate,
        "threshold": MIN_ACCEPTABLE_MATCH_RATE,
        "passes_threshold": match_rate >= MIN_ACCEPTABLE_MATCH_RATE,
        "matched_segments_swept_in_period": sum(
            1 for r in results if r["matched_physical_id"] and r["swept_during_pilot_month"]
        ),
    }

    (OUTDIR / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")

    fieldnames = sorted({k for row in results for k in row}) if results else [
        "ticket_number",
        "match_quality",
        "match_method",
        "matched_physical_id",
    ]
    with (OUTDIR / "matches.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(results)

    # Also save the observed descriptions so category selection can be audited.
    descriptions = Counter(cleanliness_text(r) for r in candidates)
    with (OUTDIR / "candidate_descriptions.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["count", "description"])
        for desc, count in descriptions.most_common():
            writer.writerow([count, desc])

    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
