"""H1/H2 main model and the frequentist cross-check.

Usage: python src/models.py data/interim/panel_blind.parquet reports/blind
"""
import sys
from pathlib import Path

import arviz as az
import bambi as bmb
import numpy as np
import pandas as pd
import statsmodels.api as sm
import statsmodels.formula.api as smf

EXPOSURES = ["mid_dev", "dur_dev"]
MAIN = "tired ~ mid_dev_w + mid_dev_b + dur_dev_w + dur_dev_b + weekend + study_week_z + (1 + mid_dev_w | uid)"
GEE = "tired ~ mid_dev_w + mid_dev_b + dur_dev_w + dur_dev_b + weekend + study_week_z"


def prepare(p, exposure_col="mid_dev_min"):
    """Within/between split, each part scaled by its own sd so effects are 'per 1 sd'."""
    p = p[p["usable"] & p[exposure_col].notna() & p["dur_dev_h"].notna()].copy()
    p["mid_dev"] = np.log1p(p[exposure_col])
    p["dur_dev"] = p["dur_dev_h"]
    for x in EXPOSURES:
        b = p.groupby("uid")[x].transform("mean")
        w = p[x] - b
        p[f"{x}_w"] = w / w.std()
        p[f"{x}_b"] = (b - b.mean()) / b.std()
    p["study_week_z"] = (p["study_week"] - p["study_week"].mean()) / p["study_week"].std()
    return p


def fit_bayes(p, formula=MAIN, seed=20261029):
    model = bmb.Model(formula, p, family="bernoulli")
    idata = model.fit(draws=1000, tune=1000, chains=4, random_seed=seed, target_accept=0.95)
    return model, idata


def summarize_bayes(idata):
    s = az.summary(idata, var_names=["mid_dev_w", "mid_dev_b", "dur_dev_w", "dur_dev_b", "weekend",
                                     "study_week_z", "1|uid_sigma", "mid_dev_w|uid_sigma"],
                   ci_prob=0.95)
    post = idata.posterior
    b, sd = post["mid_dev_w"].values.ravel(), post["mid_dev_w|uid_sigma"].values.ravel()
    extra = pd.Series({
        "OR_mid_dev_w_median": np.exp(np.median(b)),
        "OR_mid_dev_w_lo": np.exp(np.quantile(b, 0.025)),
        "OR_mid_dev_w_hi": np.exp(np.quantile(b, 0.975)),
        "P(beta_w>0)": (b > 0).mean(),
        # 95% of people's slopes, integrating over posterior uncertainty in mean and sd
        "OR_person_pi_lo": np.exp(np.quantile(b - 1.96 * sd, 0.5)),
        "OR_person_pi_hi": np.exp(np.quantile(b + 1.96 * sd, 0.5)),
    })
    return s, extra


def fit_gee(p, formula=GEE):
    return smf.gee(formula, groups="uid", data=p, family=sm.families.Binomial(),
                   cov_struct=sm.cov_struct.Exchangeable()).fit()


if __name__ == "__main__":
    panel, out = Path(sys.argv[1]), Path(sys.argv[2])
    out.mkdir(parents=True, exist_ok=True)
    p = prepare(pd.read_parquet(panel))
    print(f"n days {len(p)}, users {p['uid'].nunique()}, base rate {p['tired'].mean():.3f}")
    gee = fit_gee(p)
    print(gee.summary().tables[1])
    _, idata = fit_bayes(p)
    s, extra = summarize_bayes(idata)
    print(s.round(3)); print(extra.round(3))
    s.to_csv(out / "main_bayes_summary.csv"); extra.to_csv(out / "main_bayes_or.csv")
    idata.to_netcdf(out / "main_idata.nc")
