"""Build the Phase 2 street-segment x day event panel.

Grain: one row per (reviewed_physical_id, calendar day) for every August 2026
calendar day, restricted to the 851 Manhattan segments already linked to at
least one eligible OATH cleanliness violation in Phase 1
(data/processed/adjudication/reviewed_matches.csv).

Columns:
  physical_id       -- reviewed CSCL PhysicalID (Phase 1 output)
  date              -- calendar date, 2026-08-01 .. 2026-08-31
  swept             -- 1 if SweepNYC recorded a visit to this segment on this day
  violation_count   -- count of eligible OATH cleanliness violations recorded
                       on this segment on this day
  day_of_week       -- Mon..Sun, for day-of-week fixed effects
  segment_ever_swept_in_august -- 1 if the segment has >=1 recorded August visit
                                   at all (used to flag the small always-zero group)

Known scope limits (see docs/phase2-effect-analysis-2026-09.md):
  - Population is the 851 violation-linked segments only, not a citywide or
    random sample of Manhattan blocks.
  - Outcome is OATH cleanliness violations only; 311 complaints and weather
    controls are not yet joined in (no network access to NYC Open Data from
    this environment -- see docs).
  - One calendar month (August 2026) only.
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
OUT = ROOT / "data/processed/effect_analysis"

AUGUST_DAYS = [date(2026, 8, 1) + timedelta(days=i) for i in range(31)]


def main():
    OUT.mkdir(parents=True, exist_ok=True)

    matches = list(csv.DictReader((PROCESSED_ADJ / "reviewed_matches.csv").open(encoding="utf-8")))
    matched = [r for r in matches if r["reviewed_physical_id"]]

    segments = sorted({r["reviewed_physical_id"] for r in matched})

    # Violations per (segment, day).
    violations_by_seg_day = defaultdict(int)
    for r in matched:
        pid = r["reviewed_physical_id"]
        day = r["violation_date"][:10]
        violations_by_seg_day[(pid, day)] += 1

    # Sweep visit-days per segment (distinct physical_id/date pairs), restricted
    # to the segments in our population.
    sweep_raw = json.loads((RAW_PILOT / "sweepnyc.json").read_text())
    seg_set = set(segments)
    visit_days_by_pid = defaultdict(set)
    for row in sweep_raw:
        pid = str(row["physical_id"])
        if pid not in seg_set:
            continue
        visit_days_by_pid[pid].add(row["date_visited"][:10])

    ever_swept = {pid: bool(visit_days_by_pid.get(pid)) for pid in segments}

    panel_rows = []
    for pid in segments:
        visits = visit_days_by_pid.get(pid, set())
        for d in AUGUST_DAYS:
            dstr = d.isoformat()
            panel_rows.append({
                "physical_id": pid,
                "date": dstr,
                "day_of_week": d.strftime("%a"),
                "swept": int(dstr in visits),
                "violation_count": violations_by_seg_day.get((pid, dstr), 0),
                "segment_ever_swept_in_august": int(ever_swept[pid]),
            })

    fieldnames = list(panel_rows[0])
    out_csv = OUT / "segment_day_panel.csv"
    with out_csv.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(panel_rows)

    n_segments = len(segments)
    n_swept_segments = sum(ever_swept.values())
    n_rows = len(panel_rows)
    n_swept_days = sum(r["swept"] for r in panel_rows)
    n_violations = sum(r["violation_count"] for r in panel_rows)

    summary = {
        "generated_from": "reviewed_matches.csv + sweepnyc.json (August 2026, Manhattan)",
        "segments": n_segments,
        "segments_with_at_least_one_august_visit": n_swept_segments,
        "segments_with_zero_august_visits": n_segments - n_swept_segments,
        "calendar_days": len(AUGUST_DAYS),
        "panel_rows_segment_x_day": n_rows,
        "swept_segment_days": n_swept_days,
        "unswept_segment_days": n_rows - n_swept_days,
        "total_eligible_violations_in_panel": n_violations,
        "scope_limits": [
            "Population is the 851 Manhattan segments already linked to an eligible "
            "OATH cleanliness violation in Phase 1 -- not a citywide or random sample.",
            "Outcome is OATH cleanliness violations only; 311 complaints and weather "
            "controls are not yet joined (no NYC Open Data network access from this "
            "environment).",
            "Single calendar month (August 2026).",
        ],
    }
    (OUT / "panel_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")

    inputs = [PROCESSED_ADJ / "reviewed_matches.csv", RAW_PILOT / "sweepnyc.json"]
    checksums = {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in inputs}
    (OUT / "checksums.json").write_text(json.dumps(checksums, indent=2), encoding="utf-8")

    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
