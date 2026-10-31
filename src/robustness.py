"""Robustness checks 1-9 from analysis_plan.md section 5.

Each check refits the primary Bayesian model with one change and reports the
focal coefficient (`mid_dev_w`, or the swapped-in exposure). FDR uses the
matching GEE p-values, since the Bayesian fits give no p-value.
Leave-one-person-out (8) and missingness (7) use GEE only: 53 MCMC refits are
not worth it for a range, and (7) has a different outcome.

Usage: python src/robustness.py data/interim/panel.parquet reports/robustness.csv
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import statsmodels.api as sm
import statsmodels.formula.api as smf
from statsmodels.stats.multitest import multipletests

sys.path.insert(0, str(Path(__file__).parent))
from build_panel import BSON, build  # noqa: E402
from ema import daily_outcomes, load_mood  # noqa: E402
from models import GEE, MAIN, fit_bayes, fit_gee, prepare  # noqa: E402
from sleep import add_exposures, load_main_sleep  # noqa: E402


def winsor99(x):
    return x.clip(upper=x.quantile(0.99))


def focal(p, formula=MAIN, gee_formula=GEE, label=""):
    _, idata = fit_bayes(p, formula)
    b = idata.posterior["mid_dev_w"].values.ravel()
    g = fit_gee(p, gee_formula)
    row = {"check": label, "n_days": len(p), "n_users": p["uid"].nunique(),
           "OR": np.exp(np.median(b)), "OR_lo": np.exp(np.quantile(b, 0.025)),
           "OR_hi": np.exp(np.quantile(b, 0.975)), "P(beta>0)": (b > 0).mean(),
           "gee_p": g.pvalues["mid_dev_w"]}
    print(row, flush=True)
    return row


def report_level(min_nights=4):
    """Check 3: every mood report, nested in day in person."""
    sleep = add_exposures(load_main_sleep(BSON / "fitbit/sleep.parquet"), min_nights=min_nights)
    e = load_mood(BSON / "sema/context_and_mood_survey.parquet")
    p = e.merge(sleep, left_on=["uid", "day"], right_on=["uid", "night"])
    p["weekend"] = (p["day"].dt.day_of_week >= 5).astype(int)
    p["study_week"] = (p["day"] - p.groupby("uid")["day"].transform("min")).dt.days // 7
    p = prepare(p)
    p["uid_day"] = p["uid"] + "_" + p["day"].dt.strftime("%Y%m%d")
    return p


def missingness():
    """Check 7: does yesterday's TIRED predict today's missing report / tonight's missing sleep?

    Built on each person's full calendar span, not the analysis panel (which only
    holds days that already have both a report and a night).
    """
    days = daily_outcomes(load_mood(BSON / "sema/context_and_mood_survey.parquet"))
    nights = load_main_sleep(BSON / "fitbit/sleep.parquet")
    rows = []
    for uid, g in days.groupby("uid"):
        g = g.set_index("day")["tired"].asfreq("D")
        slept = set(nights.loc[nights["uid"] == uid, "night"])
        rows.append(pd.DataFrame({
            "uid": uid,
            "tired_prev": g.shift(1),
            "has_report": g.notna().astype(int),
            # the night after day d carries dateOfSleep d+1
            "has_sleep_next": [int(d + pd.Timedelta(days=1) in slept) for d in g.index],
        }))
    m = pd.concat(rows).dropna(subset=["tired_prev"])
    out = []
    for y in ["has_report", "has_sleep_next"]:
        f = smf.gee(f"{y} ~ tired_prev", groups="uid", data=m, family=sm.families.Binomial(),
                    cov_struct=sm.cov_struct.Exchangeable()).fit()
        out.append({"check": f"7 missingness: {y} ~ tired_prev", "n_days": len(m),
                    "OR": np.exp(f.params["tired_prev"]),
                    "OR_lo": np.exp(f.conf_int().loc["tired_prev", 0]),
                    "OR_hi": np.exp(f.conf_int().loc["tired_prev", 1]), "gee_p": f.pvalues["tired_prev"]})
        print(out[-1], flush=True)
    return out


def leave_one_out(p):
    ors = [np.exp(fit_gee(p[p["uid"] != u]).params["mid_dev_w"]) for u in p["uid"].unique()]
    row = {"check": "8 leave-one-person-out (GEE OR range)", "n_users": p["uid"].nunique(),
           "OR": np.median(ors), "OR_lo": min(ors), "OR_hi": max(ors)}
    print(row, flush=True)
    return row


def main(panel_path, out_path):
    panel = pd.read_parquet(panel_path)
    base = prepare(panel)
    rows = [focal(base, label="0 primary")]
    for k in (3, 5):
        rows.append(focal(prepare(build(min_nights=k)), label=f"1 min nights {k}"))
    rows.append(focal(base[base["first_hour"] < 13], label="2 first report before 13:00"))
    rl = report_level()
    rows.append(focal(rl, formula=MAIN.replace(")", ") + (1 | uid_day)"), label="3 all reports, 3-level"))
    rows.append(focal(base, MAIN.replace("tired ~", "negative ~"), GEE.replace("tired ~", "negative ~"),
                      label="4 outcome TENSE/ANXIOUS or SAD"))
    rows.append(focal(prepare(panel, "mid_sd7_min"), label="5a exposure: 7-night sd of midpoint"))
    rows.append(focal(prepare(panel, "eff_dev", transform=lambda x: x), label="5b exposure: efficiency deviation"))
    rows.append(focal(prepare(panel, "next_mid_dev_min", "next_dur_dev_h"), label="6 H3 negative control: next night"))
    rows.append(focal(prepare(panel, transform=winsor99), label="9 raw minutes, winsorised 99%"))
    rows += missingness()
    rows.append(leave_one_out(base))
    r = pd.DataFrame(rows)
    fdr = r["gee_p"].notna() & (r["check"] != "0 primary")
    r.loc[fdr, "gee_p_fdr"] = multipletests(r.loc[fdr, "gee_p"], method="fdr_bh")[1]
    r.to_csv(out_path, index=False)
    print(r.round(3).to_string())


if __name__ == "__main__":
    main(*sys.argv[1:3])
