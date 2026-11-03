"""Exploratory: the sleep-and-load ledger table, and absolute thresholds vs the personal baseline.

Usage: python src/posthoc_ledger.py data/interim/panel.parquet reports/causal/ledger.csv
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
from build_panel import SEED  # noqa: E402
from models import prepare  # noqa: E402
from posthoc_good_nights import add_daily  # noqa: E402


def person_ci(flagged, n=2000, seed=SEED):
    """Tired share with a person-level bootstrap interval."""
    by = flagged.groupby("uid")["tired"].agg(["sum", "size"])
    rng = np.random.default_rng(seed)
    idx = rng.integers(len(by), size=(n, len(by)))
    b = by["sum"].to_numpy()[idx].sum(1) / by["size"].to_numpy()[idx].sum(1)
    return flagged["tired"].mean(), *np.quantile(b, [0.025, 0.975])


if __name__ == "__main__":
    p = add_daily(prepare(pd.read_parquet(sys.argv[1])))
    p["slept_less"] = p["dur_dev_h"] < 0
    p["trained_more"] = p["active_prev"] > p.groupby("uid")["active_prev"].transform("mean")
    p["slept_7h"] = p["asleep_h"] >= 7
    cells = {"slept_ok_trained_usual": p[~p["slept_less"] & ~p["trained_more"]],
             "slept_ok_trained_more": p[~p["slept_less"] & p["trained_more"]],
             "slept_less_trained_usual": p[p["slept_less"] & ~p["trained_more"]],
             "slept_less_trained_more": p[p["slept_less"] & p["trained_more"]],
             "slept_7h_plus": p[p["slept_7h"]], "slept_under_7h": p[~p["slept_7h"]]}
    rows = []
    for name, d in cells.items():
        share, lo, hi = person_ci(d)
        rows.append({"cell": name, "n_days": len(d), "n_tired": int(d["tired"].sum()), "tired_share": share,
                     "lo": lo, "hi": hi})
    rows.append({"cell": "share of all days with 7h+", "tired_share": p["slept_7h"].mean()})
    rows.append({"cell": "share of tired days with 7h+", "tired_share": p.loc[p["tired"].eq(1), "slept_7h"].mean()})
    out = pd.DataFrame(rows)
    out.to_csv(sys.argv[2], index=False)
    print(out.round(3).to_string())
