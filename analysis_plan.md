# Analysis plan: sleep timing irregularity and next-day tiredness (LifeSnaps)

**Status: frozen before unblinding.** Everything below was decided with the
mood outcomes permuted within each person (`src/build_panel.py`, seed 20261029).
Any change after the commit that unblinds the data is labelled *post hoc* in the report.

## 1. Question and hypotheses

On days when a person's sleep timing departs more from their own recent pattern,
are they more likely to report feeling tired the next day, and how much does that
sensitivity differ between people?

- **H1 (primary).** Within-person deviation of last night's sleep midpoint from the
  person's previous nights is positively associated with the first mood report of
  the day being TIRED, adjusting for within-person deviation in sleep duration.
- **H2 (exploratory).** The H1 slope varies between people (sd of random slope > 0).
- **H3 (negative control).** The *following* night's midpoint deviation does not
  predict today's first mood report.

Observational data: results are associations, not effects of changing sleep.

## 2. Data and exclusions

LifeSnaps v4 (Zenodo 7229547, CC-BY-4.0). Raw BSON parsed with `src/extract_bson.py`.

| Step | Rows |
|---|---|
| Fitbit sleep records | 4,141 |
| Main sleep only | 3,688 |
| Dedupe by `logId` | 3,415 |
| One main sleep per (person, night), longest kept; 3–14 h asleep; midpoint ≤ 12:00 on wake date | 3,280 nights |
| Context and Mood Survey prompts | 11,526 |
| Completed with an on-questionnaire mood (7 labels; 10 off-list labels dropped) | 5,027 reports, 63 people |
| Person-days with ≥ 1 mood report | 2,288 |
| Joined to last night's sleep | 1,716 |
| **Analysis set**: window of 7 nights ending last night holds ≥ 4 nights | **1,587 days, 53 people** |

Night = Fitbit `dateOfSleep` (wake-up date), so it aligns with that day's reports.

## 3. Variables

**Outcome (primary).** `tired`: first mood report of the day is TIRED (base rate 15.1%).

**Exposure (primary).** `mid_dev` = log(1 + |midpoint_t − mean midpoint of the other
nights in the 7-night window|), in minutes. Log because the raw deviation is
right-skewed (median 34 min, max 544 min).

**Adjustment.** `dur_dev` = hours asleep last night − mean of the other nights in the
window (signed). Weekend day; study week (z-scored).

Both exposures are split into a person mean (`_b`) and the deviation from it
(`_w`), each scaled to sd 1, so coefficients are per 1 sd.

Not in the main model: previous-day steps (possible mediator), age band, sex,
BMI band (released only as coarse bins: age <30 / ≥30, BMI <25 / ≥25).

## 4. Primary model

```
tired ~ mid_dev_w + mid_dev_b + dur_dev_w + dur_dev_b + weekend + study_week_z
        + (1 + mid_dev_w | uid)          Bernoulli, logit link
```

Bambi 0.21 / PyMC 6.3 default weakly informative priors; 4 chains × 1,000 draws
after 1,000 tuning, `target_accept=0.95`. Convergence required: R-hat ≤ 1.01 and
bulk ESS ≥ 400 for every reported parameter.

**Reported:** posterior median OR per 1 sd of `mid_dev_w` with 95% interval;
P(β_w > 0); random-slope sd; the range of person-level ORs implied by mean ± 1.96 sd.

**Decision rule for H1.** Supported if the 95% interval for OR(`mid_dev_w`) excludes 1
on the positive side. If it includes 1, the result is reported as "no evidence of
an effect larger than the detectable size" (Section 6), not as "no effect".

**Cross-check.** GEE logistic, exchangeable working correlation, same fixed effects.

## 5. Robustness (secondary; FDR-corrected across this list)

1. Minimum nights in the 7-night window: 3, 5 (main: 4).
2. Only days whose first report is before 13:00 (66% of days).
3. All reports of the day: three-level model (report in day in person), outcome TIRED.
4. Secondary outcome: first report is TENSE/ANXIOUS or SAD.
5. Secondary exposures: 7-night sd of midpoint; efficiency deviation.
6. H3 negative control: replace exposures with the following night's deviations.
7. Missingness: model whether a day has a mood report / a night has a sleep record
   from the previous day's state; report direction of any bias.
8. Leave-one-person-out: range of OR(`mid_dev_w`).
9. Raw `mid_dev` minutes winsorised at the 99th percentile instead of log.

## 6. Power (simulated on the real panel structure)

`src/power.py`: real people, days and exposures; simulated outcomes with
between-person intercept sd 1.0 and slope sd 0.3; 200 simulations per OR; power =
share of GEE fits with two-sided p < 0.05 and a positive estimate.

| OR per 1 sd | 1.1 | 1.2 | 1.3 | 1.5 | 1.75 |
|---|---|---|---|---|---|
| Power | 0.15 | 0.48 | 0.73 | 0.99 | 1.00 |

80% power is reached at roughly OR ≈ 1.35 per sd. Smaller true effects are likely
to be missed. H2 is underpowered by design and is reported as an estimate with
its uncertainty only.

## 7. Known limits of the blinding

Permuting outcomes within person keeps each person's base rate, so it hides
within-person associations (H1, H2, H3) but **not** between-person ones. The blinded
pipeline run therefore showed the between-person coefficient (GEE: `mid_dev_b`
β = 0.33, p = 0.001, i.e. people with more irregular timing on average report
TIRED more often). This term is an adjustment covariate, not a hypothesis, and is
reported as already seen. The blinded within-person estimate was OR 1.00
(95% interval 0.85–1.18), as expected under permutation.

## 8. Replication (planned, separate plan addendum before running)

PMData (16 people, daily 1–5 fatigue/mood/readiness): same exposure definitions,
cumulative-logit mixed model. "Replicated in direction" = same sign with
overlapping intervals.
