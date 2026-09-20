"""Render reference-only audit maps; no web basemap or frontend."""

import json, csv, sys, math, os, textwrap
from pathlib import Path

os.environ.setdefault(
    "MPLCONFIGDIR",
    str(Path(__file__).resolve().parents[1] / "data/processed/validation/.matplotlib"),
)
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from shapely.geometry import Point, box
from shapely.strtree import STRtree

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from sweepnyc.validation import AddressAudit, projected

OUT = ROOT / "data/processed/validation"
rows = json.loads((OUT / "evidence.json").read_text())
cs = json.loads((ROOT / "data/raw/validation/cscl_geometry.json").read_text())
items = [
    (str(r["physicalid"]), projected(r["the_geom"])) for r in cs if r.get("the_geom")
]
geoms = [g for _, g in items]
tree = STRtree(geoms)
by_id = dict(items)
sample_ids = {
    r["ticket_number"] for r in csv.DictReader((OUT / "sample_100.csv").open())
}
sample = sorted(
    [r for r in rows if r["ticket_number"] in sample_ids],
    key=lambda r: r["ticket_number"],
)


def render(group, path, title):
    fig, axes = plt.subplots(
        math.ceil(len(group) / 4),
        4,
        figsize=(16, 4.2 * math.ceil(len(group) / 4)),
        squeeze=False,
    )
    for ax, row in zip(axes.flat, group):
        pts = [
            projected({"type": "Point", "coordinates": [e["longitude"], e["latitude"]]})
            for e in row["evidence"]
        ]
        assigned = row["assigned_physical_id"]
        suggested = row["suggested_physical_id"]
        center = (
            pts[0] if pts else by_id[assigned].centroid if assigned in by_id else None
        )
        if center is not None:
            bounds = (center.x - 180, center.y - 180, center.x + 180, center.y + 180)
            for i in tree.query(box(*bounds)):
                pid, geom = items[i]
                color = (
                    "#e88d17"
                    if pid == assigned
                    else "#267e55" if pid == suggested else "#c9ced2"
                )
                width = 3 if pid in {assigned, suggested} else 1
                for line in geom.geoms if hasattr(geom, "geoms") else [geom]:
                    x, y = line.xy
                    ax.plot(x, y, color=color, lw=width)
                if pid in {assigned, suggested}:
                    mid = geom.centroid
                    ax.text(
                        mid.x, mid.y, pid, fontsize=8, color="#333333", clip_on=True
                    )
            for pt in pts:
                ax.scatter(pt.x, pt.y, c="#0c63bb", s=30, zorder=5)
            ax.set_xlim(bounds[0], bounds[2])
            ax.set_ylim(bounds[1], bounds[3])
            ax.set_aspect("equal")
        ax.set_title(
            row["ticket_number"]
            + " | "
            + textwrap.fill(row["house"] + " " + row["street"], width=35)
            + "\n"
            + row["audit_status"].replace("_", " "),
            fontsize=8,
        )
        ax.set_xticks([])
        ax.set_yticks([])
        if not pts:
            ax.text(
                0.5,
                0.12,
                "NO EXACT ADDRESS POINT",
                transform=ax.transAxes,
                ha="center",
                fontsize=9,
                color="#a00020",
            )
    for ax in list(axes.flat)[len(group) :]:
        ax.axis("off")
    fig.suptitle(
        title
        + "\nOrange: assigned segment | Blue: address point | Green: alternative suggestion | 360-ft map width",
        fontsize=13,
    )
    fig.subplots_adjust(top=0.87 if len(group) <= 8 else 0.94, bottom=0.025, hspace=0.38, wspace=0.20)
    fig.savefig(path, dpi=140)
    plt.close(fig)


for start in range(0, 100, 20):
    render(
        sample[start : start + 20],
        OUT / f"audit-map-sheet-{start//20+1}.png",
        f"100-record random sample: {start+1}-{start+20}",
    )
flags = [
    r
    for r in rows
    if r["audit_status"]
    in {"assignment_discrepancy", "assigned_segment_missing_current_reference"}
]
render(
    flags,
    OUT / "assignment-holds-map.png",
    "Five records held for conflicting or changed reference evidence",
)
print("Rendered five sample sheets and the assignment-holds sheet.")
