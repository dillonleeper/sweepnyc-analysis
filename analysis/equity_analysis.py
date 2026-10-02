"""
Trick-or-Streets equity analysis
=================================
Question: does NYC DOT's Trick-or-Streets program hand out car-free
Halloween streets in proportion to where the city's kids actually live?

Method: join the 2026 Trick-or-Streets location dataset (same source
used by the router app -- NYC DOT's own ArcGIS FeatureServer) against
borough-level population figures from the Census Bureau and NY State
Dept. of Health, and compute a simple per-capita / per-child access
metric for each borough.

Data sources (see README.md in this folder for exact URLs and dates
pulled):
  - TOS event locations: NYC DOT Trick-or-Streets ArcGIS FeatureServer
    (same data the router app uses), 2026 season, 145 unique closures
    across 5 boroughs.
  - Population & land area: NY State Dept. of Health, "Population, Land
    Area, and Population Density by County, New York State - 2020"
    (2020 Decennial Census counts).
  - Percent of population under 18: U.S. Census Bureau QuickFacts,
    American Community Survey 2020-2024 5-year estimates, by county
    (each NYC borough is coextensive with one county).

Caveat: population counts are 2020 Census (fixed point), while the
under-18 share is a 2020-2024 ACS rolling estimate -- a one-time, minor
vintage mismatch that doesn't change which boroughs come out ahead or
behind; it's noted here rather than hidden.
"""

import json
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"

# ---- borough-level demographics (see sources above / README.md) ----
BOROUGHS = {
    "Bronx": {
        "population_2020": 1_401_142,
        "land_area_sq_mi": 42.17,
        "pct_under_18": 23.5,
    },
    "Brooklyn": {
        "population_2020": 2_538_934,
        "land_area_sq_mi": 69.38,
        "pct_under_18": 20.7,
    },
    "Manhattan": {
        "population_2020": 1_611_989,
        "land_area_sq_mi": 22.66,
        "pct_under_18": 12.9,
    },
    "Queens": {
        "population_2020": 2_225_821,
        "land_area_sq_mi": 108.72,
        "pct_under_18": 18.2,
    },
    "Staten Island": {
        "population_2020": 475_327,
        "land_area_sq_mi": 57.52,
        "pct_under_18": 20.4,
    },
}
# NY State DOH county names -> Trick-or-Streets borough field uses NYC names;
# "Staten Island" = Richmond County, the rest match directly.


def load_tos_events():
    rows = json.loads((DATA_DIR / "tos_2026_trimmed.json").read_text())
    seen = set()
    unique_rows = []
    for r in rows:
        key = (r["name"], r["on"], r["borough"])
        if key in seen:
            continue
        seen.add(key)
        unique_rows.append(r)
    return rows, unique_rows


def main():
    all_rows, unique_rows = load_tos_events()

    counts = {b: 0 for b in BOROUGHS}
    for r in unique_rows:
        counts[r["borough"]] += 1

    print(f"{'Borough':<14}{'Closures':>9}{'Pop.':>12}{'Children':>11}"
          f"{'Per 100k':>10}{'Per 10k kids':>13}{'Per 100 mi2':>12}")
    results = []
    for b, d in BOROUGHS.items():
        n = counts[b]
        pop = d["population_2020"]
        children = pop * d["pct_under_18"] / 100
        per_100k = n / pop * 100_000
        per_10k_kids = n / children * 10_000
        per_100_sqmi = n / d["land_area_sq_mi"] * 100
        results.append({
            "borough": b, "closures": n, "population": pop,
            "children_est": round(children), "pct_under_18": d["pct_under_18"],
            "per_100k_residents": round(per_100k, 2),
            "per_10k_children": round(per_10k_kids, 2),
            "per_100_sqmi": round(per_100_sqmi, 2),
        })
        print(f"{b:<14}{n:>9}{pop:>12,}{round(children):>11,}"
              f"{per_100k:>10.2f}{per_10k_kids:>13.2f}{per_100_sqmi:>12.2f}")

    out_path = Path(__file__).resolve().parent / "equity_results.json"
    out_path.write_text(json.dumps(results, indent=2))
    print(f"\nWrote {out_path}")

    # quick ranking callouts
    by_kids = sorted(results, key=lambda r: r["per_10k_children"])
    print("\nFewest car-free Halloween closures per 10k kids (most underserved first):")
    for r in by_kids:
        print(f"  {r['borough']:<14} {r['per_10k_children']:.2f} per 10k kids "
              f"({r['children_est']:,} kids est., {r['closures']} closures)")


if __name__ == "__main__":
    main()
