"""Post hoc: nightly skin temperature and next-day mood, within vs between person.

Spec: analysis_addendum_temperature.md (written before running this).

Usage: python src/posthoc_temperature.py data/interim/panel.parquet reports/posthoc_temperature.csv
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import statsmodels.api as sm
import statsmodels.formula.api as smf

sys.path.insert(0, str(Path(__file__).parent))
from build_panel import BSON  # noqa: E402
from models import fit_bayes, prepare  # noqa: E402

TEMP_RANGE = (31, 37)  # deg C; raw minimum 25.5 is a measurement failure
FORMULA = ("{y} ~ temp_w + temp_b + female + dur_dev_w + dur_dev_b + weekend + study_week_z"
           " + (1 + temp_w | uid)")
OUTCOMES = {"negative": "TENSE/ANXIOUS or SAD", "happy": "HAPPY", "tired": "TIRED"}


def nightly_temperature():
    t = pd.read_parquet(BSON / "fitbit/computed_temperature.parquet")
    t = t[t["type"] == "SKIN"].assign(
        night=lambda x: pd.to_datetime(x["sleep_end"], format="ISO8601").dt.normalize(),
        temp=lambda x: x["nightly_temperature"].astype(float),
        n_samples=lambda x: x["temperature_samples"].astype(float),
    )
    t = t.sort_values("n_samples").drop_duplicates(["uid", "night"], keep="last")
    return t[t["temp"].between(*TEMP_RANGE)][["uid", "night", "temp"]]


def build(panel):
    p = prepare(panel)
    p = p.merge(nightly_temperature(), left_on=["uid", "day"], right_on=["uid", "night"], suffixes=("", "_t"))
    p = p[p["female"].notna()].copy()
    b = p.groupby("uid")["temp"].transform("mean")
    p["temp_w"] = (p["temp"] - b) / (p["temp"] - b).std()
    p["temp_b"] = (b - b.mean()) / b.std()
    p["temp_z"] = (p["temp"] - p["temp"].mean()) / p["temp"].std()
    p["happy"] = (p["first_mood"] == "HAPPY").astype(int)
    return p


def summarize(idata, term, label, n, users):
    b = idata.posterior[term].values.ravel()
    q = np.exp(np.quantile(b, [0.5, 0.025, 0.975]))
    return {"analysis": label, "term": term, "n_days": n, "n_users": users,
            "OR": q[0], "OR_lo": q[1], "OR_hi": q[2], "P(beta>0)": (b > 0).mean()}


def main(panel_path, out_path):
    p = build(pd.read_parquet(panel_path))
    print(f"days {len(p)}, users {p['uid'].nunique()}, female users {p.drop_duplicates('uid')['female'].sum():.0f}")
    rows = []
    for y, name in OUTCOMES.items():
        _, idata = fit_bayes(p, FORMULA.format(y=y))
        for term in ["temp_w", "temp_b", "female"]:
            rows.append(summarize(idata, term, f"decomposed: {name}", len(p), p["uid"].nunique()))
            print(rows[-1], flush=True)
        # Karim-style: raw temperature, no decomposition, no random effects, no sex adjustment
        naive = smf.glm(f"{y} ~ temp_z", data=p, family=sm.families.Binomial()).fit()
        ci = np.exp(naive.conf_int().loc["temp_z"])
        rows.append({"analysis": f"naive pooled: {name}", "term": "temp_z", "n_days": len(p),
                     "n_users": p["uid"].nunique(), "OR": np.exp(naive.params["temp_z"]),
                     "OR_lo": ci[0], "OR_hi": ci[1], "p": naive.pvalues["temp_z"]})
        print(rows[-1], flush=True)
    for sex, g in p.groupby("female"):
        sub = FORMULA.format(y="negative").replace(" + female", "")
        _, idata = fit_bayes(g, sub)
        rows.append(summarize(idata, "temp_w", f"subgroup {'female' if sex else 'male'}: TENSE/ANXIOUS or SAD",
                              len(g), g["uid"].nunique()))
        print(rows[-1], flush=True)
    r = pd.DataFrame(rows)
    r.to_csv(out_path, index=False)
    print(r.round(3).to_string())


if __name__ == "__main__":
    main(*sys.argv[1:3])
