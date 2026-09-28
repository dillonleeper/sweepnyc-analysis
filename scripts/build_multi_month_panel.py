"""Build the two-month (July + August 2026) street-segment x day event panel.

Extends build_event_panel.py's single-month (August) panel with July 2026,
fetched and matched the same way as August's Phase 2 additions (see
docs/phase2-effect-analysis-2026-09.md): OATH and 311 records pulled via a
browser fetch against the Socrata API (this session's shell has no direct
network route to NYC Open Data), then address-matched to the same
851-segment population.

Important asymmetry, documented rather than hidden: August's OATH matches
are Phase 1's fully human-reviewed reviewed_matches.csv (case review,
LION-gap resolution, spatial corroboration). July's OATH matches are
automated-only (scripts/match_oath_month.py), the same first-pass method
Phase 1 started from before its manual review. July's numbers are therefore
lower-confidence than August's for OATH specifically. 311 matching used the
identical method (address matching, no manual review) for both months, so
July and August's 311 columns ARE directly comparable.

Population: the same 851 Manhattan segments as the single-month panel
(segments linked to >=1 eligible August violation in Phase 1). July uses
this same population rather than a fresh July-linked population, so the
two months describe the same set of street segments.
"""
import csv
import hashlib
import json
from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PROCESSED_ADJ = ROOT / "data/processed/adjudication"
RAW_PILOT = ROOT / "data/raw/pilot"
RAW_PHASE2 = ROOT / "data/raw/phase2"
OUT = ROOT / "data/processed/effect_analysis"

AUGUST_DAYS = [date(2026, 8, 1) + timedelta(days=i) for i in range(31)]
JULY_DAYS = [date(2026, 7, 1) + timedelta(days=i) for i in range(31)]


def main():
    OUT.mkdir(parents=True, exist_ok=True)

    matches = list(csv.DictReader((PROCESSED_ADJ / "reviewed_matches.csv").open(encoding="utf-8")))
    matched = [r for r in matches if r["reviewed_physical_id"]]
    segments = sorted({r["reviewed_physical_id"] for r in matched})
    seg_set = set(segments)

    # --- August: OATH (reviewed), sweep, 311 (already matched in Phase 2) ---
    violations_aug = defaultdict(int)
    for r in matched:
        violations_aug[(r["reviewed_physical_id"], r["violation_date"][:10])] += 1

    sweep_aug_raw = json.loads((RAW_PILOT / "sweepnyc.json").read_text())
    visits_aug = defaultdict(set)
    for row in sweep_aug_raw:
        pid = str(row["physical_id"])
        if pid in seg_set:
            visits_aug[pid].add(row["date_visited"][:10])

    complaints_aug = defaultdict(int)
    matched_311_aug_path = OUT / "matched_311.json"
    if matched_311_aug_path.exists():
        for rec in json.loads(matched_311_aug_path.read_text()):
            if rec["physical_id"] in seg_set:
                complaints_aug[(rec["physical_id"], rec["date"])] += 1

    # --- July: OATH (automated), sweep, 311 (automated, same method both months) ---
    violations_jul = defaultdict(int)
    matched_oath_july_path = OUT / "matched_oath_july.json"
    if matched_oath_july_path.exists():
        for rec in json.loads(matched_oath_july_path.read_text()):
            if rec["physical_id"] in seg_set:
                violations_jul[(rec["physical_id"], rec["date"])] += 1

    visits_jul = defaultdict(set)
    sweep_jul_path = RAW_PHASE2 / "sweep_july.json"
    if sweep_jul_path.exists():
        for row in json.loads(sweep_jul_path.read_text()):
            pid = str(row["physical_id"])
            if pid in seg_set:
                visits_jul[pid].add(row["date_visited"][:10])

    complaints_jul = defaultdict(int)
    matched_311_jul_path = OUT / "matched_311_july.json"
    if matched_311_jul_path.exists():
        for rec in json.loads(matched_311_jul_path.read_text()):
            if rec["physical_id"] in seg_set:
                complaints_jul[(rec["physical_id"], rec["date"])] += 1

    panel_rows = []
    for pid in segments:
        for month_days, visits, violations, complaints in (
            (JULY_DAYS, visits_jul.get(pid, set()), violations_jul, complaints_jul),
            (AUGUST_DAYS, visits_aug.get(pid, set()), violations_aug, complaints_aug),
        ):
            for d in month_days:
                dstr = d.isoformat()
                panel_rows.append({
                    "physical_id": pid,
                    "date": dstr,
                    "day_of_week": d.strftime("%a"),
                    "month": d.strftime("%Y-%m"),
                    "swept": int(dstr in visits),
                    "violation_count": violations.get((pid, dstr), 0),
                    "complaint_311_count": complaints.get((pid, dstr), 0),
                })

    fieldnames = list(panel_rows[0])
    out_csv = OUT / "segment_day_panel_multi_month.csv"
    with out_csv.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(panel_rows)

    n_rows = len(panel_rows)
    n_swept_days = sum(r["swept"] for r in panel_rows)
    n_violations = sum(r["violation_count"] for r in panel_rows)
    n_311 = sum(r["complaint_311_count"] for r in panel_rows)

    summary = {
        "segments": len(segments),
        "months": ["2026-07", "2026-08"],
        "panel_rows_segment_x_day": n_rows,
        "swept_segment_days": n_swept_days,
        "total_eligible_violations_in_panel": n_violations,
        "total_311_complaints_in_panel": n_311,
        "asymmetry_warning": (
            "August OATH violations are Phase 1's manually reviewed "
            "reviewed_matches.csv; July OATH violations are automated-match-only "
            "(scripts/match_oath_month.py), not manually reviewed. 311 matching "
            "used the identical automated method for both months."
        ),
    }
    (OUT / "panel_summary_multi_month.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
