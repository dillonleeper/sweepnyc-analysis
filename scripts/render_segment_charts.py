"""Render the three charts for docs/segment-analysis-2026-08.md from the
built segment table. Read-only against data/processed/segment_analysis/
manhattan_segment_table.csv; writes PNGs to the same directory."""
import csv
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data/processed/segment_analysis"

COLOR_WITH_OBS = "#2E6F95"
COLOR_NO_OBS = "#C1440E"
TEXT = "#1a1a1a"
MUTED = "#6b6b6b"

plt.rcParams.update({
    "font.size": 11,
    "axes.edgecolor": "#cccccc",
    "axes.labelcolor": TEXT,
    "text.color": TEXT,
    "xtick.color": MUTED,
    "ytick.color": TEXT,
    "figure.facecolor": "white",
    "axes.facecolor": "white",
})


def make_bar(data, title, color, filename, subtitle):
    data = sorted(data, key=lambda r: int(r["eligible_violation_count"]))[-15:]
    labels = [f"{r['representative_street_name'].title()} (id {r['reviewed_physical_id']})" for r in data]
    values = [int(r["eligible_violation_count"]) for r in data]

    fig, ax = plt.subplots(figsize=(9.5, 6.5))
    bars = ax.barh(labels, values, color=color, height=0.62)
    for bar, v in zip(bars, values):
        ax.text(bar.get_width() + 0.3, bar.get_y() + bar.get_height() / 2, str(v),
                va="center", ha="left", fontsize=10, color=TEXT)
    ax.set_xlabel("Eligible August violations linked to this segment")
    ax.set_title(title, fontsize=13, fontweight="bold", loc="left", pad=26)
    fig.text(0.08, 0.93, subtitle, fontsize=9.5, color=MUTED, ha="left")
    ax.spines[["top", "right"]].set_visible(False)
    ax.spines[["left", "bottom"]].set_color("#cccccc")
    ax.tick_params(axis="y", length=0)
    ax.set_xlim(0, max(values) * 1.15)
    fig.tight_layout(rect=[0, 0, 1, 0.90])
    fig.savefig(OUT / filename, dpi=150)
    plt.close(fig)


def main():
    rows = list(csv.DictReader((OUT / "manhattan_segment_table.csv").open(encoding="utf-8")))
    with_obs = [r for r in rows if r["has_august_observation"] == "True"]
    no_obs = [r for r in rows if r["has_august_observation"] == "False"]

    make_bar(
        with_obs,
        "Segments with the most violations despite a recorded August sweep",
        COLOR_WITH_OBS,
        "top_violations_with_sweep_observation.png",
        "Violation-linked Manhattan segments only, not a citywide ranking. A recorded sweep is not proof of cleaning outcome.",
    )
    make_bar(
        no_obs,
        "Segments with violations but no recorded August sweep observation",
        COLOR_NO_OBS,
        "top_violations_no_sweep_observation.png",
        "Violation-linked Manhattan segments only. Absence of a record does not prove no service occurred; it means SweepNYC recorded none.",
    )

    bins = [1, 2, 3, 5, 8, 15, max(int(r["eligible_violation_count"]) for r in rows) + 1]
    bin_labels = ["1", "2", "3-4", "5-7", "8-14", "15+"]

    def bin_of(v):
        for i in range(len(bins) - 1):
            if bins[i] <= v < bins[i + 1]:
                return i
        return len(bins) - 2

    with_counts = [0] * len(bin_labels)
    no_counts = [0] * len(bin_labels)
    for r in rows:
        b = bin_of(int(r["eligible_violation_count"]))
        (with_counts if r["has_august_observation"] == "True" else no_counts)[b] += 1

    fig, ax = plt.subplots(figsize=(9.5, 5.5))
    x = range(len(bin_labels))
    width = 0.38
    ax.bar([i - width / 2 for i in x], with_counts, width, label="Has an August sweep observation", color=COLOR_WITH_OBS)
    ax.bar([i + width / 2 for i in x], no_counts, width, label="No August sweep observation", color=COLOR_NO_OBS)
    ax.set_xticks(list(x))
    ax.set_xticklabels(bin_labels)
    ax.set_xlabel("Eligible violations linked to the segment")
    ax.set_ylabel("Number of segments")
    ax.set_title("How violations concentrate across violation-linked segments", fontsize=13, fontweight="bold", loc="left", pad=26)
    fig.text(0.08, 0.93, f"{len(rows)} Manhattan segments with at least one eligible August violation.", fontsize=9.5, color=MUTED, ha="left")
    ax.spines[["top", "right"]].set_visible(False)
    ax.legend(frameon=False, loc="upper right")
    fig.tight_layout(rect=[0, 0, 1, 0.90])
    fig.savefig(OUT / "violation_count_distribution.png", dpi=150)
    plt.close(fig)
    print("charts written to", OUT)


if __name__ == "__main__":
    main()
