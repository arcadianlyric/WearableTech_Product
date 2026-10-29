"""Join daily mood outcomes to the previous night's sleep exposures.

Writes a BLINDED panel by default: outcome columns are permuted within each
person, which keeps every person's base rate but breaks any link to sleep.
The real panel is only written with --unblind, after analysis_plan.md is committed.

Usage: python src/build_panel.py [--unblind]
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
from ema import daily_outcomes, load_mood  # noqa: E402
from sleep import add_exposures, load_main_sleep  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
BSON = ROOT / "data/interim/bson"
DAILY_CSV = ROOT / "data/raw/rais_anonymized/csv_rais_anonymized/daily_fitbit_sema_df_unprocessed.csv"
OUTCOMES = ["first_mood", "tired", "negative", "tired_share", "negative_share", "n_ema"]
SEED = 20261029


def demographics():
    d = pd.read_csv(DAILY_CSV, usecols=["id", "date", "age", "gender", "bmi", "steps"])
    d = d.rename(columns={"id": "uid"}).assign(date=lambda x: pd.to_datetime(x["date"]))
    demo = d.groupby("uid")[["age", "gender", "bmi"]].agg(lambda x: x.dropna().mode().iloc[0] if x.notna().any() else np.nan)
    # Released demographics are coarsened: age is '<30'/'>=30', bmi mixes bins and values.
    demo["age_ge30"] = demo["age"].map({"<30": 0, ">=30": 1})
    bmi_num = pd.to_numeric(demo["bmi"], errors="coerce")
    demo["bmi_ge25"] = np.where(demo["bmi"].isin([">=25", ">=30"]), 1,
                                np.where(demo["bmi"] == "<19", 0, (bmi_num >= 25).astype(float)))
    demo.loc[demo["bmi"].isna(), "bmi_ge25"] = np.nan
    demo["female"] = demo["gender"].map({"FEMALE": 1, "MALE": 0})
    steps = d[["uid", "date", "steps"]].rename(columns={"date": "day", "steps": "steps_prev_day"})
    steps["day"] = steps["day"] + pd.Timedelta(days=1)
    return demo.reset_index(), steps


def build(min_nights=4):
    sleep = add_exposures(load_main_sleep(BSON / "fitbit/sleep.parquet"), min_nights=min_nights)
    mood = daily_outcomes(load_mood(BSON / "sema/context_and_mood_survey.parquet"))
    p = mood.merge(sleep, left_on=["uid", "day"], right_on=["uid", "night"], how="inner")
    # Negative control: the night AFTER the EMA day (night labelled day+1).
    nxt = sleep[["uid", "night", "mid_dev_min", "dur_dev_h"]].rename(
        columns={"mid_dev_min": "next_mid_dev_min", "dur_dev_h": "next_dur_dev_h"})
    nxt["night"] = nxt["night"] - pd.Timedelta(days=1)
    p = p.merge(nxt, left_on=["uid", "day"], right_on=["uid", "night"], how="left", suffixes=("", "_n"))
    p = p.drop(columns="night_n")
    demo, steps = demographics()
    p = p.merge(demo, on="uid", how="left").merge(steps, on=["uid", "day"], how="left")
    p["weekend"] = (p["day"].dt.day_of_week >= 5).astype(int)
    p["study_week"] = (p["day"] - p.groupby("uid")["day"].transform("min")).dt.days // 7
    return p.sort_values(["uid", "day"]).reset_index(drop=True)


def blind(p, seed=SEED):
    rng = np.random.default_rng(seed)
    p = p.copy()
    for _, idx in p.groupby("uid").groups.items():
        perm = rng.permutation(idx)
        p.loc[idx, OUTCOMES] = p.loc[perm, OUTCOMES].to_numpy()
    return p


if __name__ == "__main__":
    out = ROOT / "data/interim"
    panel = build()
    if "--unblind" in sys.argv:
        panel.to_parquet(out / "panel.parquet")
        print("wrote UNBLINDED panel")
    else:
        blind(panel).to_parquet(out / "panel_blind.parquet")
        print("wrote blinded panel")
    u = panel[panel["usable"]]
    print(f"rows {len(panel)}, usable {len(u)}, users {u['uid'].nunique()}")
