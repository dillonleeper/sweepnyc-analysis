"""Run the first Manhattan OATH -> CSCL/SweepNYC linkage pilot.\n\nThis script is intentionally a linkage-validation experiment, not an effectiveness analysis.

Default pilot:
- Borough: Manhattan
- Period: August 2026
- Outcomes: narrowly selected street-cleanliness violation descriptions

Outputs are written to data/processed/pilot/.
"""

from __future__ import annotations

import argparse
import hashlib
import platform
import csv
import json
import os
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from sweepnyc.config import DATASETS, MIN_ACCEPTABLE_MATCH_RATE  # noqa: E402
from sweepnyc.matching import match_oath_to_cscl, candidate_street_names, normalize_street  # noqa: E402
from sweepnyc.socrata import fetch_rows, metadata  # noqa: E402

START = os.getenv("PILOT_START", "2026-08-01T00:00:00")
END = os.getenv("PILOT_END", "2026-09-01T00:00:00")
BOROUGH = os.getenv("PILOT_BOROUGH", "MANHATTAN")
OUTDIR = ROOT / "data" / "processed" / "pilot"

CLEANLINESS_TERMS = (
    "DIRTY SIDEWALK",
    "DIRTY AREA",
    "18 INCH",
    '18"',
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

OATH_SELECT += "," + ",".join(f"charge_{i}_code_description" for i in range(4, 11))

CSCL_SELECT = ",".join(
    [
        "physicalid",
        "l_low_hn",
        "l_high_hn",
        "r_low_hn",
        "r_high_hn",
        "l_zip",
        "r_zip",
        "boroughcode as borocode",
        "full_street_name as full_stree",
        "street_name as st_name",
        "stname_label as st_label",
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
            order=":id",
        )
        rows.extend(page)
        print(f"  {dataset_id}: {len(rows):,} rows", flush=True)
        if len(page) < page_size:
            break
        offset += page_size
    return rows


def cleanliness_text(row: dict) -> str:
    pieces = [
        row.get("violation_description"),
        *(row.get(f"charge_{i}_code_description") for i in range(1, 11)),
    ]
    return " | ".join(str(x or "").upper() for x in pieces)


def is_cleanliness_candidate(row: dict) -> bool:
    text = cleanliness_text(row)
    return any(term in text for term in CLEANLINESS_TERMS)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--replay", action="store_true", help="Reuse saved extracts without network access")
    args = parser.parse_args()
    OUTDIR.mkdir(parents=True, exist_ok=True)
    rawdir = ROOT / "data" / "raw" / "pilot"
    rawdir.mkdir(parents=True, exist_ok=True)
    manifest_path = rawdir / "manifest.json"
    manifest = json.loads(manifest_path.read_text()) if args.replay else {
        "extracted_at_utc": datetime.now(timezone.utc).isoformat(),
        "pilot_start": START, "pilot_end": END, "borough": BOROUGH, "sources": {},
    }
    if args.replay and (manifest["pilot_start"], manifest["pilot_end"], manifest["borough"]) != (START, END, BOROUGH):
        raise ValueError("Replay parameters differ from saved extraction")
    if BOROUGH != "MANHATTAN":
        raise ValueError("This pilot currently supports MANHATTAN only")
    if datetime.fromisoformat(START) >= datetime.fromisoformat(END):
        raise ValueError("PILOT_START must precede PILOT_END")

    def extract(name, *, where, select):
        path = rawdir / f"{name}.json"
        if args.replay:
            source = manifest["sources"][name]
            if (source["dataset_id"], source["where"], source["select"]) != (DATASETS[name], where, select):
                raise ValueError(f"Replay query differs from saved extraction: {name}")
            payload = path.read_bytes()
            if hashlib.sha256(payload).hexdigest() != manifest["sources"][name]["sha256"]:
                raise ValueError(f"Snapshot checksum mismatch: {name}")
            return json.loads(payload)
        print(f"Fetching {name}...", flush=True)
        meta = metadata(DATASETS[name])
        (rawdir / f"{name}_metadata.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
        rows = fetch_all(DATASETS[name], where=where, select=select)
        payload = json.dumps(rows, sort_keys=True).encode("utf-8")
        path.write_bytes(payload)
        manifest["sources"][name] = {
            "dataset_id": DATASETS[name], "where": where, "select": select,
            "order": ":id", "rows": len(rows), "sha256": hashlib.sha256(payload).hexdigest(),
            "rows_updated_at": meta.get("rowsUpdatedAt"),
        }
        manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        print(f"Fetched {len(rows):,} {name} rows", flush=True)
        return rows

    oath_where = (
        f"violation_location_borough='{BOROUGH}' "
        f"AND violation_date >= '{START}' AND violation_date < '{END}'"
    )
    oath_all = extract("oath", where=oath_where, select=OATH_SELECT)
    candidates = [r for r in oath_all if is_cleanliness_candidate(r)]

    # Manhattan CSCL rows only.
    cscl = extract(
        "cscl",
        where="boroughcode='1'",
        select=CSCL_SELECT,
    )

    sweep = extract(
        "sweepnyc",
        where=f"date_visited >= '{START}' AND date_visited < '{END}'",
        select="physical_id,date_visited,cscl_version",
    )
    swept_ids = {str(r["physical_id"]) for r in sweep if r.get("physical_id") is not None}

    results = []
    quality_counts = Counter()
    method_counts = Counter()

    street_index = defaultdict(list)
    for segment in cscl:
        for name in candidate_street_names(segment):
            street_index[name].append(segment)
    for row in candidates:
        match = match_oath_to_cscl(row, street_index[normalize_street(row.get("violation_location_street_name"))])
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
    match_rate = confident / eligible if eligible else None
    exact_rate = quality_counts["exact"] / eligible if eligible else None

    swept_records = sum(bool(r["swept_during_pilot_month"]) for r in results)
    summary = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "pilot_start": START,
        "pilot_end": END,
        "borough": BOROUGH,
        "oath_rows_in_period": len(oath_all),
        "cleanliness_candidate_rows": eligible,
        "cscl_rows": len(cscl),
        "sweepnyc_rows_in_period": len(sweep),
        "sweepnyc_extract_scope": "citywide; overlap assessed on Manhattan matched IDs",
        "unique_swept_physical_ids": len(swept_ids),
        "quality_counts": dict(quality_counts),
        "method_counts": dict(method_counts),
        "exact_rate": exact_rate,
        "confident_match_rate": match_rate,
        "sweep_linkage_rate_all_eligible": swept_records / eligible if eligible else None,
        "sweep_overlap_rate_among_matched": swept_records / confident if confident else None,
        "duplicate_oath_ticket_rows": len(oath_all) - len({r.get("ticket_number") for r in oath_all}),
        "threshold": MIN_ACCEPTABLE_MATCH_RATE,
        "passes_threshold": match_rate >= MIN_ACCEPTABLE_MATCH_RATE if match_rate is not None else None,
        "status": "evaluated" if eligible else "no_eligible_records",
        "source_manifest": manifest,
        "python_version": platform.python_version(),
        "sweep_cscl_versions": sorted({r.get("cscl_version", "unknown") for r in sweep}),
        "matched_unique_segments": len({r["matched_physical_id"] for r in results if r["matched_physical_id"]}),
        "matched_unique_segments_swept_in_period": len({r["matched_physical_id"] for r in results if r["swept_during_pilot_month"]}),
        "matched_oath_records_swept_in_period": sum(
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

    (OUTDIR / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
