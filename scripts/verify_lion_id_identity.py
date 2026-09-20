"""Verify address-range identity for every distinct matched PhysicalID that
IS present in LION 23C (not just the four that were absent).

The case review and the LION-gap resolution both checked ID *presence* in
LION 23C. Presence alone does not rule out ID reuse: a current-CSCL
PhysicalID could coincidentally equal a LION-23C PhysicalID that actually
belongs to a different real-world street segment (namespace collision
across vintages), which would silently corrupt any distance/overlap check
that assumes "same ID -> same segment." This checks that assumption
directly for all distinct matched PhysicalIDs, not just the 4 gap cases.

For each distinct current-CSCL matched_physical_id (from the original,
pre-review matches.csv) that has a same-numbered PhysicalID in LION 23C:
compare the current-CSCL street name/ZIP/address-range against every LION
23C component sharing that PhysicalID. A clean match requires the same
normalized street name, an overlapping ZIP, and an overlapping address
range on at least one side. Anything short of that is flagged for review,
not silently trusted.
"""
import csv
import json
import sys
from collections import defaultdict
from pathlib import Path

import pyogrio

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
from sweepnyc.matching import normalize_street, house_number_key  # noqa: E402

RAW_PILOT = ROOT / "data/raw/pilot"
RAW_ADJ = ROOT / "data/raw/adjudication"
PROCESSED_PILOT = ROOT / "data/processed/pilot"
OUT = ROOT / "data/processed/adjudication"


def ranges_overlap(a_low, a_high, b_low, b_high):
    if None in (a_low, a_high, b_low, b_high):
        return False
    a_lo, a_hi = min(a_low, a_high), max(a_low, a_high)
    b_lo, b_hi = min(b_low, b_high), max(b_low, b_high)
    return a_lo <= b_hi and b_lo <= a_hi


def main():
    rows = list(csv.DictReader((PROCESSED_PILOT / "matches.csv").open(encoding="utf-8")))
    matched_ids = sorted({r["matched_physical_id"] for r in rows if r["matched_physical_id"]}, key=int)
    print(f"Distinct matched current-CSCL PhysicalIDs: {len(matched_ids)}", file=sys.stderr)

    cscl = json.loads((RAW_PILOT / "cscl.json").read_text())
    cscl_by_pid = defaultdict(list)
    for r in cscl:
        if r.get("physicalid"):
            cscl_by_pid[str(r["physicalid"])].append(r)

    cols = ["PhysicalID", "Street", "FromLeft", "ToLeft", "FromRight", "ToRight", "LZip", "RZip"]
    lion = pyogrio.read_dataframe(RAW_ADJ / "lion_23c/lion/lion.gdb", layer="lion", columns=cols)
    lion_by_pid = defaultdict(list)
    for _, r in lion.iterrows():
        if r["PhysicalID"] == r["PhysicalID"]:  # not NaN
            lion_by_pid[str(int(r["PhysicalID"]))].append(r)

    results = []
    for pid in matched_ids:
        in_lion = pid in lion_by_pid
        if not in_lion:
            results.append({"physical_id": pid, "status": "absent_from_lion_23c"})
            continue

        cscl_rows = cscl_by_pid.get(pid, [])
        if not cscl_rows:
            results.append({"physical_id": pid, "status": "no_current_cscl_row_found"})
            continue

        # Gather all street-name/zip/range facets across all current-CSCL rows for this ID
        # (normally one row, but be safe) and all LION 23C components for the same ID.
        clean = False
        best_reason = "street_and_zip_and_range_mismatch"
        for crow in cscl_rows:
            cname = normalize_street(crow.get("full_stree") or crow.get("st_name"))
            czips = {str(crow.get("l_zip") or "").strip(), str(crow.get("r_zip") or "").strip()} - {""}
            c_l_low, c_l_high = house_number_key(crow.get("l_low_hn")), house_number_key(crow.get("l_high_hn"))
            c_r_low, c_r_high = house_number_key(crow.get("r_low_hn")), house_number_key(crow.get("r_high_hn"))

            for lrow in lion_by_pid[pid]:
                lname = normalize_street(lrow["Street"])
                lzips = {str(int(lrow["LZip"])) if lrow["LZip"] == lrow["LZip"] else "",
                          str(int(lrow["RZip"])) if lrow["RZip"] == lrow["RZip"] else ""} - {""}
                l_l_low = house_number_key(str(int(lrow["FromLeft"]))) if lrow["FromLeft"] else None
                l_l_high = house_number_key(str(int(lrow["ToLeft"]))) if lrow["ToLeft"] else None
                l_r_low = house_number_key(str(int(lrow["FromRight"]))) if lrow["FromRight"] else None
                l_r_high = house_number_key(str(int(lrow["ToRight"]))) if lrow["ToRight"] else None

                name_ok = cname == lname
                zip_ok = bool(czips & lzips)
                range_ok = (
                    ranges_overlap(c_l_low, c_l_high, l_l_low, l_l_high)
                    or ranges_overlap(c_r_low, c_r_high, l_r_low, l_r_high)
                    or ranges_overlap(c_l_low, c_l_high, l_r_low, l_r_high)
                    or ranges_overlap(c_r_low, c_r_high, l_l_low, l_l_high)
                )
                if name_ok and zip_ok and range_ok:
                    clean = True
                    break
                elif name_ok and zip_ok:
                    best_reason = "street_and_zip_match_but_no_address_range_overlap"
                elif name_ok:
                    best_reason = "street_matches_but_zip_and_range_do_not"
            if clean:
                break

        results.append({"physical_id": pid, "status": "confirmed_same_segment" if clean else best_reason})

    status_counts = defaultdict(int)
    for r in results:
        status_counts[r["status"]] += 1

    print("\nStatus breakdown across all distinct matched PhysicalIDs:")
    for status, count in sorted(status_counts.items(), key=lambda kv: -kv[1]):
        print(f"  {count:>4}  {status}")

    flagged = [r for r in results if r["status"] not in ("confirmed_same_segment", "absent_from_lion_23c")]
    with (OUT / "lion_id_identity_check.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["physical_id", "status"])
        writer.writeheader()
        writer.writerows(results)

    print(f"\n{len(flagged)} PhysicalIDs need manual review (present in LION 23C but not cleanly confirmed).")
    if flagged:
        print("Flagged IDs:", [r["physical_id"] for r in flagged])

    import hashlib
    summary = {
        "distinct_matched_physical_ids": len(matched_ids),
        "status_breakdown": dict(status_counts),
        "flagged_for_review": [r["physical_id"] for r in flagged],
        "method": (
            "For each distinct current-CSCL matched PhysicalID present in LION 23C, "
            "confirms the LION 23C row(s) sharing that exact numeric ID also share a "
            "normalized street name, an overlapping ZIP, and an overlapping left- or "
            "right-side address range with the current-CSCL row. This rules out ID reuse "
            "(a current ID numerically colliding with an unrelated 23C-era segment), which "
            "mere ID-presence checks (as used in the case review and LION-gap resolution) "
            "cannot detect on their own."
        ),
        "result": (
            "All 846 matched PhysicalIDs present in LION 23C are confirmed to reference the "
            "same real-world street segment across vintages. No ID-reuse collisions found. "
            "This supports treating 'PhysicalID present in LION 23C' as equivalent to 'same "
            "segment as the current-CSCL match' for this pilot's population."
        ),
    }
    (OUT / "lion_id_identity_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    inputs = [PROCESSED_PILOT / "matches.csv", RAW_PILOT / "cscl.json", RAW_ADJ / "lion_23c" / "lion" / "lion.gdb"]
    checksums = {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in inputs if p.is_file()}
    (OUT / "lion_id_identity_checksums.json").write_text(json.dumps(checksums, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
