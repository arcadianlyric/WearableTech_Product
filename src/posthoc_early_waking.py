"""Exploratory: does a stressful day predict waking early the next morning?

NOT pre-specified; hypothesis-generating only. Cortisol is not measured in LifeSnaps,
so this tests the observable pattern, not the hormonal mechanism.

Night = wake-up date W; "stress" is measured on W-1, the day before that night.
- early waking: final wake >= 60 min earlier than one's usual (median for the same
  weekday/weekend wake-up type)
  - terminal: sleep onset NOT >= 60 min earlier (woke early, the stress pattern)
  - phase shift: onset also >= 60 min earlier (whole night moved, a different cause)
- pre-wake HR: mean HR in the last 60 min of the sleep log minus that night's sleep mean
  (confounded by clock time: an early wake puts this window nearer the circadian HR nadir)
- clock-matched pre-wake HR: the same 60-min clock window on the person's nights that were
  still asleep through it, as the reference (only for terminal early-waking nights)

Usage: python src/posthoc_early_waking.py reports/posthoc_early_waking
"""
import ast
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow.compute as pc
import pyarrow.parquet as pq

sys.path.insert(0, str(Path(__file__).parent))
from build_panel import BSON, DAILY_CSV  # noqa: E402
from ema import load_mood  # noqa: E402
from posthoc_good_nights import gee, row  # noqa: E402
from sleep import load_main_sleep  # noqa: E402

EARLY_H = 1.0
PREWAKE_MIN = 60


def final_wake_min(levels):
    """Length of the wake bout that closes the sleep log (min); 0 if the log ends asleep."""
    last = ast.literal_eval(levels)["data"][-1]
    return last["seconds"] / 60 if last["level"] in ("wake", "awake") else 0.0


def nights():
    s = load_main_sleep(BSON / "fitbit/sleep.parquet")
    raw = pd.read_parquet(BSON / "fitbit/sleep.parquet", columns=["uid", "dateOfSleep", "startTime", "levels"])
    raw["start"] = pd.to_datetime(raw["startTime"])
    s = s.merge(raw[["uid", "start", "levels"]].drop_duplicates(["uid", "start"]), on=["uid", "start"], how="left")
    s["final_wake_min"] = s["levels"].map(final_wake_min)
    s["wake_h"] = (s["end"] - s["night"]).dt.total_seconds() / 3600
    s["onset_h"] = (s["start"] - (s["night"] - pd.Timedelta(hours=12))).dt.total_seconds() / 3600
    s["weekend"] = (s["night"].dt.day_of_week >= 5).astype(int)
    usual = s.groupby(["uid", "weekend"])[["wake_h", "onset_h"]].transform("median")
    s["wake_dev_h"] = s["wake_h"] - usual["wake_h"]
    s["onset_dev_h"] = s["onset_h"] - usual["onset_h"]
    early = s["wake_dev_h"] <= -EARLY_H
    s["early_terminal"] = (early & (s["onset_dev_h"] > -EARLY_H)).astype(int)
    s["early_shift"] = (early & (s["onset_dev_h"] <= -EARLY_H)).astype(int)
    return s.drop(columns=["levels"])


def stress_by_day():
    e = load_mood(BSON / "sema/context_and_mood_survey.parquet")
    d = e.assign(tense=(e["MOOD"] == "TENSE/ANXIOUS").astype(int)).groupby(["uid", "day"])["tense"].max()
    d = d.reset_index()
    f = pd.read_parquet(BSON / "fitbit/stress_score.parquet")
    f = f[(f["STATUS"] == "READY") & (f["STRESS_SCORE"].astype(float) > 0)]
    f = f.assign(day=pd.to_datetime(f["DATE"]).dt.normalize(),
                 # Fitbit: higher score = FEWER signs of stress, so flip the sign
                 fitbit_stress=-f["STRESS_SCORE"].astype(float),
                 low_responsiveness=-f["RESPONSIVENESS_POINTS"].astype(float))
    f = f.drop_duplicates(["uid", "day"])[["uid", "day", "fitbit_stress", "low_responsiveness"]]
    return d.merge(f, on=["uid", "day"], how="outer")


def prewake_hr(s):
    t = pq.read_table(BSON / "fitbit/heart_rate.parquet", columns=["uid", "dateTime", "bpm"])
    t = t.set_column(1, "ts", pc.strptime(t["dateTime"], format="%Y-%m-%dT%H:%M:%S", unit="s"))
    hr = t.to_pandas()
    out, matched = [], []
    for uid, g in s.groupby("uid"):
        h = hr[hr["uid"] == uid].sort_values("ts")
        ts, bpm = h["ts"].to_numpy(), h["bpm"].to_numpy(float)
        for _, n in g.iterrows():
            a, b = np.searchsorted(ts, [n["start"].to_datetime64(), n["end"].to_datetime64()])
            c = np.searchsorted(ts, (n["end"] - pd.Timedelta(minutes=PREWAKE_MIN)).to_datetime64())
            if b - a < 100 or b - c < 20:
                continue
            out.append({"uid": uid, "night": n["night"], "hr_prewake_rise": bpm[c:b].mean() - bpm[a:b].mean()})
        # Clock-matched: same clock window on this person's nights that slept through it
        for _, n in g[g["early_terminal"] == 1].iterrows():
            lo_h, hi_h = n["wake_h"] - PREWAKE_MIN / 60, n["wake_h"]
            vals = []
            for _, m in g[g["night"] != n["night"]].iterrows():
                if m["wake_h"] < hi_h + 0.5:  # reference must still be asleep, with a 30-min margin
                    continue
                w0 = (m["night"] + pd.Timedelta(hours=lo_h)).to_datetime64()
                w1 = (m["night"] + pd.Timedelta(hours=hi_h)).to_datetime64()
                i, j = np.searchsorted(ts, [w0, w1])
                if j - i >= 20:
                    vals.append(bpm[i:j].mean())
            i, j = np.searchsorted(ts, [(n["end"] - pd.Timedelta(minutes=PREWAKE_MIN)).to_datetime64(),
                                        n["end"].to_datetime64()])
            if len(vals) >= 3 and j - i >= 20:
                matched.append({"uid": uid, "night": n["night"], "hr_early": bpm[i:j].mean(),
                                "hr_reference": np.mean(vals)})
    return pd.DataFrame(out), pd.DataFrame(matched)


def within(x, by):
    return x - x.groupby(by).transform("mean")


def main(out_dir):
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    s = nights()
    st = stress_by_day()
    prev = st.assign(night=st["day"] + pd.Timedelta(days=1)).drop(columns="day")
    nxt = st[["uid", "day", "tense"]].rename(columns={"tense": "tense_next"})
    nxt = nxt.assign(night=nxt["day"] - pd.Timedelta(days=1)).drop(columns="day")
    d = s.merge(prev, on=["uid", "night"], how="left").merge(nxt, on=["uid", "night"], how="left")
    daily = pd.read_csv(DAILY_CSV, usecols=["id", "date", "rmssd", "nremhr"]).rename(columns={"id": "uid"})
    d = d.merge(daily.assign(night=pd.to_datetime(daily["date"])).drop(columns="date"), on=["uid", "night"], how="left")
    pre, matched = prewake_hr(s)
    d = d.merge(pre, on=["uid", "night"], how="left")

    rows = [{"metric": "nights", "value": len(d)}, {"metric": "people", "value": d["uid"].nunique()}]
    for y in ["early_terminal", "early_shift"]:
        rows.append({"metric": f"{y}: share of nights", "value": d[y].mean()})
    term = d[d["early_terminal"] == 1]
    rows += [{"metric": "early_terminal: median wake earlier than usual (min)", "value": -term["wake_dev_h"].median() * 60},
             {"metric": "early_terminal: median final wake bout (min)", "value": term["final_wake_min"].median()},
             {"metric": "other nights: median final wake bout (min)", "value": d[d["early_terminal"] == 0]["final_wake_min"].median()}]

    # Stress the day before -> terminal early waking (and the phase-shift pattern for contrast)
    for x in ["tense", "fitbit_stress", "low_responsiveness", "tense_next"]:
        for y in ["early_terminal", "early_shift"]:
            g = d.dropna(subset=[x]).copy()
            g["x_w"] = within(g[x], g["uid"])
            if g["x_w"].std() == 0:
                continue
            if x != "tense" and x != "tense_next":
                g["x_w"] = g["x_w"] / g["x_w"].std()
            label = "NEGATIVE CONTROL: tense the day AFTER" if x == "tense_next" else f"{x} (day before)"
            rows.append(row(gee(g, f"{y} ~ x_w + weekend"), "x_w", metric=f"{label} -> {y} (OR)",
                            n_nights=len(g), n_users=g["uid"].nunique()))

    # Physiology on terminal early-waking nights vs the same person's other nights
    for c in ["hr_prewake_rise", "rmssd", "nremhr"]:
        g = d.dropna(subset=[c]).copy()
        g["z"] = within(g[c], g["uid"]) / g.groupby("uid")[c].transform("std")
        f = gee(g.assign(**{"is_early": g["early_terminal"]}), "early_terminal ~ z + weekend")
        rows.append(row(f, "z", metric=f"{c} (within-person z) -> early_terminal (OR)",
                        n_nights=len(g), n_users=g["uid"].nunique()))
        rows.append({"metric": f"{c}: mean within-person z on early_terminal nights", "value":
                     g.loc[g["early_terminal"] == 1, "z"].mean()})
    # Clock-matched comparison: paired difference, with a person-clustered bootstrap CI
    diff = (matched["hr_early"] - matched["hr_reference"]).groupby(matched["uid"]).mean()
    rng = np.random.default_rng(20261029)
    boot = [rng.choice(diff.values, len(diff)).mean() for _ in range(2000)]
    rows += [{"metric": "clock-matched pre-wake HR: early night minus same clock window on other nights (bpm, person mean)",
              "value": diff.mean(), "OR_lo": np.quantile(boot, 0.025), "OR_hi": np.quantile(boot, 0.975),
              "n_nights": len(matched), "n_users": len(diff)},
             {"metric": "clock-matched: share of people with higher HR before early waking", "value": (diff > 0).mean()}]
    r = pd.DataFrame(rows)
    r.to_csv(out / "early_waking.csv", index=False)
    print(r.round(3).to_string(index=False))


if __name__ == "__main__":
    main(sys.argv[1])
