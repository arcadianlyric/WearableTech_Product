"""Exploratory: sex-stratified descriptive rates and the two causal shifts.

Not in analysis_addendum_causal.md, so everything here is hypothesis-generating.
Usage: python src/posthoc_sex_strata.py data/interim/panel.parquet reports/causal/sex_strata.csv
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
from causal import E1, E2, add_terms, boot_counts, calendar, columns, gcomp, needed  # noqa: E402


def rates(panel):
    p = panel[panel["usable"] & panel["female"].notna() & panel["dur_dev_h"].notna()].copy()
    rows = []
    for sex, g in p.groupby("female"):
        by_person = g.groupby("uid")[["tired", "negative"]].mean()
        rows.append({"check": f"rates {'female' if sex else 'male'}", "n_users": g["uid"].nunique(), "n_days": len(g),
                     "tired_days": g["tired"].mean(), "negative_days": g["negative"].mean(),
                     "tired_person_median": by_person["tired"].median(),
                     "negative_person_median": by_person["negative"].median(),
                     "asleep_h": g["asleep_h"].mean(), "days_per_person": len(g) / g["uid"].nunique()})
    return rows


def shifts(g, panel):
    sex = panel.groupby("uid")["female"].first()
    a = g[g["analysed"].eq(1)].assign(female=lambda d: d["uid"].map(sex)).dropna(subset=["female"])
    rows = []
    for name, e in [("E1", E1), ("E2", E2)]:
        x, cols = columns(e)
        delta = e["shift"] / g.attrs[f"sd_{e['x']}"]
        d = needed(a, cols).reset_index(drop=True)
        f, m = d[d["female"].eq(1)].reset_index(drop=True), d[d["female"].eq(0)].reset_index(drop=True)
        rd = lambda t, w: gcomp(t, cols, x, delta, w)[0]
        obs = [rd(f, np.ones(len(f))), rd(m, np.ones(len(m)))]
        draws = np.array([[rd(f, c), rd(m, k)] for c, k in zip(boot_counts(f, 1000), boot_counts(m, 1000, seed=1))])
        diff = draws[:, 0] - draws[:, 1]
        rows.append({"check": name, "RD_female": obs[0], "RD_female_lo": np.quantile(draws[:, 0], .025),
                     "RD_female_hi": np.quantile(draws[:, 0], .975), "RD_male": obs[1],
                     "RD_male_lo": np.quantile(draws[:, 1], .025), "RD_male_hi": np.quantile(draws[:, 1], .975),
                     "diff": obs[0] - obs[1], "diff_lo": np.quantile(diff, .025), "diff_hi": np.quantile(diff, .975),
                     "n_female": f["uid"].nunique(), "n_male": m["uid"].nunique(),
                     "days_female": len(f), "days_male": len(m),
                     "tired_female": int(f["tired"].sum()), "tired_male": int(m["tired"].sum())})
    return rows


if __name__ == "__main__":
    panel = pd.read_parquet(sys.argv[1])
    g = add_terms(calendar())
    out = pd.DataFrame(rates(panel) + shifts(g, panel))
    out.to_csv(sys.argv[2], index=False)
    print(out.T.round(3).to_string())
