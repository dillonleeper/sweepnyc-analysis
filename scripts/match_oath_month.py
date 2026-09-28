"""Match a month's fetched OATH violations to the 851-segment population.

This is the automated-only counterpart to Phase 1's reviewed_matches.csv:
August's OATH matches went through a full manual adjudication pass
(case-review, LION-gap resolution, spatial corroboration -- see
docs/segment-analysis-2026-08.md and friends). A newly fetched month has NOT
been through that review, so this script uses `match_oath_to_cscl` alone
(the same automated first pass Phase 1 started from) and keeps only
"exact"/"high_confidence" quality matches, restricted to physical_ids
already in the 851-segment population. Ambiguous and unmatched records are
dropped, the same way Phase 1's initial automated pass did before review.

This is a known, documented limitation of extending beyond August: additional
months' OATH counts have NOT been through the same human review as August's,
so a like-for-like comparison should treat August as higher-confidence.

The fetched field set for extra months is smaller than Phase 1's original
OATH_SELECT: only charge_1_code_description is available (fields
charge_2..10 and violation_description were confirmed empty for every August
record, so the cleanliness-candidate filter only ever depended on charge_1
in practice -- see docs/phase2-effect-analysis-2026-09.md).
"""
import argparse
import csv
import json
from collections import Counter
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from sweepnyc.matching import match_oath_to_cscl, candidate_street_names, normalize_street  # noqa: E402

RAW_PILOT = ROOT / "data/raw/pilot"
PROCESSED_ADJ = ROOT / "data/processed/adjudication"

CLEANLINESS_TERMS = (
    "DIRTY SIDEWALK",
    "DIRTY AREA",
    "18 INCH",
    '18"',
    "EIGHTEEN INCH",
)


def is_cleanliness_candidate(row: dict) -> bool:
    text = str(row.get("charge_1_code_description") or "").upper()
    return any(term in text for term in CLEANLINESS_TERMS)


def load_population_ids() -> set[str]:
    rows = list(csv.DictReader((PROCESSED_ADJ / "reviewed_matches.csv").open(encoding="utf-8")))
    return {r["reviewed_physical_id"] for r in rows if r["reviewed_physical_id"]}


def build_street_index(cscl_rows: list[dict]) -> dict[str, list[dict]]:
    index: dict[str, list[dict]] = {}
    for row in cscl_rows:
        for name in candidate_street_names(row):
            index.setdefault(name, []).append(row)
    return index


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--summary-output", required=True)
    args = parser.parse_args()

    cscl_rows = json.loads((RAW_PILOT / "cscl.json").read_text())
    oath_all = json.loads(Path(args.input).read_text())
    population_ids = load_population_ids()
    street_index = build_street_index(cscl_rows)

    candidates = [r for r in oath_all if is_cleanliness_candidate(r)]

    quality_counts = Counter()
    in_population = []
    for row in candidates:
        street = normalize_street(row.get("violation_location_street_name"))
        match = match_oath_to_cscl(row, street_index.get(street, []))
        quality_counts[match.quality] += 1
        if match.quality in ("exact", "high_confidence") and match.physical_id in population_ids:
            in_population.append({
                "ticket_number": row["ticket_number"],
                "physical_id": match.physical_id,
                "date": row["violation_date"][:10],
            })
        elif match.quality in ("exact", "high_confidence"):
            quality_counts["matched_but_out_of_population"] += 1

    print(f"OATH rows in month: {len(oath_all)}")
    print(f"Cleanliness candidates: {len(candidates)}")
    print(f"Quality breakdown (candidates): {dict(quality_counts)}")
    print(f"Matched to population: {len(in_population)}")

    Path(args.output).write_text(json.dumps(in_population, indent=2))

    summary = {
        "input": args.input,
        "oath_rows_in_month": len(oath_all),
        "cleanliness_candidate_rows": len(candidates),
        "quality_breakdown": dict(quality_counts),
        "matched_to_population": len(in_population),
        "segments_with_hit": len({r["physical_id"] for r in in_population}),
        "note": "Automated match_oath_to_cscl only -- NOT manually reviewed like August's reviewed_matches.csv.",
    }
    Path(args.summary_output).write_text(json.dumps(summary, indent=2))
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
