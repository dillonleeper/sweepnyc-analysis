"""Audit frozen pilot assignments against saved address points and geometry."""

import csv, json, sys, random, hashlib, re
from pathlib import Path
from collections import Counter, defaultdict

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from sweepnyc.validation import AddressAudit
from sweepnyc.matching import (
    match_oath_to_cscl,
    normalize_street,
    candidate_street_names,
)

SEED = 20260819
OUT = ROOT / "data/processed/validation"


def write_csv(name, rows):
    if not rows:
        return
    fields = list(rows[0])
    with (OUT / name).open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(
            {
                k: json.dumps(v, sort_keys=True) if isinstance(v, (list, dict)) else v
                for k, v in row.items()
            }
            for row in rows
        )


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    for folder in ["pilot", "validation"]:
        base = ROOT / "data/raw" / folder
        manifest = json.loads((base / "manifest.json").read_text())
        for name, source in manifest["sources"].items():
            actual = hashlib.sha256((base / f"{name}.json").read_bytes()).hexdigest()
            if actual != source["sha256"]:
                raise ValueError(f"Snapshot checksum mismatch: {name}")
    rows = list(
        csv.DictReader(
            (ROOT / "data/processed/pilot/matches.csv").open(encoding="utf-8")
        )
    )
    points = json.loads((ROOT / "data/raw/validation/address_points.json").read_text())
    segments = json.loads((ROOT / "data/raw/validation/cscl_geometry.json").read_text())
    audit = AddressAudit(points, segments)
    all_evidence = [audit.inspect(r) for r in rows]
    matched = sorted(
        (r for r in rows if r["matched_physical_id"]), key=lambda r: r["ticket_number"]
    )
    sample_ids = {r["ticket_number"] for r in random.Random(SEED).sample(matched, 100)}
    sample = [r for r in all_evidence if r["ticket_number"] in sample_ids]
    challenges = [
        r
        for r in all_evidence
        if r["original_quality"] == "high_confidence"
        and r["ticket_number"] not in sample_ids
    ]
    unresolved = [r for r in all_evidence if not r["assigned_physical_id"]]
    write_csv("sample_100.csv", sample)
    write_csv("suffix_challenges.csv", challenges)
    write_csv("unresolved_106.csv", unresolved)
    write_csv("all_eligible_audit.csv", all_evidence)
    (OUT / "evidence.json").write_text(json.dumps(all_evidence, indent=2))
    # All four suffixed addresses are included, whether in the random sample or challenge set.
    write_csv(
        "all_suffix_cases.csv",
        [r for r in all_evidence if r["original_quality"] == "high_confidence"],
    )
    write_csv(
        "assignment_holds.csv",
        [
            r
            for r in all_evidence
            if r["audit_status"]
            in {"assignment_discrepancy", "assigned_segment_missing_current_reference"}
        ],
    )
    old = json.loads((ROOT / "data/raw/pilot/cscl.json").read_text())
    old_ids = {r["physicalid"] for r in old}
    new_ids = {r["physicalid"] for r in segments}
    matched_ids = {r["matched_physical_id"] for r in matched}
    comparable = {
        "full_stree": "full_street_name",
        "st_label": "stname_label",
        "st_name": "street_name",
        **{
            k: k
            for k in [
                "l_low_hn",
                "l_high_hn",
                "r_low_hn",
                "r_high_hn",
                "l_zip",
                "r_zip",
            ]
        },
    }
    current = {r["physicalid"]: r for r in segments}
    changed = []
    for row in old:
        if row["physicalid"] in current:
            differences = {
                k: {"pilot": row.get(k), "current": current[row["physicalid"]].get(v)}
                for k, v in comparable.items()
                if row.get(k) != current[row["physicalid"]].get(v)
            }
            if differences:
                changed.append(
                    {"physical_id": row["physicalid"], "differences": differences}
                )
    write_csv("current_reference_changes.csv", changed)
    # Same matcher, frozen OATH rows, refreshed reference: a version-sensitivity check.
    current_index = defaultdict(list)
    for seg in segments:
        mapped = {
            **seg,
            "full_stree": seg.get("full_street_name"),
            "st_name": seg.get("street_name"),
            "st_label": seg.get("stname_label"),
        }
        for name in candidate_street_names(mapped):
            current_index[name].append(mapped)
    sweep = json.loads((ROOT / "data/raw/pilot/sweepnyc.json").read_text())
    swept_ids = {r["physical_id"] for r in sweep}
    reassigned = []
    current_quality = Counter()
    current_overlap = 0
    for row in rows:
        new = match_oath_to_cscl(
            row,
            current_index[normalize_street(row.get("violation_location_street_name"))],
        )
        current_quality[new.quality] += 1
        current_overlap += bool(new.physical_id and new.physical_id in swept_ids)
        if (new.physical_id or "", new.quality) != (
            row["matched_physical_id"],
            row["match_quality"],
        ):
            reassigned.append(
                {
                    "ticket_number": row["ticket_number"],
                    "house": row.get("violation_location_house", ""),
                    "street": row.get("violation_location_street_name", ""),
                    "pilot_physical_id": row["matched_physical_id"],
                    "current_physical_id": new.physical_id or "",
                    "pilot_quality": row["match_quality"],
                    "current_quality": new.quality,
                    "pilot_sweep_overlap": row["swept_during_pilot_month"],
                    "current_sweep_overlap": bool(
                        new.physical_id and new.physical_id in swept_ids
                    ),
                }
            )
    write_csv("reference_sensitivity.csv", reassigned)
    original_by_id = {r["physicalid"]: r for r in old}
    diagnostics = []
    for row in unresolved:
        suggested = row["suggested_physical_id"]
        original = original_by_id.get(suggested)
        reason = "no_exact_address_point"
        if not row["house"]:
            reason = "missing_house_number"
        elif "1 2" in row["house"]:
            reason = "fractional_house_not_parsed"
        elif suggested:
            if not original:
                reason = "suggested_id_absent_pilot_reference"
            elif row["original_method"] == "multiple_house_range_segments":
                reason = "overlapping_house_ranges_spatial_candidate"
            elif row["zip"] and row["zip"] not in {
                original.get("l_zip"),
                original.get("r_zip"),
            }:
                reason = "zip_conflict_spatial_candidate"
            else:
                reason = "house_range_or_parity_conflict_spatial_candidate"
        elif normalize_street(row["street"]) == "7 AVE":
            reason = "uptown_seventh_avenue_alias_needs_reference"
        elif row["original_method"] == "no_street_match":
            reason = "street_alias_or_name_gap"
        diagnostics.append(
            {
                **row,
                "diagnostic": reason,
                "suggested_segment_original_ranges": original or {},
                "action": (
                    "review_candidate_do_not_auto_assign"
                    if suggested
                    else "additional_address_evidence_required"
                ),
            }
        )
    write_csv("unresolved_106.csv", diagnostics)
    write_csv(
        "possible_recoveries.csv",
        [r for r in diagnostics if r["audit_status"] == "possible_recovery"],
    )
    summary = {
        "audit_type": "same-lineage address-point spatial corroboration; not independent accuracy",
        "sample_design": "simple random sample without replacement of matched violation records, sorted by ticket before sampling",
        "random_seed": SEED,
        "sample_size": len(sample),
        "sample_unique_addresses": len({(r["house"], r["street"]) for r in sample}),
        "sample_status_counts": dict(Counter(r["audit_status"] for r in sample)),
        "sample_field_validated_corroborated": sum(
            r["audit_status"] == "corroborated" and r["field_validated_point_present"]
            for r in sample
        ),
        "suffix_challenge_count": len(challenges),
        "suffix_challenge_status_counts": dict(
            Counter(r["audit_status"] for r in challenges)
        ),
        "unresolved_status_counts": dict(
            Counter(r["audit_status"] for r in unresolved)
        ),
        "unresolved_diagnostic_counts": dict(
            Counter(r["diagnostic"] for r in diagnostics)
        ),
        "all_matched_status_counts": dict(
            Counter(
                r["audit_status"] for r in all_evidence if r["assigned_physical_id"]
            )
        ),
        "reference_drift": {
            "pilot_rows": len(old),
            "audit_rows": len(segments),
            "added_ids": sorted(new_ids - old_ids),
            "removed_ids": sorted(old_ids - new_ids),
            "changed_attribute_ids": len(changed),
            "changed_matched_ids": len(
                {r["physical_id"] for r in changed} & matched_ids
            ),
            "matched_ids_absent_current": sorted(matched_ids - new_ids),
        },
        "historical_23c_alignment": "not_verified",
        "current_reference_sensitivity": {
            "changed_records": len(reassigned),
            "quality_counts": dict(current_quality),
            "sweep_overlap_records": current_overlap,
        },
        "spatial_rules": {
            "max_distance_ft": 150,
            "min_runner_up_margin_ft": 20,
            "min_along_segment_endpoint_distance_ft": 20,
            "address_match": "exact normalized street and house including suffix; no range expansion; excludes explicitly non-built/retired points",
        },
        "pilot_matches_sha256": hashlib.sha256(
            (ROOT / "data/processed/pilot/matches.csv").read_bytes()
        ).hexdigest(),
        "input_manifest": json.loads(
            (ROOT / "data/raw/validation/manifest.json").read_text()
        ),
    }
    (OUT / "summary.json").write_text(json.dumps(summary, indent=2))
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
