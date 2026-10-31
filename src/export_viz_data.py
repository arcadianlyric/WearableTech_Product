"""Export aggregated data for the interactive page (visualization/index.html).

Two views, both aggregated only; no person-level row leaves this script.

1. Gap matrix (retrospective): "body data looks fine" vs "feels tired", using the same
   person-mean z-scores as masked_strain() in posthoc_good_nights.py.
2. Alert simulator (what a shipped rule could know): every z-score uses only the previous
   W days, and alert load counts all device days, not just days with a mood report.

CIs are person-level bootstrap. Any figure resting on fewer than MIN_PEOPLE people is suppressed.

Usage: python src/export_viz_data.py data/interim/panel.parquet visualization/data.json
"""
import json
import sys
from itertools import product
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
from build_panel import BSON, DAILY_CSV, SEED  # noqa: E402
from ema import daily_outcomes, load_mood  # noqa: E402
from posthoc_good_nights import add_daily  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
SIGNALS = ["resting_hr", "nremhr", "rmssd"]
SIGN = {"resting_hr": 1, "nremhr": 1, "rmssd": -1}  # +z always means "more strained"
SLEEP_H = [6, 6.5, 7, 7.5, 8]
STRAIN_SD = [0.5, 0.75, 1, 1.25, 1.5]
GROUPS = {"all": None, "women": 1, "men": 0}
RULE_SIGNALS, RULE_DAYS, RULE_SD, RULE_WINDOW = [1, 2, 3], [1, 2, 3], [1, 1.5, 2], [14, 21, 28]
DEFAULT_RULE = {"signals": 2, "days": 2, "sd": 1, "window": 14}  # from README insight 7, fixed before any rule was run
NEXT_DAYS = 3
MIN_PEOPLE, MIN_DAYS = 5, 20
N_BOOT = 1000


def ratio_ci(num, den, rng, scale=1.0):
    """Pooled ratio with a person-level bootstrap CI. num and den are per-person totals."""
    if den.sum() == 0:
        return None, None, None
    idx = rng.integers(0, len(num), (N_BOOT, len(num)))
    n, d = num[idx].sum(1), den[idx].sum(1)
    b = n[d > 0] / d[d > 0] * scale
    return float(num.sum() / den.sum() * scale), float(np.quantile(b, 0.025)), float(np.quantile(b, 0.975))


def pct(est):
    return dict(zip(["est", "lo", "hi"], [None if v is None else round(v, 4) for v in est]))


def person_sum(flag, uid, people):
    return flag.groupby(uid).sum().reindex(people, fill_value=0).to_numpy(float)


def gap_matrix(panel, rng):
    p = add_daily(panel[panel["usable"]].copy())
    full = p.copy()
    p = p.dropna(subset=SIGNALS).copy()
    g = p.groupby("uid")
    z = pd.DataFrame({c: SIGN[c] * (p[c] - g[c].transform("mean")) / g[c].transform("std") for c in SIGNALS})
    cells, hero = [], []
    for group, sex in GROUPS.items():
        keep = p["female"].eq(sex) if sex is not None else pd.Series(True, index=p.index)
        d, zg = p[keep], z[keep]
        people = np.sort(d["uid"].unique())
        total = person_sum(pd.Series(1, index=d.index), d["uid"], people)
        for h, sd in product(SLEEP_H, STRAIN_SD):
            strained = (zg >= sd).any(axis=1)
            fine = (d["asleep_h"] >= h) & ~strained
            tired = d["tired"] == 1
            row = {"group": group, "sleep_h": h, "strain_sd": sd, "n_days": len(d), "n_people": len(people),
                   "strain_share": pct(ratio_ci(person_sum(strained, d["uid"], people), total, rng)),
                   "agreement": pct(ratio_ci(person_sum(fine != tired, d["uid"], people), total, rng))}
            for name, flag in {"fine_tired": fine & tired, "fine_ok": fine & ~tired,
                               "off_tired": ~fine & tired, "off_ok": ~fine & ~tired}.items():
                n_people = d.loc[flag, "uid"].nunique()
                row[name] = {"suppressed": True} if n_people < MIN_PEOPLE else {
                    **pct(ratio_ci(person_sum(flag, d["uid"], people), total, rng)),
                    "n_days": int(flag.sum()), "n_people": int(n_people)}
            # A column's two cells sum to its total, so suppressing one alone would reveal it
            for a, b in [("fine_tired", "fine_ok"), ("off_tired", "off_ok")]:
                if row[a].get("suppressed") or row[b].get("suppressed"):
                    row[a] = row[b] = {"suppressed": True}
            row["fine_share"] = pct(ratio_ci(person_sum(fine, d["uid"], people), total, rng))
            cells.append(row)
        f = full[full["female"].eq(sex)] if sex is not None else full
        t = f[f["tired"] == 1]
        pp = np.sort(t["uid"].unique())
        for h in SLEEP_H:
            hero.append({"group": group, "sleep_h": h, "n_tired_days": len(t), "n_people": len(pp),
                         **pct(ratio_ci(person_sum(t["asleep_h"] >= h, t["uid"], pp),
                                        person_sum(pd.Series(1, index=t.index), t["uid"], pp), rng))})
    return cells, hero


def device_days(window):
    """Calendar-indexed device days with trailing-baseline z-scores (past days only)."""
    d = pd.read_csv(DAILY_CSV, usecols=["id", "date", *SIGNALS]).rename(columns={"id": "uid"})
    d["day"] = pd.to_datetime(d["date"])
    d = d.groupby(["uid", "day"])[SIGNALS].mean().reset_index()
    min_days = max(7, window // 2)
    out = []
    for uid, g in d.groupby("uid"):
        g = g.set_index("day").asfreq("D")
        z = pd.DataFrame(index=g.index)
        for c in SIGNALS:
            prior = g[c].shift(1).rolling(window, min_periods=min_days)
            z[c] = (SIGN[c] * (g[c] - prior.mean()) / prior.std()).replace([np.inf, -np.inf], np.nan)
        z["uid"] = uid
        out.append(z.reset_index())
    return pd.concat(out, ignore_index=True)


def mood_days():
    e = daily_outcomes(load_mood(BSON / "sema/context_and_mood_survey.parquet"))
    m = e[["uid", "day", "tired"]].copy()
    ahead = []
    for uid, g in m.groupby("uid"):
        s = g.set_index("day")["tired"].asfreq("D")
        a = pd.concat([s.shift(-k) for k in range(1, NEXT_DAYS + 1)], axis=1).max(axis=1)
        ahead.append(pd.DataFrame({"uid": uid, "day": s.index, "tired_later": a.values}))
    return m.merge(pd.concat(ahead), on=["uid", "day"], how="left")


def simulate(rng):
    moods, rules, windows = mood_days(), [], {}
    for window in RULE_WINDOW:
        z = device_days(window)
        z["evaluable"] = z[SIGNALS].notna().all(axis=1)
        z = z[z["evaluable"]].merge(moods, on=["uid", "day"], how="left").sort_values(["uid", "day"])
        people = np.sort(z["uid"].unique())
        days = person_sum(pd.Series(1, index=z.index), z["uid"], people)
        mood = z["tired"].notna()
        tired = z["tired"] == 1
        base = pct(ratio_ci(person_sum(tired, z["uid"], people), person_sum(mood, z["uid"], people), rng))
        windows[window] = {"n_days": len(z), "n_people": len(people), "n_mood_days": int(mood.sum()),
                           "n_tired_days": int(tired.sum()), "base_rate": base}
        # Calendar gaps must break a streak, so compare with the previous calendar day explicitly
        new_run = (z["uid"] != z["uid"].shift()) | (z["day"] - z["day"].shift() != pd.Timedelta(days=1))
        for k, d, sd in product(RULE_SIGNALS, RULE_DAYS, RULE_SD):
            hit = (z[SIGNALS] >= sd).sum(axis=1) >= k
            run = hit.groupby((new_run | ~hit).cumsum()).cumsum()
            flagged = run >= d
            onset = flagged & (run == d)  # one alert per episode, however long it lasts
            n_people = z.loc[onset, "uid"].nunique()
            r = {"signals": k, "days": d, "sd": sd, "window": window,
                 "alerts_30d": pct(ratio_ci(person_sum(onset, z["uid"], people), days, rng, 30)),
                 "people_alerted": int(n_people), "people_total": len(people), "flagged_share": round(float(flagged.mean()), 4)}
            fm = flagged & mood
            r["n_flagged_mood_days"] = int(fm.sum())
            usable = fm.sum() >= MIN_DAYS and z.loc[fm, "uid"].nunique() >= MIN_PEOPLE
            r["precision"] = pct(ratio_ci(person_sum(fm & tired, z["uid"], people),
                                          person_sum(fm, z["uid"], people), rng)) if usable else None
            r["coverage"] = pct(ratio_ci(person_sum(flagged & tired, z["uid"], people),
                                         person_sum(tired, z["uid"], people), rng)) if usable else None
            calm = (z["tired"] == 0) & z["tired_later"].notna()
            fc, nc = calm & flagged, calm & ~flagged
            r["later"] = None
            if fc.sum() >= MIN_DAYS and z.loc[fc, "uid"].nunique() >= MIN_PEOPLE:
                later = z["tired_later"] == 1
                r["later"] = {"flagged": pct(ratio_ci(person_sum(fc & later, z["uid"], people),
                                                      person_sum(fc, z["uid"], people), rng)),
                              "not_flagged": pct(ratio_ci(person_sum(nc & later, z["uid"], people),
                                                          person_sum(nc, z["uid"], people), rng))}
            rules.append(r)
    return rules, windows


def check(cells, hero):
    """Defaults must reproduce the published reports, or nothing is written."""
    sizing = pd.read_csv(ROOT / "reports/posthoc_good_nights/sizing.csv").set_index("metric")["value"]
    strain = pd.read_csv(ROOT / "reports/posthoc_good_nights/masked_strain.csv").set_index("metric")["value"]
    h = next(x for x in hero if x["group"] == "all" and x["sleep_h"] == 7)
    c = next(x for x in cells if x["group"] == "all" and x["sleep_h"] == 7 and x["strain_sd"] == 1)
    assert abs(h["est"] - sizing["share of tired days after >= 7 h asleep"]) < 1e-3, h
    assert h["n_tired_days"] == sizing["tired days"], h
    assert abs(c["strain_share"]["est"] - strain["strain: share of days"]) < 1e-3, c
    assert c["n_days"] == strain["days with HR + HRV"] and c["n_people"] == strain["people"], c


def main(panel_path, out_path):
    rng = np.random.default_rng(SEED)
    cells, hero = gap_matrix(pd.read_parquet(panel_path), rng)
    check(cells, hero)
    rules, windows = simulate(rng)
    out = {"defaults": {"sleep_h": 7, "strain_sd": 1, "group": "all", "rule": DEFAULT_RULE},
           "limits": {"min_people": MIN_PEOPLE, "min_days": MIN_DAYS, "n_boot": N_BOOT, "next_days": NEXT_DAYS},
           "gap": cells, "hero": hero, "rules": rules, "windows": windows}
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    Path(out_path).write_text(json.dumps(out, separators=(",", ":")))
    d = next(r for r in rules if all(r[k] == v for k, v in DEFAULT_RULE.items()))
    print(json.dumps({"windows": windows, "default_rule": d}, indent=1))
    print(f"{len(cells)} gap cells, {len(rules)} rules, {Path(out_path).stat().st_size / 1024:.0f} KB")


if __name__ == "__main__":
    main(*sys.argv[1:3])
