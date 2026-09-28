"""Build the PhysicalID-level table of eligible violations vs. August
SweepNYC visit-days for Manhattan, August 2026.

Visit-day definition: SweepNYC's own field description says `date_visited`
is "the GPS signal ... during that segment's allowed sweep time frame," and
the dataset's stated grain is one observation per segment/day. In practice
13,333 of 451,085+13,333=464,418 raw records (about 2.9%) share a
(physical_id, calendar date) pair with another record that same day, most a
few minutes to a few hours apart -- plausibly two curb-side sweep passes
sharing one PhysicalID, or an artifact of the GPS association process; the
data does not let us tell which. Per the project's instruction that
"duplicate observations must not become extra visits," a visit is defined
here as a distinct (physical_id, calendar date) pair: a segment either has
or does not have a recorded sweep on a given day. This is a lower bound on
the number of physical sweeper passes, and a same-day double-observation is
never counted as two visits.

Population: only PhysicalIDs (reviewed vintage) linked to at least one
eligible August violation. This is the violation-linked segment population,
not all Manhattan street segments -- most Manhattan segments are not in
this table at all, and its absence says nothing about their cleanliness or
service level.
"""
import csv
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PROCESSED_ADJ = ROOT / "data/processed/adjudication"
RAW_PILOT = ROOT / "data/raw/pilot"
OUT = ROOT / "data/processed/segment_analysis"


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    rows = list(csv.DictReader((PROCESSED_ADJ / "reviewed_matches.csv").open(encoding="utf-8")))
    sweep = json.loads((RAW_PILOT / "sweepnyc.json").read_text())

    # Visit-day table: distinct (physical_id, date) pairs.
    visit_days_by_pid = defaultdict(set)
    raw_record_count = Counter()
    for r in sweep:
        pid = r["physical_id"]
        date = r["date_visited"][:10]
        visit_days_by_pid[pid].add(date)
        raw_record_count[pid] += 1

    same_day_duplicate_records = sum(
        raw_record_count[pid] - len(visit_days_by_pid[pid]) for pid in raw_record_count
    )

    # Violation-linked segments only (reviewed_physical_id set).
    matched = [r for r in rows if r["reviewed_physical_id"]]
    by_segment = defaultdict(list)
    for r in matched:
        by_segment[r["reviewed_physical_id"]].append(r)

    segment_rows = []
    for pid, recs in sorted(by_segment.items(), key=lambda kv: -len(kv[1])):
        street_names = Counter(r["violation_location_street_name"] for r in recs)
        original_ids = sorted({r["matched_physical_id"] for r in recs})
        visit_dates = sorted(visit_days_by_pid.get(pid, set()))
        segment_rows.append({
            "reviewed_physical_id": pid,
            "original_physical_id": original_ids[0] if len(original_ids) == 1 else ";".join(original_ids),
            "id_was_corrected": original_ids != [pid],
            "representative_street_name": street_names.most_common(1)[0][0],
            "eligible_violation_count": len(recs),
            "ticket_numbers": ";".join(sorted(r["ticket_number"] for r in recs)),
            "august_visit_day_count": len(visit_dates),
            "august_raw_observation_count": raw_record_count.get(pid, 0),
            "first_august_visit_date": visit_dates[0] if visit_dates else "",
            "last_august_visit_date": visit_dates[-1] if visit_dates else "",
            "has_august_observation": len(visit_dates) > 0,
        })

    fieldnames = list(segment_rows[0])
    with (OUT / "manhattan_segment_table.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(segment_rows)

    no_observation = [s for s in segment_rows if not s["has_august_observation"]]
    with_observation = [s for s in segment_rows if s["has_august_observation"]]
    summary = {
        "distinct_violation_linked_segments": len(segment_rows),
        "segments_with_no_august_observation": len(no_observation),
        "segments_with_august_observation": len(with_observation),
        "eligible_violations_on_violation_linked_segments": sum(s["eligible_violation_count"] for s in segment_rows),
        "sweepnyc_raw_record_count_total": len(sweep),
        "sweepnyc_distinct_segment_day_visits_total": sum(len(v) for v in visit_days_by_pid.values()),
        "sweepnyc_same_day_duplicate_records_collapsed": same_day_duplicate_records,
        "sweepnyc_distinct_physical_ids_citywide_august": len(visit_days_by_pid),
        "visit_definition": (
            "A visit is a distinct (physical_id, calendar date) pair from the August "
            "SweepNYC extract. Multiple same-day GPS associations for one segment are "
            "collapsed into a single visit-day, not counted as separate visits."
        ),
        "population_note": (
            "This table covers only the segments linked to at least one eligible "
            "August OATH violation via the reviewed matcher output. It is not a "
            "citywide or all-Manhattan segment population."
        ),
    }
    (OUT / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")

    inputs = [PROCESSED_ADJ / "reviewed_matches.csv", RAW_PILOT / "sweepnyc.json"]
    checksums = {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in inputs}
    (OUT / "checksums.json").write_text(json.dumps(checksums, indent=2), encoding="utf-8")

    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
