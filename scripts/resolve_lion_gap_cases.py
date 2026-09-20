"""Resolve the eight violations on the four PhysicalIDs absent from LION 23C.

The case review located an official LION 23C archive and found 846 of 850
distinct matched PhysicalIDs present in it. The four absent IDs (204036,
206391, 206394, 206507) affect eight violations. This script explains and
resolves the gap.

Root cause: `data/raw/pilot/sweepnyc.json` declares `cscl_version: "23C"` on
every record (SweepNYC's own PhysicalID vintage), while the pilot matcher
assigned violations against a current CSCL snapshot. For 1,914 of 1,922
matched violations the ID happens to be unchanged between the two vintages,
so matching directly on ID worked. For these four segments, the PhysicalID
was renumbered between the 23C vintage and the current snapshot, so the
current-vintage ID assigned by the matcher does not exist in the 23C
reference and cannot be found in the 23C-keyed SweepNYC extract either,
which silently understated sweep-overlap for these eight rows.

Method: re-match each of the eight violations' street/house/zip against
LION 23C address ranges (reusing the same matcher used for CSCL), and
corroborate with address-point-to-segment-geometry distance in EPSG:2263,
as the five-case review did. This is NOT a general re-matching pass: the
crosswalk check below confirms the ID vintage only diverges for these four
segments among all 1,922 matched violations.
"""
import csv
import hashlib
import json
import sys
from collections import defaultdict
from pathlib import Path

import pyogrio
from pyproj import Transformer
from shapely.geometry import Point
from shapely.ops import transform, unary_union

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from sweepnyc.matching import candidate_street_names, match_oath_to_cscl, normalize_street  # noqa: E402

RAW_PILOT = ROOT / "data/raw/pilot"
RAW_ADJ = ROOT / "data/raw/adjudication"
PROCESSED_PILOT = ROOT / "data/processed/pilot"
PROCESSED_VAL = ROOT / "data/processed/validation"
OUT = ROOT / "data/processed/adjudication"

MISSING_IDS = {"204036", "206391", "206394", "206507"}

# Address points for the affected addresses, drawn from the saved validation
# extract (data/raw/validation/address_points.json), used only for the
# geometric distance corroboration.
ADDRESS_POINTS = {
    "051_bayard": ("51", "BAYARD ST", "10013", -73.997565801375, 40.715224513047),
    "600_w157": ("600", "W  157 ST", "10032", -73.945661040747, 40.834289393005),
    "229_henry": ("229", "HENRY ST", "10002", -73.986124977078, 40.713819948275),
    "231_henry": ("231", "HENRY ST", "10002", -73.986039245306, 40.713827276263),
    "025_montgomery": ("25", "MONTGOMERY ST", "10002", -73.984844555476, 40.713379973922),
}


def load_lion_rows():
    cols = ["PhysicalID", "Street", "FromLeft", "ToLeft", "FromRight", "ToRight", "LZip", "RZip", "LBoro", "RBoro"]
    lion = pyogrio.read_dataframe(RAW_ADJ / "lion_23c/lion/lion.gdb", layer="lion", columns=cols)
    assert str(lion.crs).upper() == "EPSG:2263"
    lion = lion[(lion["LBoro"] == 1.0) | (lion["RBoro"] == 1.0)]
    lion = lion[(lion["FromLeft"] != 0) | (lion["ToLeft"] != 0) | (lion["FromRight"] != 0) | (lion["ToRight"] != 0)]
    rows = []
    for _, r in lion.iterrows():
        rows.append({
            "full_stree": r["Street"], "st_name": r["Street"], "st_label": r["Street"],
            "l_low_hn": str(int(r["FromLeft"])) if r["FromLeft"] else None,
            "l_high_hn": str(int(r["ToLeft"])) if r["ToLeft"] else None,
            "r_low_hn": str(int(r["FromRight"])) if r["FromRight"] else None,
            "r_high_hn": str(int(r["ToRight"])) if r["ToRight"] else None,
            "l_zip": str(int(r["LZip"])) if r["LZip"] == r["LZip"] and r["LZip"] else "",
            "r_zip": str(int(r["RZip"])) if r["RZip"] == r["RZip"] and r["RZip"] else "",
            "physicalid": str(int(r["PhysicalID"])) if r["PhysicalID"] == r["PhysicalID"] else None,
        })
    return lion, rows


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    rows = list(csv.DictReader((PROCESSED_PILOT / "matches.csv").open(encoding="utf-8")))
    tickets = {r["ticket_number"]: r for r in rows}
    sweep_ids = {r["physical_id"] for r in json.loads((RAW_PILOT / "sweepnyc.json").read_text())}

    lion_gdf, lion_rows = load_lion_rows()
    street_index = defaultdict(list)
    for seg in lion_rows:
        for name in candidate_street_names(seg):
            street_index[name].append(seg)

    # Crosswalk-scope check: confirm the ID-vintage mismatch is confined to
    # these four segments among all 1,922 matched violations (not a broader
    # systemic issue). This governs whether the rest of the matched
    # population's overlap flag can be trusted as-is.
    scope_check = {"checked": 0, "id_differs": 0, "unexpected_ids": set()}
    for row in rows:
        if not row["matched_physical_id"]:
            continue
        scope_check["checked"] += 1
        candidates = street_index[normalize_street(row.get("violation_location_street_name"))]
        m = match_oath_to_cscl(row, candidates)
        if m.physical_id and m.physical_id != row["matched_physical_id"]:
            scope_check["id_differs"] += 1
            if row["matched_physical_id"] not in MISSING_IDS:
                scope_check["unexpected_ids"].add(row["matched_physical_id"])
    if scope_check["unexpected_ids"]:
        raise ValueError(
            "ID-vintage mismatch found beyond the four known missing IDs: "
            f"{sorted(scope_check['unexpected_ids'])}. Human review required."
        )

    project = Transformer.from_crs(4326, 2263, always_xy=True).transform
    decisions = []
    ticket_to_case = {
        "046898837M": "051_bayard",
        "049994082M": "600_w157",
        "049935143R": "229_henry", "049906526L": "229_henry", "049968594R": "229_henry",
        "049906527N": "231_henry", "049968595Z": "231_henry",
        "049961979X": "025_montgomery",
    }
    for ticket, case in ticket_to_case.items():
        original = tickets[ticket]
        assert original["matched_physical_id"] in MISSING_IDS
        house, street, zipc, lon, lat = ADDRESS_POINTS[case]
        candidates = street_index[normalize_street(street)]
        oath_like = {
            "violation_location_street_name": street,
            "violation_location_house": house,
            "violation_location_zip_code": zipc,
        }
        m = match_oath_to_cscl(oath_like, candidates)
        if m.quality != "exact" or m.physical_id is None:
            raise ValueError(f"{ticket}: no unambiguous LION 23C candidate ({m.quality}); human review required")
        point = transform(project, Point(lon, lat))
        subset = lion_gdf[lion_gdf.PhysicalID == int(m.physical_id)]
        distance_ft = round(point.distance(unary_union(subset.geometry)), 2)
        reviewed_overlap = m.physical_id in sweep_ids
        decisions.append({
            "ticket_number": ticket,
            "address": f"{house} {street}",
            "original_physical_id": original["matched_physical_id"],
            "reviewed_physical_id": m.physical_id,
            "decision": "lion_23c_id_vintage_correction",
            "match_quality": m.quality,
            "point_to_lion23c_segment_ft": distance_ft,
            "reviewed_sweep_overlap": reviewed_overlap,
        })

    overrides = {d["ticket_number"]: d["reviewed_physical_id"] for d in decisions}
    overlap_overrides = {d["ticket_number"]: d["reviewed_sweep_overlap"] for d in decisions}

    # Extend the existing case-reviewed output (which already carries the
    # three West 125/East 27 corrections) with these four-ID corrections,
    # rather than replacing it.
    existing_reviewed = list(csv.DictReader((OUT / "reviewed_matches.csv").open(encoding="utf-8")))
    for row in existing_reviewed:
        if row["ticket_number"] in overrides:
            row["reviewed_physical_id"] = overrides[row["ticket_number"]]
            row["reviewed_sweep_overlap"] = overlap_overrides[row["ticket_number"]]
            row["case_reviewed"] = "True"
    with (OUT / "reviewed_matches.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(existing_reviewed[0]))
        writer.writeheader()
        writer.writerows(existing_reviewed)

    summary = {
        "scope_check_total_matched_rows": scope_check["checked"],
        "scope_check_id_vintage_mismatches": scope_check["id_differs"],
        "scope_check_confined_to_four_known_ids": not scope_check["unexpected_ids"],
        "cases": decisions,
        "recovered_sweep_overlap_count": sum(1 for d in decisions if d["reviewed_sweep_overlap"]),
        "root_cause": (
            "SweepNYC's frozen August extract keys physical_id to cscl_version 23C. "
            "The pilot matcher used a current CSCL snapshot. For these four segments "
            "the PhysicalID was renumbered between vintages; for the other 1,914 "
            "matched violations the ID is unchanged across vintages."
        ),
        "limitations": (
            "LION 23C is not verified to be the exact CSCL 23C snapshot DSNY/SweepNYC "
            "uses internally (same open question as the five-case review). The public "
            "SweepNYC lookup was checked informally for these five addresses (not saved "
            "with checksums): it returned the 23C-vintage ID for Henry/Montgomery/W157 "
            "St and the current-vintage ID for Bayard St, an inconsistency this script "
            "does not attempt to explain. The frozen August extract has no record under "
            "either ID vintage for the Bayard St segment; that is treated as a genuine "
            "absence of an August observation, not a matching failure."
        ),
    }
    (OUT / "lion_gap_resolution_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    inputs = [PROCESSED_PILOT / "matches.csv", RAW_PILOT / "sweepnyc.json", RAW_ADJ / "lion_23c" / "lion" / "lion.gdb"]
    checksums = {}
    for p in inputs:
        if p.is_dir():
            continue
        checksums[str(p.relative_to(ROOT))] = hashlib.sha256(p.read_bytes()).hexdigest()
    (OUT / "lion_gap_resolution_checksums.json").write_text(json.dumps(checksums, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
