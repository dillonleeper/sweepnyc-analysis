"""Phase 2, two-month extension: does a recorded sweep predict fewer violations
or complaints, across July + August 2026?

Same models and rationale as run_effect_analysis.py, run on the two-month
panel (data/processed/effect_analysis/segment_day_panel_multi_month.csv)
instead of August alone, with a month fixed effect added
(C(month) alongside C(physical_id) and C(day_of_week)) to absorb any
systematic July-vs-August difference (e.g. weather, seasonal enforcement
patterns) that would otherwise leak into the swept coefficient.

Read docs/phase2-effect-analysis-2026-09.md before treating this as a
stronger result than the August-only pass: July's OATH violations are
automated-match-only (scripts/match_oath_month.py), NOT manually reviewed
like August's reviewed_matches.csv. Extending the sample size is the point
of this pass, but it comes with that asymmetry baked in.
"""
import json
from pathlib import Path

import pandas as pd
import statsmodels.formula.api as smf

ROOT = Path(__file__).resolve().parent.parent
PANEL = ROOT / "data/processed/effect_analysis/segment_day_panel_multi_month.csv"
OUT = ROOT / "data/processed/effect_analysis"


def cluster_fe_ols(df, y, x, cluster="physical_id"):
    formula = f"{y} ~ {x} + C(physical_id) + C(day_of_week) + C(month)"
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

    swept_mean = df.loc[df.swept == 1, "violation_count"].mean()
    unswept_mean = df.loc[df.swept == 0, "violation_count"].mean()
    swept_311_mean = df.loc[df.swept == 1, "complaint_311_count"].mean()
    unswept_311_mean = df.loc[df.swept == 0, "complaint_311_count"].mean()

    descriptive = {
        "mean_violations_per_day_on_swept_days": round(float(swept_mean), 4),
        "mean_violations_per_day_on_unswept_days": round(float(unswept_mean), 4),
        "mean_311_complaints_per_day_on_swept_days": round(float(swept_311_mean), 4),
        "mean_311_complaints_per_day_on_unswept_days": round(float(unswept_311_mean), 4),
        "total_311_complaints_in_panel": int(df["complaint_311_count"].sum()),
        "segments_with_at_least_one_311_hit": int(
            df.groupby("physical_id")["complaint_311_count"].max().gt(0).sum()
        ),
        "caveat": "Unadjusted. See fixed-effects models below for the controlled comparison.",
    }

    same_day = cluster_fe_ols(df, "violation_count", "swept")
    df["violation_count_next_day"] = df.groupby("physical_id")["violation_count"].shift(-1)
    lead_df = df.dropna(subset=["violation_count_next_day"]).copy()
    next_day = cluster_fe_ols(lead_df, "violation_count_next_day", "swept")

    same_day_311 = cluster_fe_ols(df, "complaint_311_count", "swept")
    df["complaint_311_count_next_day"] = df.groupby("physical_id")["complaint_311_count"].shift(-1)
    lead_df_311 = df.dropna(subset=["complaint_311_count_next_day"]).copy()
    next_day_311 = cluster_fe_ols(lead_df_311, "complaint_311_count_next_day", "swept")

    results = {
        "panel": {
            "rows": int(len(df)),
            "segments": int(df.physical_id.nunique()),
            "days": int(df.date.nunique()),
            "months": sorted(df["month"].unique().tolist()),
        },
        "descriptive_unadjusted": descriptive,
        "model_1_same_day_fixed_effects": {
            "spec": "violation_count[i,t] ~ swept[i,t] + segment FE + day-of-week FE + month FE, clustered SE by segment",
            **same_day,
            "interpretation": (
                f"On the same day, a recorded sweep is associated with "
                f"{same_day['coef']:+.4f} eligible violations per segment-day "
                f"(p={same_day['p']:.3f}), holding segment, day-of-week, and month fixed."
            ),
        },
        "model_2_next_day_fixed_effects": {
            "spec": "violation_count[i,t+1] ~ swept[i,t] + segment FE + day-of-week FE + month FE, clustered SE by segment",
            **next_day,
            "interpretation": (
                f"A sweep today is associated with {next_day['coef']:+.4f} eligible "
                f"violations on the segment the next day (p={next_day['p']:.3f})."
            ),
        },
        "model_3_same_day_fixed_effects_311": {
            "spec": "complaint_311_count[i,t] ~ swept[i,t] + segment FE + day-of-week FE + month FE, clustered SE by segment",
            **same_day_311,
            "interpretation": (
                f"On the same day, a recorded sweep is associated with "
                f"{same_day_311['coef']:+.4f} eligible 311 complaints per segment-day "
                f"(p={same_day_311['p']:.3f})."
            ),
        },
        "model_4_next_day_fixed_effects_311": {
            "spec": "complaint_311_count[i,t+1] ~ swept[i,t] + segment FE + day-of-week FE + month FE, clustered SE by segment",
            **next_day_311,
            "interpretation": (
                f"A sweep today is associated with {next_day_311['coef']:+.4f} eligible "
                f"311 complaints on the segment the next day (p={next_day_311['p']:.3f})."
            ),
        },
        "caveats": [
            "Two calendar months (July+August 2026), one borough, and only the "
            "violation-linked segment population -- not a citywide or random sample.",
            "IMPORTANT ASYMMETRY: August's OATH violations are Phase 1's fully "
            "manually reviewed reviewed_matches.csv (case review, LION-gap "
            "resolution, spatial corroboration). July's OATH violations are "
            "automated-match-only (scripts/match_oath_month.py) -- the same "
            "first-pass method Phase 1 started from before its human review, not "
            "reviewed the same way. July's OATH counts are therefore "
            "lower-confidence than August's. 311 matching used the identical "
            "automated method for both months, so the 311 columns ARE directly "
            "comparable across July and August.",
            "This is an observational association, not a randomized experiment.",
            "OATH violations depend on an inspector being present; 311 complaints "
            "depend on a resident noticing and reporting -- different noise "
            "sources, which is why both are reported rather than one alone.",
            "Weather and street-type controls are still not joined in.",
        ],
    }

    (OUT / "effect_analysis_results_multi_month.json").write_text(
        json.dumps(results, indent=2), encoding="utf-8"
    )
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
