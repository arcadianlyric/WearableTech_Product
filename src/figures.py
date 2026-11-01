"""Report figures: primary model ORs and the robustness forest plot.

Usage: python src/figures.py
"""
from pathlib import Path

import arviz as az
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
FIG = ROOT / "reports/figures"
SERIES, REF, INK, INK2, SURFACE = "#2a78d6", "#a3a29c", "#0b0b0b", "#52514e", "#fcfcfb"
MDE = 1.35  # OR per sd at 80% power, analysis_plan.md section 6

plt.rcParams.update({
    "font.family": ["Helvetica Neue", "Arial", "DejaVu Sans", "sans-serif"],
    "axes.unicode_minus": False, "figure.facecolor": SURFACE, "axes.facecolor": SURFACE,
    "axes.edgecolor": REF, "axes.labelcolor": INK2, "xtick.color": INK2, "ytick.color": INK,
    "axes.spines.top": False, "axes.spines.right": False, "axes.spines.left": False,
})

TERMS = {
    "mid_dev_w": "Sleep midpoint deviation (within-person)",
    "mid_dev_b": "Sleep midpoint deviation (between-person)",
    "dur_dev_w": "Sleep duration deviation (within-person)",
    "dur_dev_b": "Sleep duration deviation (between-person)",
    "weekend": "Weekend (yes/no)",
    "study_week_z": "Study week",
}
CHECKS = {
    "0 primary": "Primary analysis",
    "1 min nights 3": "1 Window with >= 3 nights",
    "1 min nights 5": "1 Window with >= 5 nights",
    "2 first report before 13:00": "2 First report before 13:00",
    "3 all reports, 3-level": "3 All reports (3-level model)",
    "4 outcome TENSE/ANXIOUS or SAD": "4 Outcome: tense/anxious or sad",
    "5a exposure: 7-night sd of midpoint": "5a Exposure: 7-night midpoint sd",
    "5b exposure: efficiency deviation": "5b Exposure: efficiency deviation",
    "6 H3 negative control: next night": "6 Negative control: next night",
    "9 raw minutes, winsorised 99%": "9 Raw minutes (99% winsorised)",
    "8 leave-one-person-out (GEE OR range)": "8 Leave-one-person-out (GEE range)",
}


def interval_plot(ax, labels, est, lo, hi, emphasize=None):
    y = np.arange(len(labels))[::-1]
    ax.axvline(1, color=REF, lw=1, zorder=0)
    ax.hlines(y, lo, hi, color=SERIES, lw=2)
    ax.scatter(est, y, s=64, color=SERIES, edgecolor=SURFACE, linewidth=2, zorder=3)
    ax.set_yticks(y, labels)
    ax.tick_params(axis="y", length=0)
    ax.set_xscale("log")
    ticks = [t for t in (0.6, 0.7, 0.8, 0.9, 1, 1.25, 1.5, 2) if min(lo) * 0.95 <= t <= max(hi) * 1.05 or t == 1]
    ax.set_xticks(ticks, [f"{t:g}" for t in ticks])
    ax.xaxis.set_minor_formatter(plt.NullFormatter())
    ax.grid(axis="x", color=REF, alpha=0.3, lw=0.5)
    if emphasize is not None:
        ax.get_yticklabels()[emphasize].set_fontweight("bold")
    for yi, e, l, h in zip(y, est, lo, hi):
        ax.text(1.02, yi, f"{e:.2f} ({l:.2f}-{h:.2f})", transform=ax.get_yaxis_transform(),
                color=INK2, fontsize=8, va="center", ha="left")


def main_or():
    idata = az.from_netcdf(ROOT / "reports/main/main_idata.nc")
    post = idata.posterior
    rows = [(TERMS[t], *np.exp(np.quantile(post[t].values.ravel(), [0.5, 0.025, 0.975]))) for t in TERMS]
    lab, est, lo, hi = zip(*rows)
    fig, ax = plt.subplots(figsize=(7.5, 3.6))
    interval_plot(ax, lab, est, lo, hi, emphasize=0)
    ax.set_xlabel("Odds ratio (OR) per 1 standard deviation (log scale)")
    ax.set_title('Primary model: first report is "tired" (1,587 days, 53 people)', loc="left", color=INK, fontsize=11)
    fig.savefig(FIG / "main_or.png", dpi=200, bbox_inches="tight")


def forest():
    r = pd.read_csv(ROOT / "reports/robustness.csv")
    r = r[r["check"].isin(CHECKS)].set_index("check").loc[[c for c in CHECKS if c in set(r["check"])]]
    lab = [CHECKS[c] + (f"   n={int(n)}" if pd.notna(n) else "") for c, n in zip(r.index, r["n_days"])]
    fig, ax = plt.subplots(figsize=(7.5, 4.8))
    interval_plot(ax, lab, r["OR"], r["OR_lo"], r["OR_hi"], emphasize=0)
    ax.axvline(MDE, color=INK2, lw=1, ls=(0, (3, 3)), zorder=0)
    ax.text(MDE, len(lab) - 0.45, "80% power ", color=INK2, fontsize=8, ha="right", va="center")
    ax.set_xlabel("OR per 1 standard deviation of within-person exposure (log scale)")
    ax.set_title("H1 robustness: within-person effect across analyses", loc="left", color=INK, fontsize=11)
    fig.savefig(FIG / "robustness_forest.png", dpi=200, bbox_inches="tight")


if __name__ == "__main__":
    FIG.mkdir(parents=True, exist_ok=True)
    main_or()
    forest()
