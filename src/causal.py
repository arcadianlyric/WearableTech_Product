"""Post hoc causal estimates: analysis_addendum_causal.md.

E1: shift last night's sleep by -1 h. E2: shift yesterday's vigorous minutes by +30.
Bayesian g-computation is primary; IPW, MNAR tipping point, negative controls and
sensitivity checks use logistic g-computation with a person-level bootstrap.

Usage: python src/causal.py reports/causal
"""
import sys
from pathlib import Path

import arviz as az
import numpy as np
import pandas as pd
from scipy.special import expit

sys.path.insert(0, str(Path(__file__).parent))
from build_panel import BSON, DAILY_CSV, SEED  # noqa: E402
from ema import daily_outcomes, load_mood  # noqa: E402
from models import fit_bayes  # noqa: E402
from sleep import add_exposures, load_main_sleep  # noqa: E402

COMMON = ["lag3_w", "weekend", "prev_weekend", "study_week_z"]
E1 = {"x": "dur", "shift": -1.0, "adj": ["active_w", "active_b", "steps_w"] + COMMON,
      "worse": lambda d: d["dur_dev_h"] >= 0}
E2 = {"x": "active", "shift": 30.0, "adj": COMMON,
      "worse": lambda d: d["active_prev"] <= d.groupby("uid")["active_prev"].transform("mean")}
DELTAS = [0, 0.5, 1, 1.5, 2, 3]


def calendar():
    """All days between each analysed person's first and last report, with or without data."""
    sleep = add_exposures(load_main_sleep(BSON / "fitbit/sleep.parquet"))
    mood = daily_outcomes(load_mood(BSON / "sema/context_and_mood_survey.parquet"))
    mood = mood[["uid", "day", "tired", "first_hour"]]
    keep = set(sleep.merge(mood, left_on=["uid", "night"], right_on=["uid", "day"]).query("usable")["uid"])
    d = pd.read_csv(DAILY_CSV, usecols=["id", "date", "very_active_minutes", "steps"]).rename(columns={"id": "uid"})
    d["day"] = pd.to_datetime(d["date"]).dt.tz_localize(None)
    d = d.groupby(["uid", "day"], as_index=False)[["very_active_minutes", "steps"]].max()
    span = mood[mood["uid"].isin(keep)].groupby("uid")["day"].agg(["min", "max"])
    grid = pd.concat(pd.DataFrame({"uid": u, "day": pd.date_range(r["min"], r["max"]), "t0": r["min"]})
                     for u, r in span.iterrows())
    prev = d.assign(day=d["day"] + pd.Timedelta(days=1)).rename(
        columns={"very_active_minutes": "active_prev", "steps": "steps_prev"})[["uid", "day", "active_prev", "steps_prev"]]
    nxt = d.assign(day=d["day"] - pd.Timedelta(days=1)).rename(
        columns={"very_active_minutes": "active_next"})[["uid", "day", "active_next"]]
    s = sleep[["uid", "night", "dur_dev_h", "mid_dev_min", "usable"]].rename(columns={"night": "day"})
    g = grid.merge(s, on=["uid", "day"], how="left").merge(mood, on=["uid", "day"], how="left")
    g = g.merge(prev, on=["uid", "day"], how="left").merge(nxt, on=["uid", "day"], how="left")
    g = g.sort_values(["uid", "day"]).reset_index(drop=True)
    u = g.groupby("uid")
    g["has_sleep"] = (g["usable"].fillna(False).astype(bool) & g["dur_dev_h"].notna()).astype(int)
    g["analysed"] = (g["has_sleep"].eq(1) & g["tired"].notna()).astype(int)
    g["lag3"] = u["dur_dev_h"].transform(lambda x: x.shift(1).rolling(3, min_periods=1).mean())
    g["dur_next"] = u["dur_dev_h"].shift(-1)
    g["tired_lag"] = u["tired"].shift(1)
    g["weekend"] = (g["day"].dt.day_of_week >= 5).astype(int)
    g["prev_weekend"] = ((g["day"] - pd.Timedelta(days=1)).dt.day_of_week >= 5).astype(int)
    g["study_week"] = (g["day"] - g["t0"]).dt.days // 7
    g["study_week_z"] = (g["study_week"] - g["study_week"].mean()) / g["study_week"].std()
    return g


def add_terms(g):
    """Within/between parts on the analysed days; scales kept so shifts stay in raw units."""
    a = g["analysed"].eq(1)
    g = g.copy()
    for raw, name in [("dur_dev_h", "dur"), ("active_prev", "active"), ("steps_prev", "steps"), ("lag3", "lag3"),
                      ("mid_dev_min", "mid")]:
        x = np.log1p(g[raw]) if raw == "mid_dev_min" else g[raw]
        mean = x[a].groupby(g.loc[a, "uid"]).mean()
        b = g["uid"].map(mean)
        sd_w = (x - b)[a].std()
        g[f"{name}_w"] = (x - b) / sd_w
        g[f"{name}_b"] = (b - b[a].mean()) / b[a].std()
        g.attrs[f"sd_{name}"] = sd_w
    return g


def logit_fit(X, y, w, iters=30):
    """Weighted logistic regression by Newton steps."""
    beta = np.zeros(X.shape[1])
    for _ in range(iters):
        p = expit(X @ beta)
        v = np.maximum(w * p * (1 - p), 1e-9)
        step = np.linalg.solve((X * v[:, None]).T @ X + 1e-8 * np.eye(X.shape[1]), X.T @ (w * (y - p)))
        beta += step
        if np.abs(step).max() < 1e-8:
            break
    return beta


def design(d, cols):
    return np.column_stack([np.ones(len(d)), d[cols].to_numpy(float)])


def gcomp(d, cols, x, delta, w, y="tired", y_values=None):
    """RD in points and RR for shifting column x by delta; weights also standardise."""
    X = design(d, cols)
    target = d[y].to_numpy(float) if y_values is None else y_values
    beta = logit_fit(X, target, w)
    X1 = X.copy()
    X1[:, cols.index(x) + 1] += delta
    p0, p1 = (w * expit(X @ beta)).sum() / w.sum(), (w * expit(X1 @ beta)).sum() / w.sum()
    return 100 * (p1 - p0), p1 / p0


def ipw(g, w_boot):
    """Stabilised inverse-probability weights for has_sleep, then report given sleep."""
    g = g.assign(wt=w_boot)
    lag = g.groupby("uid")["analysed"]
    g["analysed_lag"] = lag.shift(1).fillna(0)
    g["recent"] = lag.transform(lambda x: x.shift(1).rolling(7, min_periods=1).mean()).fillna(0)
    g["rate"] = lag.transform("mean")
    g["active_miss"] = g["active_prev"].isna().astype(int)
    g["active_fill"] = g["active_prev"].fillna(g.groupby("uid")["active_prev"].transform("mean")).fillna(0) / 30
    base = ["weekend", "prev_weekend", "study_week_z", "analysed_lag", "recent", "rate"]
    p1 = expit(design(g, base) @ logit_fit(design(g, base), g["has_sleep"].to_numpy(float), g["wt"].to_numpy()))
    s = g[g["has_sleep"].eq(1)]
    cols2 = base + ["dur_dev_h", "active_fill", "active_miss"]
    b2 = logit_fit(design(s, cols2), s["analysed"].to_numpy(float), s["wt"].to_numpy())
    p2 = expit(design(s, cols2) @ b2)
    out = pd.Series(1 / (p1[g["has_sleep"].eq(1).to_numpy()] * p2), index=s.index)
    out = out[s["analysed"].eq(1)] * g.loc[s.index[s["analysed"].eq(1)], "rate"]
    return out.clip(out.quantile(0.01), out.quantile(0.99))


def boot_counts(g, n, seed=SEED):
    """Each draw maps person -> times resampled, so a bootstrap is a row reweighting."""
    rng = np.random.default_rng(seed)
    uids = g["uid"].unique()
    for _ in range(n):
        c = pd.Series(rng.multinomial(len(uids), [1 / len(uids)] * len(uids)), index=uids)
        yield g["uid"].map(c).to_numpy(float)


def interval(rows):
    a = np.array(rows, float)
    return {"RD": a[0, 0], "RD_lo": np.quantile(a[1:, 0], 0.025), "RD_hi": np.quantile(a[1:, 0], 0.975),
            "RR": a[0, 1], "RR_lo": np.quantile(a[1:, 1], 0.025), "RR_hi": np.quantile(a[1:, 1], 0.975)}


def boot(d, cols, x, delta, n=1000):
    d = d.reset_index(drop=True)
    rows = [gcomp(d, cols, x, delta, np.ones(len(d)))]
    rows += [gcomp(d, cols, x, delta, c) for c in boot_counts(d, n) if c.sum() > 0]
    return {**interval(rows), "n_days": len(d), "n_users": d["uid"].nunique()}


def columns(e):
    x = f"{e['x']}_w"
    return x, [x, f"{e['x']}_b"] + e["adj"]


def needed(g, cols):
    return g.dropna(subset=cols)


def bayes(g, e):
    x, cols = columns(e)
    d = needed(g[g["analysed"].eq(1)], cols).reset_index(drop=True)
    formula = f"tired ~ {' + '.join(cols)} + (1 + {x} | uid)"
    model, idata = fit_bayes(d, formula)
    post = idata.posterior
    delta = e["shift"] / g.attrs[f"sd_{e['x']}"]
    groups = d["uid"].astype(str).to_numpy()

    def draws(name):
        return post[name].stack(sample=("chain", "draw")).values

    def person(name):
        a = post[name].stack(sample=("chain", "draw"))
        dim = next(c for c in a.dims if c != "sample")
        return a.sel({dim: groups}).transpose(dim, "sample").values

    eta = draws("Intercept") + sum(np.outer(d[c].to_numpy(float), draws(c)) for c in cols)
    u0, u1 = person("1|uid"), person(f"{x}|uid")
    p0 = expit(eta + u0 + u1 * d[[x]].to_numpy(float)).mean(axis=0)
    p1 = expit(eta + u0 + u1 * d[[x]].to_numpy(float) + (draws(x) + u1) * delta).mean(axis=0)
    rd, rr = 100 * (p1 - p0), p1 / p0
    return {"RD": np.median(rd), "RD_lo": np.quantile(rd, 0.025), "RD_hi": np.quantile(rd, 0.975),
            "RR": np.median(rr), "RR_lo": np.quantile(rr, 0.025), "RR_hi": np.quantile(rr, 0.975),
            "P(RD>0)": (rd > 0).mean(), "base_risk": 100 * np.median(p0), "n_days": len(d),
            "n_users": d["uid"].nunique(), "n_tired": int(d["tired"].sum()),
            "summary": az.summary(idata, var_names=["Intercept"] + cols + ["1|uid_sigma", f"{x}|uid_sigma"], ci_prob=0.95)}


def weighted(g, e, n=1000):
    x, cols = columns(e)
    delta = e["shift"] / g.attrs[f"sd_{e['x']}"]
    g = g.reset_index(drop=True)
    ok = needed(g[g["analysed"].eq(1)], cols).index

    def one(c):
        wt = ipw(g, c).reindex(ok).fillna(0).to_numpy() * c[ok]
        return gcomp(g.loc[ok].reset_index(drop=True), cols, x, delta, wt)

    w = ipw(g, np.ones(len(g))).reindex(ok)
    rows = [one(np.ones(len(g)))] + [one(c) for c in boot_counts(g, n)]
    return {**interval(rows), "n_days": len(ok), "weight_max": w.max(), "weight_mean": w.mean(),
            "ess": w.sum() ** 2 / (w ** 2).sum()}


def tipping(g, e, n=500):
    x, cols = columns(e)
    delta = e["shift"] / g.attrs[f"sd_{e['x']}"]
    d = needed(g[g["has_sleep"].eq(1)], cols).reset_index(drop=True)
    seen = d["tired"].notna().to_numpy()
    unfavourable = e["worse"](d).to_numpy()
    X = design(d, cols)
    y = d["tired"].fillna(0).to_numpy(float)

    def one(c, dl):
        b = logit_fit(X[seen], y[seen], c[seen])
        p = expit(X[~seen] @ b + dl * unfavourable[~seen])
        Xs = np.vstack([X[seen], X[~seen], X[~seen]])
        ys = np.r_[y[seen], np.ones((~seen).sum()), np.zeros((~seen).sum())]
        ws = np.r_[c[seen], c[~seen] * p, c[~seen] * (1 - p)]
        b2 = logit_fit(Xs, ys, ws)
        X1 = X.copy()
        X1[:, cols.index(x) + 1] += delta
        p0, p1 = (c * expit(X @ b2)).sum() / c.sum(), (c * expit(X1 @ b2)).sum() / c.sum()
        return 100 * (p1 - p0), p1 / p0

    out, counts = [], list(boot_counts(d, n))
    for dl in DELTAS:
        rows = [one(np.ones(len(d)), dl)] + [one(c, dl) for c in counts]
        out.append({"delta": dl, **interval(rows), "n_imputed": int((~seen).sum())})
    return out


def evalue(rr):
    rr = max(rr, 1 / rr)
    return rr + np.sqrt(rr * (rr - 1))


def sensitivity(g):
    a = g[g["analysed"].eq(1)]
    x1, c1 = columns(E1)
    x2, c2 = columns(E2)
    d1, d2 = E1["shift"] / g.attrs["sd_dur"], E2["shift"] / g.attrs["sd_active"]
    rows = {}
    rows["E1 baseline, unweighted"] = boot(needed(a, c1), c1, x1, d1)
    rows["E2 baseline, unweighted"] = boot(needed(a, c2), c2, x2, d2)
    z = a.assign(tired_lag_c=a["tired_lag"] - a.groupby("uid")["tired_lag"].transform("mean"))
    rows["E1 + yesterday tired"] = boot(needed(z, c1 + ["tired_lag_c"]), c1 + ["tired_lag_c"], x1, d1)
    rows["E2 + yesterday tired"] = boot(needed(z, c2 + ["tired_lag_c"]), c2 + ["tired_lag_c"], x2, d2)
    m = a[a["first_hour"] < 13]
    rows["E1 first report before 13:00"] = boot(needed(m, c1), c1, x1, d1)
    rows["E2 first report before 13:00"] = boot(needed(m, c2), c2, x2, d2)
    rows["E1 + mid-sleep deviation"] = boot(needed(a, c1 + ["mid_w", "mid_b"]), c1 + ["mid_w", "mid_b"], x1, d1)
    rows["E2 controlled direct effect"] = boot(needed(a, c2 + ["dur_w", "dur_b"]), c2 + ["dur_w", "dur_b"], x2, d2)
    rows["E1 negative control: next night"] = negative(a, c1, "dur_next", E1["shift"])
    rows["E2 negative control: next day"] = negative(a, c2, "active_next", E2["shift"])
    rows["E1 quadratic"] = curved(a, c1, x1, d1)
    rows["E2 quadratic"] = curved(a, c2, x2, d2)
    rows["E2 log1p exposure"] = logged(a, c2)
    return pd.DataFrame(rows).T.reset_index(names="check")


def negative(a, cols, col, shift):
    d = needed(a, cols + [col]).copy()
    d["nc_w"] = (d[col] - d.groupby("uid")[col].transform("mean"))
    sd = d["nc_w"].std()
    d["nc_w"] /= sd
    return boot(d, cols + ["nc_w"], "nc_w", shift / sd)


def refit(d, cols, change):
    d = d.reset_index(drop=True)

    def one(w):
        X = design(d, cols)
        y = d["tired"].to_numpy(float)
        b = logit_fit(X, y, w)
        p0, p1 = (w * expit(X @ b)).sum() / w.sum(), (w * expit(change(d, cols, b))).sum() / w.sum()
        return 100 * (p1 - p0), p1 / p0

    rows = [one(np.ones(len(d)))] + [one(c) for c in boot_counts(d, 1000) if c.sum() > 0]
    return {**interval(rows), "n_days": len(d), "n_users": d["uid"].nunique()}


def curved(a, cols, x, delta):
    d = needed(a, cols).assign(x2=lambda t: t[x] ** 2)
    all_cols = cols + ["x2"]

    def change(t, c, b):
        m = t.assign(**{x: t[x] + delta, "x2": (t[x] + delta) ** 2})
        return design(m, c) @ b

    return refit(d, all_cols, change)


def logged(a, cols):
    """Exposure on log1p minutes; the shift stays +30 raw minutes."""
    d = needed(a, cols + ["active_prev"]).copy()
    raw = np.log1p(d["active_prev"])
    mean = raw.groupby(d["uid"]).transform("mean")
    sd = (raw - mean).std()
    d["active_w"] = (raw - mean) / sd

    def change(t, c, b):
        return design(t.assign(active_w=(np.log1p(t["active_prev"] + 30) - mean.values) / sd), c) @ b

    return refit(d, cols, change)


def main(out):
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    g = add_terms(calendar())
    n_grid, n_a = len(g), int(g["analysed"].sum())
    coverage = pd.DataFrame([{"person_days": n_grid, "has_sleep": int(g["has_sleep"].sum()), "analysed": n_a,
                              "analysed_share": n_a / n_grid, "people": g["uid"].nunique(),
                              "sd_dur_h": g.attrs["sd_dur"], "sd_active_min": g.attrs["sd_active"]}])
    coverage.to_csv(out / "coverage.csv", index=False)
    print(coverage.T, flush=True)
    a = g[g["analysed"].eq(1)]
    print("shift stays in own range:",
          ((a["dur_dev_h"] - 1) >= a.groupby("uid")["dur_dev_h"].transform("min")).mean(),
          ((a["active_prev"] + 30) <= a.groupby("uid")["active_prev"].transform("max")).mean(), flush=True)

    rows, diag = [], []
    for name, e in [("E1", E1), ("E2", E2)]:
        r = bayes(g, e)
        diag.append(r.pop("summary").assign(estimand=name))
        rows.append({"estimand": name, **r, "evalue_point": evalue(r["RR"]),
                     "evalue_ci": evalue(r["RR_lo"] if r["RD"] > 0 else r["RR_hi"]) if (r["RD_lo"] > 0 or r["RD_hi"] < 0) else 1.0})
        print(rows[-1], flush=True)
    pd.DataFrame(rows).to_csv(out / "bayes_gcomp.csv", index=False)
    pd.concat(diag).to_csv(out / "bayes_diagnostics.csv")

    weighted_rows = [{"estimand": n, **weighted(g, e)} for n, e in [("E1", E1), ("E2", E2)]]
    pd.DataFrame(weighted_rows).to_csv(out / "ipw.csv", index=False)
    print(weighted_rows, flush=True)
    tip = [{"estimand": n, **r} for n, e in [("E1", E1), ("E2", E2)] for r in tipping(g, e)]
    pd.DataFrame(tip).to_csv(out / "mnar_tipping.csv", index=False)
    sens = sensitivity(g)
    sens.to_csv(out / "sensitivity.csv", index=False)
    print(sens.round(3).to_string(), flush=True)


if __name__ == "__main__":
    main(sys.argv[1])
