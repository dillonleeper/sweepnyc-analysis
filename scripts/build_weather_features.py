"""Design-gap fix #2: daily weather as a covariate.

Rain is a plausible common cause of both sides of the same-day 311/OATH models:
it can change how much litter accumulates and independently change how likely a
resident is to go outside and notice/report it, or an inspector is out writing
tickets. It doesn't need to affect whether a sweep happened (that's already
observed directly in the `swept` column) to still confound the swept-coefficient
if rainy days happen to cluster with certain sweep schedules.

Source: NOAA NCEI GHCN-Daily, station USW00094728 (Central Park, NYC) -- the
standard official daily-weather reference station for Manhattan. Fetched via the
same browser-fetch technique used for OATH/311/sweep (data/raw/phase2/
weather_central_park.json, see data/raw/phase2/design_gap_manifest.json).

Output: data/processed/effect_analysis/weather_daily.csv, one row per day
(2026-07-01 through 2026-08-31): date, tmax_c, tmin_c, prcp_mm, rained (1 if
prcp_mm >= 1.0mm, a standard "measurable precipitation" threshold, else 0).
"""
import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW_PHASE2 = ROOT / "data/raw/phase2"
OUT = ROOT / "data/processed/effect_analysis"

RAIN_THRESHOLD_MM = 1.0


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    records = json.loads((RAW_PHASE2 / "weather_central_park.json").read_text())

    rows = []
    for r in records:
        prcp = float(r["PRCP"])
        rows.append({
            "date": r["DATE"],
            "tmax_c": float(r["TMAX"]),
            "tmin_c": float(r["TMIN"]),
            "prcp_mm": prcp,
            "rained": int(prcp >= RAIN_THRESHOLD_MM),
        })
    rows.sort(key=lambda r: r["date"])

    out_csv = OUT / "weather_daily.csv"
    with out_csv.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

    n_rain_days = sum(r["rained"] for r in rows)
    print(json.dumps({
        "days": len(rows),
        "date_range": [rows[0]["date"], rows[-1]["date"]],
        "rain_threshold_mm": RAIN_THRESHOLD_MM,
        "days_with_measurable_precipitation": n_rain_days,
        "output": str(out_csv),
    }, indent=2))


if __name__ == "__main__":
    main()
