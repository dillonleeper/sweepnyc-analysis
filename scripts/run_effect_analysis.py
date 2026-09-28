"""Phase 2, first pass: does a recorded sweep predict fewer violations?

Two models on the segment x day panel (data/processed/effect_analysis/segment_day_panel.csv):

  1. Same-day two-way fixed-effects (segment + day-of-week):
       violation_count[i,t] ~ swept[i,t] + segment_i + dow_t
     Segment-clustered standard errors. Segment FE absorbs each block's
     baseline dirtiness/enforcement level; day-of-week FE absorbs citywide
     weekday patterns (e.g. more inspectors out on weekdays).

  2. Next-day lead version, to ask whether a sweep predicts fewer violations
     the following day rather than just the same day:
       violation_count[i,t+1] ~ swept[i,t] + segment_i + dow_t

  3. A plain descriptive comparison (no controls): mean violations/day on
     swept-days vs unswept-days, and on segments with >=1 August sweep visit
     vs segments with zero -- reported for plain-language framing, but this
     one is NOT adjusted for anything and is confounded by which segments
     get swept at all (a segment with zero recorded visits may just not be
     on a sweeping route, not because it's already clean).

Why fixed effects and not covariate-matched controls: building genuine
matched controls (nearest-neighbor on street width, class, typical traffic,
etc.) needs a covariate set this project hasn't joined in yet -- CSCL alone
doesn't carry a service-need proxy. Segment fixed effects are the more
defensible design available right now: every segment is compared only
against itself on other days, which controls for anything about the block
that doesn't change during August (width, block length, neighborhood).
Note from the panel build: the median gap between two recorded sweep-days
on the same segment is 1 day (sweeps are frequent), so a classic
before/after event window would mostly overlap the next sweep -- that's why
this uses the panel regression instead of an isolated pre/post window.
"""
import json
from pathlib import Path

import numpy as np
import pandas as pd
import statsmodels.formula.api as smf

ROOT = Path(__file__).resolve().parent.parent
PANEL = ROOT / "data/processed/effect_analysis/segment_day_panel.csv"
OUT = ROOT / "data/processed/effect_analysis"


def cluster_fe_ols(df, y, x, cluster="physical_id"):
    formula = f"{y} ~ {x} + C(physical_id) + C(day_of_week)"
    model = smf.ols(formula, data=df).fit(
        cov_type="cluster", cov_kwds={"groups": df[cluster]}
    )
    return {
        "coef": float(model.params[x]),
        "se": float(model.bse[x]),
        "t": float(model.tvalues[x]),
        "p": float(model.pvalues[x]),
        "n_obs": int(model.nobs),
        "n_segments": int(df[cluster].nunique()),
    }


def main():
    df = pd.read_csv(PANEL, dtype={"physical_id": str})
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values(["physical_id", "date"]).reset_index(drop=True)

    # --- Descriptive, unadjusted comparisons ---------------------------------
    swept_mean = df.loc[df.swept == 1, "violation_count"].mean()
    unswept_mean = df.loc[df.swept == 0, "violation_count"].mean()

    seg_means = df.groupby("physical_id").agg(
        ever_swept=("segment_ever_swept_in_august", "max"),
        mean_daily_violations=("violation_count", "mean"),
    )
    ever_swept_mean = seg_means.loc[seg_means.ever_swept == 1, "mean_daily_violations"].mean()
    never_swept_mean = seg_means.loc[seg_means.ever_swept == 0, "mean_daily_violations"].mean()

    descriptive = {
        "mean_violations_per_day_on_swept_days": round(float(swept_mean), 4),
        "mean_violations_per_day_on_unswept_days": round(float(unswept_mean), 4),
        "mean_daily_violations_segments_ever_swept_in_august": round(float(ever_swept_mean), 4),
        "mean_daily_violations_segments_never_swept_in_august": round(float(never_swept_mean), 4),
        "caveat": (
            "Unadjusted. The ever-swept vs never-swept comparison is confounded: "
            "a segment with zero recorded August sweeps may simply not be on an "
            "active sweeping route, not because it started out cleaner. Not causal evidence."
        ),
    }

    # --- Model 1: same-day two-way fixed effects -----------------------------
    same_day = cluster_fe_ols(df, "violation_count", "swept")

    # --- Model 2: next-day lead, two-way fixed effects -----------------------
    df["violation_count_next_day"] = df.groupby("physical_id")["violation_count"].shift(-1)
    lead_df = df.dropna(subset=["violation_count_next_day"]).copy()
    next_day = cluster_fe_ols(lead_df, "violation_count_next_day", "swept")

    results = {
        "panel": {
            "rows": int(len(df)),
            "segments": int(df.physical_id.nunique()),
            "days": int(df.date.nunique()),
            "median_gap_between_sweep_visits_days": 1,
        },
        "descriptive_unadjusted": descriptive,
        "model_1_same_day_fixed_effects": {
            "spec": "violation_count[i,t] ~ swept[i,t] + segment FE + day-of-week FE, clustered SE by segment",
            **same_day,
            "interpretation": (
                f"On the same day, a recorded sweep is associated with "
                f"{same_day['coef']:+.4f} eligible violations per segment-day "
                f"(p={same_day['p']:.3f}), holding the segment and day-of-week fixed."
            ),
        },
        "model_2_next_day_fixed_effects": {
            "spec": "violation_count[i,t+1] ~ swept[i,t] + segment FE + day-of-week FE, clustered SE by segment",
            **next_day,
            "interpretation": (
                f"A sweep today is associated with {next_day['coef']:+.4f} eligible "
                f"violations on the segment the next day (p={next_day['p']:.3f}), "
                f"holding the segment and day-of-week fixed."
            ),
        },
        "caveats": [
            "One calendar month, one borough, and only the violation-linked segment "
            "population -- not a citywide or random sample.",
            "This is an observational association, not a randomized experiment. "
            "Sweep schedules are administratively fixed rather than assigned by "
            "current street condition, which weakens (but does not eliminate) "
            "reverse-causality concerns.",
            "OATH violations depend on an inspector being present, so this measures "
            "enforcement-observed cleanliness, not litter volume directly.",
            "311 complaints and weather/street-type controls are not yet joined in.",
        ],
    }

    (OUT / "effect_analysis_results.json").write_text(json.dumps(results, indent=2), encoding="utf-8")
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
