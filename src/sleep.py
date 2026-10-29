"""Nightly sleep table and regularity exposures.

One row per (uid, night), where night = dateOfSleep (the wake-up date), so a
night aligns with the EMA answered later that same day.
"""
import numpy as np
import pandas as pd

MIN_ASLEEP_H, MAX_ASLEEP_H = 3, 14  # outside this range treated as device artefact
MAX_MID_H = 24  # midpoint no later than 12:00 on the wake-up date


def load_main_sleep(path):
    s = pd.read_parquet(path)
    n_raw = len(s)
    s = s[s["mainSleep"] == "True"].drop_duplicates("logId")
    s = s.assign(
        night=pd.to_datetime(s["dateOfSleep"]),
        start=pd.to_datetime(s["startTime"]),
        end=pd.to_datetime(s["endTime"]),
        asleep_h=s["minutesAsleep"].astype(float) / 60,
        efficiency=s["efficiency"].astype(float),
    )
    # Several main sleeps on one date: keep the longest.
    s = s.sort_values("asleep_h").drop_duplicates(["uid", "night"], keep="last")
    s = s[s["asleep_h"].between(MIN_ASLEEP_H, MAX_ASLEEP_H)]
    mid = s["start"] + (s["end"] - s["start"]) / 2
    # Clock hours counted from the noon before the night, so 23:00 -> 11, 03:00 -> 15.
    s["mid_h"] = (mid - (s["night"] - pd.Timedelta(hours=12))).dt.total_seconds() / 3600
    # Midpoint after noon of the wake-up date: a daytime sleep or a mislabelled date.
    s = s[s["mid_h"] <= MAX_MID_H]
    s.attrs["n_raw"] = n_raw
    return s[["uid", "night", "start", "end", "mid_h", "asleep_h", "efficiency"]].sort_values(["uid", "night"])


def add_exposures(s, window=7, min_nights=4):
    """Exposures for night t against the other nights in [t-window+1, t].

    A night is usable when it exists and the window holds >= min_nights nights.
    """
    out = []
    for uid, g in s.groupby("uid"):
        g = g.set_index("night").asfreq("D")
        prior = g[["mid_h", "asleep_h", "efficiency"]].shift(1).rolling(window - 1, min_periods=1)
        base = prior.mean()
        n_in_window = g["mid_h"].notna().astype(int).rolling(window, min_periods=1).sum()
        e = pd.DataFrame({
            "uid": uid,
            "mid_h": g["mid_h"],
            "asleep_h": g["asleep_h"],
            "efficiency": g["efficiency"],
            "mid_dev_min": (g["mid_h"] - base["mid_h"]).abs() * 60,
            "mid_shift_min": (g["mid_h"] - base["mid_h"]) * 60,
            "dur_dev_h": g["asleep_h"] - base["asleep_h"],
            "eff_dev": g["efficiency"] - base["efficiency"],
            "mid_sd7_min": g["mid_h"].rolling(window, min_periods=min_nights).std() * 60,
            "n_nights7": n_in_window,
        })
        out.append(e[g["mid_h"].notna()].reset_index())
    e = pd.concat(out, ignore_index=True)
    e["usable"] = e["n_nights7"] >= min_nights
    return e
