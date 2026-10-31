"""Exploratory: why are people tired after nights that look good on paper?

NOT pre-specified. Run after the primary analysis and the temperature addendum,
then written up; treat every estimate here as hypothesis-generating.

"Good night" = >= 7 h asleep and efficiency >= the panel median.
All features are within-person deviations (person-mean centred), per 1 sd.

Usage: python src/posthoc_good_nights.py data/interim/panel.parquet reports/posthoc_good_nights
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import statsmodels.api as sm
import statsmodels.formula.api as smf

sys.path.insert(0, str(Path(__file__).parent))
from build_panel import BSON, DAILY_CSV  # noqa: E402
from models import fit_bayes  # noqa: E402
from posthoc_temperature import build as build_temperature  # noqa: E402
from sleep import load_main_sleep  # noqa: E402

GOOD_MIN_H = 7
SCREEN = {
    "active_prev": "very active minutes, previous day",
    "sleep_deep_ratio": "deep sleep vs own 30-day average",
    "mid_shift_min": "midpoint shift (min, + = later)",
    "wake_h": "wake time",
    "resting_hr": "resting HR",
    "debt3": "prior 3 nights vs usual (h)",
    "dur_dev_h": "last night vs usual (h)",
    "nremhr": "NREM HR",
    "first_hour": "time of first report",
    "rmssd": "HRV (RMSSD)",
}


def add_daily(p):
    d = pd.read_csv(DAILY_CSV, usecols=["id", "date", "sleep_deep_ratio", "rmssd", "resting_hr", "nremhr",
                                        "very_active_minutes"]).rename(columns={"id": "uid"})
    d["day"] = pd.to_datetime(d["date"])
    act = d[["uid", "day", "very_active_minutes"]]
    p = p.merge(d.drop(columns=["date", "very_active_minutes"]), on=["uid", "day"], how="left")
    p = p.merge(act.assign(day=act["day"] + pd.Timedelta(days=1))
                .rename(columns={"very_active_minutes": "active_prev"}), on=["uid", "day"], how="left")
    # negative control: activity on the day AFTER the report cannot cause today's tiredness
    p = p.merge(act.assign(day=act["day"] - pd.Timedelta(days=1))
                .rename(columns={"very_active_minutes": "active_next"}), on=["uid", "day"], how="left")
    return p


def add_debt(p):
    """Mean deviation from the usual (previous 14 nights) over the 3 nights before last night."""
    s = load_main_sleep(BSON / "fitbit/sleep.parquet")
    out = []
    for uid, g in s.groupby("uid"):
        h = g.set_index("night")["asleep_h"].asfreq("D")
        dev = h - h.shift(1).rolling(14, min_periods=5).mean()
        out.append(pd.DataFrame({"uid": uid, "day": h.index, "debt3": dev.shift(1).rolling(3, min_periods=2).mean()}))
    return p.merge(pd.concat(out), on=["uid", "day"], how="left")


def within(g, col):
    x = g[col] - g.groupby("uid")[col].transform("mean")
    return x / x.std(), x.std()


def gee(g, formula):
    return smf.gee(formula, groups="uid", data=g, family=sm.families.Binomial(),
                   cov_struct=sm.cov_struct.Exchangeable()).fit()


def row(fit, term, **extra):
    lo, hi = np.exp(fit.conf_int().loc[term])
    return {**extra, "OR": np.exp(fit.params[term]), "OR_lo": lo, "OR_hi": hi, "p": fit.pvalues[term]}


def screen(good):
    rows = []
    for col, label in SCREEN.items():
        g = good.dropna(subset=[col]).copy()
        g["xw"], sd = within(g, col)
        rows.append(row(gee(g, "tired ~ xw"), "xw", feature=label, n_days=len(g), n_users=g["uid"].nunique(), sd=sd))
    return pd.DataFrame(rows).sort_values("p")


def adjusted(p, good):
    rows = []
    for sub, label in [(p, "all nights"), (good, "good nights")]:
        g = sub.dropna(subset=["sleep_deep_ratio", "active_prev", "dur_dev_h"]).copy()
        for c in ["sleep_deep_ratio", "active_prev", "dur_dev_h"]:
            g[f"{c}_w"], _ = within(g, c)
        f = gee(g, "tired ~ sleep_deep_ratio_w + active_prev_w + dur_dev_h_w + weekend")
        for t in ["sleep_deep_ratio_w", "active_prev_w", "dur_dev_h_w"]:
            rows.append(row(f, t, subset=label, coef=t, n_days=len(g), n_users=g["uid"].nunique()))
    g = p.dropna(subset=["active_next"]).copy()
    g["an_w"], _ = within(g, "active_next")
    rows.append(row(gee(g, "tired ~ an_w"), "an_w", subset="all nights", coef="negative control: active_next_w",
                    n_days=len(g), n_users=g["uid"].nunique()))
    return pd.DataFrame(rows)


def temperature_by_sex(panel):
    t = build_temperature(panel)
    rows = []
    for female, g in t.groupby("female"):
        _, idata = fit_bayes(g, "tired ~ temp_w + dur_dev_w + weekend + study_week_z + (1 + temp_w | uid)")
        b = idata.posterior["temp_w"].values.ravel()
        q = np.exp(np.quantile(b, [0.5, 0.025, 0.975]))
        rows.append({"group": "female" if female else "male", "n_days": len(g), "n_users": g["uid"].nunique(),
                     "OR": q[0], "OR_lo": q[1], "OR_hi": q[2], "P(beta>0)": (b > 0).mean(),
                     "within_person_temp_sd_median": g.groupby("uid")["temp"].std().median()})
    return pd.DataFrame(rows)


def sizing(p):
    """How big is 'slept well, still tired'? Plus the same rates by sex."""
    p = p.assign(good=(p["asleep_h"] >= GOOD_MIN_H) & (p["efficiency"] >= p["efficiency"].median()))
    tired = p[p["tired"] == 1]
    rows = [
        {"metric": "tired days", "value": len(tired)},
        {"metric": "share of tired days after >= 7 h asleep", "value": (tired["asleep_h"] >= GOOD_MIN_H).mean()},
        {"metric": "share of tired days after a good night", "value": tired["good"].mean()},
        {"metric": "people with >= 1 tired-after-good-night",
         "value": p[p["good"] & (p["tired"] == 1)]["uid"].nunique()},
        {"metric": "people with >= 1 good night", "value": p[p["good"]]["uid"].nunique()},
    ]
    for female, g in p.groupby("female"):
        sex = "female" if female else "male"
        rows += [{"metric": f"{sex}: people", "value": g["uid"].nunique()},
                 {"metric": f"{sex}: share of panel days", "value": len(g) / len(p)},
                 {"metric": f"{sex}: tired rate, good nights", "value": g[g["good"]]["tired"].mean()},
                 {"metric": f"{sex}: negative-mood rate, all days", "value": g["negative"].mean()}]
    return pd.DataFrame(rows)


def masked_strain(p):
    """The reverse mismatch: the body shows strain but the person does not report tiredness.

    Strain = resting HR or NREM HR >= +1 sd, or RMSSD <= -1 sd, vs the person's own mean;
    "strong" = at least 2 of the 3. Does a strained-but-not-tired day predict tiredness in the next 3 days?
    """
    p = p.dropna(subset=["resting_hr", "rmssd", "nremhr"]).sort_values(["uid", "day"]).copy()
    z = {c: (p[c] - p.groupby("uid")[c].transform("mean")) / p.groupby("uid")[c].transform("std")
         for c in ["resting_hr", "rmssd", "nremhr"]}
    n_signals = (z["resting_hr"] >= 1).astype(int) + (z["rmssd"] <= -1) + (z["nremhr"] >= 1)

    def next3(g):
        s = g.set_index("day")["tired"].asfreq("D")
        ahead = pd.concat([s.shift(-k) for k in (1, 2, 3)], axis=1).max(axis=1)
        return pd.Series(ahead.reindex(g["day"]).values, index=g.index)

    p["tired_next3"] = p.groupby("uid", group_keys=False)[["day", "tired"]].apply(next3)
    rows = [{"metric": "days with HR + HRV", "value": len(p)}, {"metric": "people", "value": p["uid"].nunique()}]
    for name, flag in [("strain", n_signals >= 1), ("strong strain", n_signals >= 2)]:
        s, rest = p[flag], p[~flag]
        rows += [{"metric": f"{name}: share of days", "value": flag.mean()},
                 {"metric": f"{name}: tired rate", "value": s["tired"].mean()},
                 {"metric": f"{name}: tired rate, other days", "value": rest["tired"].mean()},
                 {"metric": f"{name}, not tired: HAPPY or ALERT", "value":
                  s[s["tired"] == 0]["first_mood"].isin(["HAPPY", "ALERT"]).mean()},
                 {"metric": f"{name}, not tired: TENSE/ANXIOUS", "value":
                  (s[s["tired"] == 0]["first_mood"] == "TENSE/ANXIOUS").mean()},
                 {"metric": f"{name}: other days, not tired: HAPPY or ALERT", "value":
                  rest[rest["tired"] == 0]["first_mood"].isin(["HAPPY", "ALERT"]).mean()}]
    nt = p[(p["tired"] == 0) & p["tired_next3"].notna()].assign(strain=(n_signals >= 1).astype(int))
    fit = gee(nt, "tired_next3 ~ strain + weekend")
    rows.append(row(fit, "strain", metric="not tired today: strain -> tired within next 3 days (OR)",
                    value=np.exp(fit.params["strain"]), n_days=len(nt)))
    return pd.DataFrame(rows)


def main(panel_path, out_dir):
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    panel = pd.read_parquet(panel_path)
    p = add_debt(add_daily(panel[panel["usable"]].copy()))
    p["wake_h"] = p["mid_h"] + p["asleep_h"] / 2
    good = p[(p["asleep_h"] >= GOOD_MIN_H) & (p["efficiency"] >= p["efficiency"].median())]
    print(f"usable days {len(p)}, good nights {len(good)} ({good['uid'].nunique()} users); "
          f"TIRED rate {p['tired'].mean():.3f} vs {good['tired'].mean():.3f}")
    for name, df in [("sizing", sizing(p)), ("masked_strain", masked_strain(p)), ("screen", screen(good)),
                     ("adjusted", adjusted(p, good)),
                     ("temperature_by_sex", temperature_by_sex(panel))]:
        df.to_csv(out / f"{name}.csv", index=False)
        print(f"\n## {name}\n{df.round(3).to_string(index=False)}")


if __name__ == "__main__":
    main(*sys.argv[1:3])
