"""Render the Phase 2 event-time chart: mean violations by days-since-last-sweep.

Because recorded sweeps are frequent (median gap between two sweep-days on the
same segment is 1 day, per panel_summary.json), a classic symmetric event
window (-N..+N days around a sweep) would mostly overlap the next sweep. This
chart instead buckets every segment-day by how many days it has been since
that segment's most recent recorded sweep (0 = swept today), which stays
interpretable even when sweeps are frequent.
"""
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
PANEL = ROOT / "data/processed/effect_analysis/segment_day_panel.csv"
OUT = ROOT / "data/processed/effect_analysis"


def days_since_last_sweep(group):
    group = group.sort_values("date")
    last_sweep = pd.NaT
    out = []
    for _, row in group.iterrows():
        if row["swept"] == 1:
            last_sweep = row["date"]
        if pd.isna(last_sweep):
            out.append(np.nan)
        else:
            out.append((row["date"] - last_sweep).days)
    group = group.copy()
    group["days_since_sweep"] = out
    return group


def main():
    df = pd.read_csv(PANEL, dtype={"physical_id": str})
    df["date"] = pd.to_datetime(df["date"])
    df = df.groupby("physical_id", group_keys=False).apply(days_since_last_sweep)

    # Days 0-7+, dropping the undefined start-of-month days (no prior sweep observed yet).
    df = df.dropna(subset=["days_since_sweep"])
    df["bucket"] = df["days_since_sweep"].clip(upper=7).astype(int)

    stats = df.groupby("bucket")["violation_count"].agg(["mean", "count", "std"]).reset_index()
    stats["se"] = stats["std"] / np.sqrt(stats["count"])

    fig, ax = plt.subplots(figsize=(8, 5), dpi=150)
    labels = [str(b) if b < 7 else "7+" for b in stats["bucket"]]
    ax.bar(labels, stats["mean"], yerr=stats["se"], color="#2E6F5E", capsize=4, width=0.6)
    ax.set_xlabel("Days since this segment's last recorded sweep")
    ax.set_ylabel("Mean eligible violations / segment-day")
    ax.set_title("Violations vs. time since last recorded sweep\nManhattan, August 2026 (851 violation-linked segments)")
    ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    fig.savefig(OUT / "violations_by_days_since_sweep.png")

    stats_out = stats.to_dict(orient="records")
    (OUT / "days_since_sweep_stats.json").write_text(json.dumps(stats_out, indent=2, default=float), encoding="utf-8")
    print(json.dumps(stats_out, indent=2, default=float))


if __name__ == "__main__":
    main()
