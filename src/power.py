"""Simulation-based power for H1 on the real panel structure.

Keeps the observed people, days and exposure values; only the outcome is
simulated. Fits use GEE logistic (exchangeable) on within-person centred
exposures, a fast stand-in for the Bayesian mixed model used in the analysis.

Usage: python src/power.py data/interim/panel_blind.parquet reports/power.csv
"""
import sys

import numpy as np
import pandas as pd
import statsmodels.api as sm
import statsmodels.formula.api as smf

SD_INTERCEPT = 1.0  # between-person sd of logit(TIRED); assumption
SD_SLOPE = 0.3      # between-person sd of the H1 slope; assumption
OR_GRID = [1.1, 1.2, 1.3, 1.5, 1.75, 2.0]
N_SIM = 200


def prepare(p):
    p = p[p["usable"] & p["mid_dev_min"].notna() & p["dur_dev_h"].notna()].copy()
    p["mid_dev_min"] = np.log1p(p["mid_dev_min"])  # right-skewed: median 34, max 544 min
    for x in ["mid_dev_min", "dur_dev_h"]:
        w = p[x] - p.groupby("uid")[x].transform("mean")
        p[f"{x}_w"] = w / w.std()
    return p


def simulate(p, log_or, base_rate, rng):
    uids = p["uid"].unique()
    u0 = dict(zip(uids, rng.normal(0, SD_INTERCEPT, len(uids))))
    u1 = dict(zip(uids, rng.normal(0, SD_SLOPE, len(uids))))
    a = np.log(base_rate / (1 - base_rate))
    eta = (a + p["uid"].map(u0) + (log_or + p["uid"].map(u1)) * p["mid_dev_min_w"]
           + 0.2 * p["dur_dev_h_w"])
    return rng.binomial(1, 1 / (1 + np.exp(-eta)))


def power(p, n_sim=N_SIM, seed=1):
    rng = np.random.default_rng(seed)
    base = p["tired"].mean()
    rows = []
    for odds in OR_GRID:
        hits = 0
        for _ in range(n_sim):
            d = p.assign(y=simulate(p, np.log(odds), base, rng))
            fit = smf.gee("y ~ mid_dev_min_w + dur_dev_h_w", groups="uid", data=d,
                          family=sm.families.Binomial(), cov_struct=sm.cov_struct.Exchangeable()).fit()
            hits += (fit.pvalues["mid_dev_min_w"] < 0.05) & (fit.params["mid_dev_min_w"] > 0)
        rows.append({"or_per_sd": odds, "power": hits / n_sim})
        print(rows[-1], flush=True)
    return pd.DataFrame(rows).assign(n_days=len(p), n_users=p["uid"].nunique(), base_rate=base)


if __name__ == "__main__":
    p = prepare(pd.read_parquet(sys.argv[1]))
    power(p).to_csv(sys.argv[2], index=False)
