"""Match Phase 2's fetched 311 complaints to the 851-segment Phase 1 population.

Reuses `sweepnyc.matching`'s street-normalization and house-number-range
logic (the same approach validated in Phase 1 for OATH violations), adapted
for 311's schema: 311 gives `incident_address` as a single combined
"<house number> <street name>" string plus a separate `street_name` field,
unlike OATH's separate `violation_location_house` field. The house number is
recovered here by stripping the trailing `street_name` off `incident_address`.

Population restriction: only the 851 PhysicalIDs already in
`reviewed_matches.csv` (the Phase 1/segment-analysis population) are
considered candidates. A 311 complaint whose address falls on some other
Manhattan segment is out of scope for this project and marked
`out_of_population`, not `unmatched` -- these are different things and are
reported separately.
"""
import csv
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from sweepnyc.matching import (  # noqa: E402
    candidate_street_names,
    house_number_key,
    normalize_street,
    _same_shape_between,
    _parity_match,
)

RAW_PILOT = ROOT / "data/raw/pilot"
RAW_PHASE2 = ROOT / "data/raw/phase2"
PROCESSED_ADJ = ROOT / "data/processed/adjudication"
OUT = ROOT / "data/processed/effect_analysis"


def load_population_ids() -> set[str]:
    rows = list(csv.DictReader((PROCESSED_ADJ / "reviewed_matches.csv").open(encoding="utf-8")))
    return {r["reviewed_physical_id"] for r in rows if r["reviewed_physical_id"]}


def house_number_from_address(incident_address: str, street_name: str) -> str | None:
    """Strip the trailing street_name off incident_address to recover the house number."""
    if not incident_address or not street_name:
        return None
    addr = incident_address.strip().upper()
    street = street_name.strip().upper()
    if addr.endswith(street):
        house = addr[: -len(street)].strip()
        return house or None
    # Fallback: take the leading numeric/alphanumeric token.
    parts = addr.split(" ", 1)
    return parts[0] if parts else None


def build_street_index(cscl_rows: list[dict]) -> dict[str, list[dict]]:
    """Precompute street-name -> CSCL rows so matching is O(1) lookups, not an O(n*m) scan."""
    index: dict[str, list[dict]] = {}
    for row in cscl_rows:
        for name in candidate_street_names(row):
            index.setdefault(name, []).append(row)
    return index


def match_311_to_cscl(rec: dict, street_index: dict[str, list[dict]], population_ids: set[str]) -> dict:
    street = normalize_street(rec.get("street_name"))
    house = house_number_key(house_number_from_address(rec.get("incident_address", ""), rec.get("street_name", "")))
    zipcode = str(rec.get("incident_zip") or "").strip()

    result = {
        "unique_key": rec.get("unique_key"),
        "physical_id": None,
        "quality": "unmatched",
        "method": "missing_address",
        "candidate_count": 0,
    }
    if not street or house is None:
        return result

    name_matches = street_index.get(street, [])
    if zipcode:
        zip_matches = [
            r for r in name_matches
            if zipcode in {str(r.get("l_zip") or "").strip(), str(r.get("r_zip") or "").strip()}
        ]
        if zip_matches:
            name_matches = zip_matches

    ranged = []
    for row in name_matches:
        left_low = house_number_key(row.get("l_low_hn"))
        left_high = house_number_key(row.get("l_high_hn"))
        right_low = house_number_key(row.get("r_low_hn"))
        right_high = house_number_key(row.get("r_high_hn"))

        left_ok = _same_shape_between(house, left_low, left_high) and _parity_match(house, left_low, left_high)
        right_ok = _same_shape_between(house, right_low, right_high) and _parity_match(house, right_low, right_high)
        if left_ok or right_ok:
            ranged.append(row)

    physical_ids = sorted({str(r.get("physicalid")) for r in ranged if r.get("physicalid") is not None})
    if len(physical_ids) == 1:
        result["candidate_count"] = 1
        result["method"] = "street_house_range"
        pid = physical_ids[0]
        if pid in population_ids:
            result["physical_id"] = pid
            result["quality"] = "exact"
        else:
            result["quality"] = "out_of_population"
            result["physical_id"] = pid
        return result
    if len(physical_ids) > 1:
        result["quality"] = "ambiguous"
        result["method"] = "multiple_house_range_segments"
        result["candidate_count"] = len(physical_ids)
        return result

    name_ids = sorted({str(r.get("physicalid")) for r in name_matches if r.get("physicalid") is not None})
    if len(name_ids) == 1:
        result["method"] = "street_match_no_house_range"
        result["candidate_count"] = 1
        return result
    if len(name_ids) > 1:
        result["quality"] = "ambiguous"
        result["method"] = "street_match_no_house_range"
        result["candidate_count"] = len(name_ids)
        return result
    result["method"] = "no_street_match"
    return result


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    cscl_rows = json.loads((RAW_PILOT / "cscl.json").read_text())
    records = json.loads((RAW_PHASE2 / "311_manhattan_august.json").read_text())
    population_ids = load_population_ids()
    street_index = build_street_index(cscl_rows)

    results = [match_311_to_cscl(r, street_index, population_ids) for r in records]

    quality_counts = Counter(r["quality"] for r in results)
    in_population = [r for r in results if r["quality"] == "exact"]

    print(f"Total 311 records: {len(records)}")
    print(f"Quality breakdown: {dict(quality_counts)}")
    print(f"Matched to a Phase-1-population segment: {len(in_population)}")

    # Merge unique_key -> physical_id/date back onto original records for the panel join.
    by_key = {r["unique_key"]: r for r in records}
    joined = []
    for m in in_population:
        rec = by_key[m["unique_key"]]
        joined.append({
            "unique_key": m["unique_key"],
            "physical_id": m["physical_id"],
            "date": rec["created_date"][:10],
            "complaint_type": rec["complaint_type"],
        })

    out_path = OUT / "matched_311.json"
    out_path.write_text(json.dumps(joined, indent=2))
    print(f"Wrote {len(joined)} matched 311 records -> {out_path}")

    summary = {
        "total_311_fetched": len(records),
        "quality_breakdown": dict(quality_counts),
        "matched_to_population": len(in_population),
        "segments_with_311_hit": len({m["physical_id"] for m in in_population}),
    }
    (OUT / "matched_311_summary.json").write_text(json.dumps(summary, indent=2))
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
