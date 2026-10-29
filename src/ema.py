"""Mood EMA cleaning: one row per completed Context and Mood Survey."""
import pandas as pd

MOODS = ["RESTED/RELAXED", "TIRED", "NEUTRAL", "HAPPY", "TENSE/ANXIOUS", "ALERT", "SAD"]
NEGATIVE = {"TENSE/ANXIOUS", "SAD"}


def load_mood(path):
    e = pd.read_parquet(path)
    n_raw = len(e)
    e = e[e["COMPLETED_TS"].notna() & e["MOOD"].isin(MOODS)].copy()  # drops off-questionnaire labels
    e["ts"] = pd.to_datetime(e["COMPLETED_TS"])
    e["day"] = e["ts"].dt.normalize()
    e["tired"] = (e["MOOD"] == "TIRED").astype(int)
    e["negative"] = e["MOOD"].isin(NEGATIVE).astype(int)
    e = e.sort_values(["uid", "ts"]).drop_duplicates(["uid", "ts"])
    e.attrs["n_raw"] = n_raw
    return e[["uid", "ts", "day", "MOOD", "PLACE", "tired", "negative"]]


def daily_outcomes(e):
    """First EMA of each day plus the day's share of TIRED answers."""
    first = e.groupby(["uid", "day"]).head(1).rename(columns={"ts": "first_ts", "MOOD": "first_mood"})
    agg = e.groupby(["uid", "day"]).agg(n_ema=("tired", "size"), tired_share=("tired", "mean"),
                                       negative_share=("negative", "mean"))
    d = first.merge(agg.reset_index(), on=["uid", "day"])
    d["first_hour"] = d["first_ts"].dt.hour + d["first_ts"].dt.minute / 60
    return d.drop(columns=["PLACE"])
