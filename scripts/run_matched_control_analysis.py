"""Design-gap fix #1 (part 2): a genuine covariate-matched control comparison.

The segment fixed-effects models (run_effect_analysis*.py) compare each segment
against ITSELF on swept vs. unswept days -- that already controls for anything
time-invariant about the block (street width, lane count, etc.) perfectly, since
it never compares across segments. What it can't do is answer the OTHER question
this project has flagged as confounded since the first pass:

    "a segment with zero recorded sweeps may simply not be on an active sweeping
    route, not because it started out cleaner" (docs/phase2-effect-analysis-2026-09.md)

That is a cross-segment question -- do segments that get swept at all look
different, outcome-wise, from segments that never do -- and answering it without
real matching just compares two arbitrary groups. This script builds the matching
this project's docs have been calling for: nearest-neighbor matching of each
never-swept segment to its closest structurally-similar swept segment, using the
real street-type covariates from build_street_covariates.py (width, lane counts,
one-way/two-way, snow-plow-priority functional-class proxy, truck-route flag)
instead of comparing all 663 swept vs all 188 unswept segments unmatched.

Method: for each never-swept segment, compute standardized Euclidean distance
(z-scored streetwidth_ft, travel_lanes, total_lanes) to every ever-swept segment
that also matches EXACTLY on one_way and snow_priority (the two coarse categorical
proxies for street type) -- exact match on category, nearest neighbor within it.
Never-swept segments with no exact-category match are reported as unmatched, not
forced onto a poor match. Each matched pair contributes its two-month total
violation/311 counts; the estimate is the mean matched-pair difference
(swept-match minus never-swept), with a paired t-test / Wilcoxon signed-rank test
reported for reference -- not a substitute for the fixed-effects models, a second,
independent design answering a different question.

This is still a small-sample, single-population, observational comparison (see
caveats in the output) -- matching removes the "different street type" confound,
not the deeper "sweep routes are assigned administratively" one.
"""
import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data/processed/effect_analysis"


def main():
    panel = pd.read_csv(OUT / "segment_day_panel_multi_month.csv", dtype={"physical_id": str})
    cov = pd.read_csv(OUT / "segment_covariates.csv", dtype={"physical_id": str})

    seg_outcomes = panel.groupby("physical_id").agg(
        ever_swept=("swept", "max"),
        total_violations=("violation_count", "sum"),
        total_311=("complaint_311_count", "sum"),
        n_days=("date", "nunique"),
    ).reset_index()
    seg_outcomes["violations_per_day"] = seg_outcomes["total_violations"] / seg_outcomes["n_days"]
    seg_outcomes["complaints_311_per_day"] = seg_outcomes["total_311"] / seg_outcomes["n_days"]

    df = seg_outcomes.merge(cov, on="physical_id", how="inner")
    dropped_no_covariates = len(seg_outcomes) - len(df)

    treated = df[df.ever_swept == 1].copy()
    control = df[df.ever_swept == 0].copy()

    # Standardize continuous covariates on the treated (donor) pool.
    cont_cols = ["streetwidth_ft", "travel_lanes", "total_lanes"]
    means = treated[cont_cols].mean()
    stds = treated[cont_cols].std().replace(0, 1)

    def zscore(sub):
        return (sub[cont_cols] - means) / stds

    treated_z = zscore(treated)
    control_z = zscore(control)

    pairs = []
    unmatched = []
    for idx, row in control.iterrows():
        pool = treated[
            (treated.one_way == row.one_way) & (treated.snow_priority == row.snow_priority)
        ]
        if pool.empty:
            unmatched.append(row.physical_id)
            continue
        pool_z = treated_z.loc[pool.index]
        target = control_z.loc[idx]
        dist = np.sqrt(((pool_z - target) ** 2).sum(axis=1))
        best_idx = dist.idxmin()
        best = treated.loc[best_idx]
        pairs.append({
            "control_physical_id": row.physical_id,
            "matched_swept_physical_id": best.physical_id,
            "distance": float(dist.loc[best_idx]),
            "control_violations_per_day": float(row.violations_per_day),
            "matched_violations_per_day": float(best.violations_per_day),
            "control_311_per_day": float(row.complaints_311_per_day),
            "matched_311_per_day": float(best.complaints_311_per_day),
            "control_streetwidth_ft": float(row.streetwidth_ft),
            "matched_streetwidth_ft": float(best.streetwidth_ft),
            "control_travel_lanes": int(row.travel_lanes),
            "matched_travel_lanes": int(best.travel_lanes),
            "one_way": int(row.one_way),
            "snow_priority": row.snow_priority,
        })

    pairs_df = pd.DataFrame(pairs)

    n_unique_donors = pairs_df["matched_swept_physical_id"].nunique()
    donor_reuse_top3 = (
        pairs_df["matched_swept_physical_id"].value_counts().head(3).to_dict()
    )

    def paired_stats(control_col, matched_col, label):
        diffs = pairs_df[matched_col] - pairs_df[control_col]
        t_stat, t_p = stats.ttest_rel(pairs_df[matched_col], pairs_df[control_col])
        try:
            w_stat, w_p = stats.wilcoxon(pairs_df[matched_col], pairs_df[control_col])
        except ValueError:
            w_stat, w_p = float("nan"), float("nan")

        # Donor-reuse check: the naive test above treats each never-swept
        # segment as an independent observation, but with only 52 unique
        # donor (swept) segments matched to 186 controls, many pairs share the
        # same donor -- those pairs are NOT independent draws of "a swept
        # segment's outcome." Collapsing to one row per unique donor (control
        # side averaged across whichever never-swept segments matched it) is
        # the conservative version of this test, at the actual independent
        # sample size.
        donor_collapsed = pairs_df.groupby("matched_swept_physical_id").agg(
            **{matched_col: (matched_col, "first"), control_col: (control_col, "mean")}
        )
        dc_t, dc_p = stats.ttest_rel(donor_collapsed[matched_col], donor_collapsed[control_col])

        return {
            "outcome": label,
            "n_pairs": int(len(pairs_df)),
            "mean_never_swept": round(float(pairs_df[control_col].mean()), 4),
            "mean_matched_swept": round(float(pairs_df[matched_col].mean()), 4),
            "mean_paired_difference_swept_minus_never_swept": round(float(diffs.mean()), 4),
            "naive_paired_ttest": {
                "note": "treats all 186 pairs as independent -- overstated, see donor reuse below",
                "t": round(float(t_stat), 4),
                "p": round(float(t_p), 4),
                "wilcoxon_p": round(float(w_p), 4) if w_p == w_p else None,
            },
            "donor_collapsed_paired_ttest": {
                "note": (
                    f"one row per unique donor segment (n={n_unique_donors}), "
                    "the conservative test at the true independent sample size"
                ),
                "t": round(float(dc_t), 4),
                "p": round(float(dc_p), 4),
            },
            "interpretation": (
                f"Across {len(pairs_df)} matched pairs, swept segments average "
                f"{diffs.mean():+.4f} {label} per day relative to their "
                f"never-swept match (naive paired t-test p={t_p:.3f}, but "
                f"donor-collapsed p={dc_p:.3f} once the {n_unique_donors} "
                f"unique donor segments -- not 186 -- are treated as the "
                f"sample size)."
            ),
        }

    results = {
        "population": {
            "total_segments_in_population": int(len(seg_outcomes)),
            "dropped_no_covariates": int(dropped_no_covariates),
            "ever_swept_donor_pool": int(len(treated)),
            "never_swept_to_match": int(len(control)),
            "matched_pairs": int(len(pairs_df)),
            "unmatched_no_exact_category": len(unmatched),
            "unique_donor_segments_used": int(n_unique_donors),
            "top_3_donor_reuse_counts": {str(k): int(v) for k, v in donor_reuse_top3.items()},
        },
        "matching_method": (
            "Exact match on one_way (trafdir TW vs FT/TF) and snow_priority "
            "(H/C/S, used as functional-class proxy -- CSCL's fcc field is null "
            "for this extract), then nearest-neighbor by Euclidean distance on "
            "z-scored streetwidth_ft, travel_lanes, and total_lanes within that "
            "exact-match pool. No replacement restriction: the same swept "
            "segment can be the closest match for more than one never-swept "
            "segment."
        ),
        "violations_result": paired_stats("control_violations_per_day", "matched_violations_per_day", "eligible violations"),
        "complaints_311_result": paired_stats("control_311_per_day", "matched_311_per_day", "311 complaints"),
        "caveats": [
            f"Donor reuse: only {n_unique_donors} unique swept segments serve "
            "as the nearest-neighbor match for all 186 never-swept segments "
            "(the busiest donor is reused for dozens of pairs) -- the naive "
            "186-pair paired test substantially overstates the independent "
            "sample size. The donor-collapsed test above (true n = number of "
            "unique donors) is the more honest read; where it disagrees with "
            "the naive test, trust the collapsed one.",
            "This answers a different question than the fixed-effects models: "
            "'do segments that are ever swept differ, outcome-wise, from "
            "structurally similar segments that are never swept' -- not "
            "'does sweeping on a given day reduce same-day violations.' It is "
            "still confounded by anything the covariates don't capture "
            "(administrative route assignment, unobserved neighborhood "
            "factors) and by reverse causality: DSNY may route sweepers toward "
            "streets it already expects to need it.",
            "Small control pool: only 188 never-swept segments in this "
            "population, all from one borough and restricted to segments "
            "already linked to >=1 August violation in Phase 1 -- not a "
            "citywide or random comparison.",
            f"{len(unmatched)} never-swept segments had no exact-category "
            "match (same one_way + snow_priority) among the swept pool and "
            "were dropped rather than force-matched.",
            f"{dropped_no_covariates} segments (of {len(seg_outcomes)}) had no "
            "usable street-covariate record and were excluded entirely.",
        ],
    }

    (OUT / "matched_control_results.json").write_text(json.dumps(results, indent=2), encoding="utf-8")
    pairs_df.to_csv(OUT / "matched_control_pairs.csv", index=False)
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
