"""Design-gap fix #2 (part 2): rerun the two-month fixed-effects models with a
daily rain control added.

Same four models and panel as run_effect_analysis_multi_month.py
(segment_day_panel_multi_month.csv), but each formula now also includes `rained`
(1 if Central Park recorded >=1.0mm precipitation that day, from
weather_daily.csv) alongside segment, day-of-week, and month fixed effects.
`rained` is a day-level variable shared by every segment on a given date, so it's
already partly absorbed by nothing else in the model (day-of-week FE doesn't
capture it, since rain isn't a weekly cycle) -- this is a real additional control,
not a redundant one.

Purpose: check whether the swept-coefficient estimates from the no-weather
version move once rainy days are accounted for. If they don't move, rain wasn't
the confound; if they do, the earlier estimates were partly picking up a
rain-driven correlation between sweep timing and reporting/enforcement behavior.
"""
import json
from pathlib import Path

import pandas as pd
import statsmodels.formula.api as smf

ROOT = Path(__file__).resolve().parent.parent
PANEL = ROOT / "data/processed/effect_analysis/segment_day_panel_multi_month.csv"
WEATHER = ROOT / "data/processed/effect_analysis/weather_daily.csv"
OUT = ROOT / "data/processed/effect_analysis"


def cluster_fe_ols(df, y, x, cluster="physical_id"):
    formula = f"{y} ~ {x} + rained + C(physical_id) + C(day_of_week) + C(month)"
    model = smf.ols(formula, data=df).fit(
        cov_type="cluster", cov_kwds={"groups": df[cluster]}
    )
    return {
        "coef": float(model.params[x]),
        "se": float(model.bse[x]),
        "p": float(model.pvalues[x]),
        "rained_coef": float(model.params["rained"]),
        "rained_p": float(model.pvalues["rained"]),
        "n_obs": int(model.nobs),
        "n_segments": int(df[cluster].nunique()),
    }


def main():
    df = pd.read_csv(PANEL, dtype={"physical_id": str})
    weather = pd.read_csv(WEATHER, parse_dates=["date"])
    df["date"] = pd.to_datetime(df["date"])
    df = df.merge(weather[["date", "rained", "prcp_mm"]], on="date", how="left")
    assert df["rained"].isna().sum() == 0, "every panel day should have a weather match"
    df = df.sort_values(["physical_id", "date"]).reset_index(drop=True)

    same_day = cluster_fe_ols(df, "violation_count", "swept")
    df["violation_count_next_day"] = df.groupby("physical_id")["violation_count"].shift(-1)
    lead_df = df.dropna(subset=["violation_count_next_day"]).copy()
    next_day = cluster_fe_ols(lead_df, "violation_count_next_day", "swept")

    same_day_311 = cluster_fe_ols(df, "complaint_311_count", "swept")
    df["complaint_311_count_next_day"] = df.groupby("physical_id")["complaint_311_count"].shift(-1)
    lead_df_311 = df.dropna(subset=["complaint_311_count_next_day"]).copy()
    next_day_311 = cluster_fe_ols(lead_df_311, "complaint_311_count_next_day", "swept")

    # Load the no-weather results for a direct before/after comparison.
    no_weather = json.loads((OUT / "effect_analysis_results_multi_month.json").read_text())

    def compare(no_weather_model, with_weather_result, label):
        return {
            "outcome": label,
            "coef_no_weather_control": no_weather_model["coef"],
            "p_no_weather_control": no_weather_model["p"],
            "coef_with_rain_control": with_weather_result["coef"],
            "p_with_rain_control": with_weather_result["p"],
            "rained_coefficient": with_weather_result["rained_coef"],
            "rained_p_value": with_weather_result["rained_p"],
        }

    results = {
        "panel": {
            "rows": int(len(df)),
            "days_with_rain": int(df.groupby("date")["rained"].first().sum()),
            "days_total": int(df["date"].nunique()),
        },
        "model_1_same_day": compare(no_weather["model_1_same_day_fixed_effects"], same_day, "same-day OATH violations"),
        "model_2_next_day": compare(no_weather["model_2_next_day_fixed_effects"], next_day, "next-day OATH violations"),
        "model_3_same_day_311": compare(no_weather["model_3_same_day_fixed_effects_311"], same_day_311, "same-day 311 complaints"),
        "model_4_next_day_311": compare(no_weather["model_4_next_day_fixed_effects_311"], next_day_311, "next-day 311 complaints"),
        "caveats": [
            "Weather is Central Park station data (nearest official daily record), "
            "applied uniformly to all Manhattan segments -- it does not capture "
            "neighborhood-level microclimate or localized storm variation.",
            "`rained` is a binary >=1.0mm threshold, not rainfall intensity or "
            "duration; a borderline choice, tested here as the simplest "
            "plausible confounder control rather than an exhaustively tuned one.",
            "This still doesn't add street-type controls (see "
            "matched_control_results.json for that design-gap fix) -- it only "
            "tests whether rain was biasing the day-level fixed-effects estimates.",
        ],
    }

    (OUT / "effect_analysis_results_with_weather.json").write_text(json.dumps(results, indent=2), encoding="utf-8")
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
