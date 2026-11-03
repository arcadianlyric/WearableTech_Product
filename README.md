# WearableTech: the score looks fine, so why am I still tired?

> Fatigue works like a ledger: the sleep score records only the income, not the spending. Using LifeSnaps Fitbit data and daily mood check-ins, this project estimates the absolute effects of short sleep and training load on next-day tiredness in observational time series with no randomized experiment, and rules out several popular explanations.

English | [中文](README_CN.md) | [Interactive page](https://arcadianlyric.github.io/WearableTech_Product/)

## Impact

- **When both sides of the ledger are bad, the share of tired days is about 2.2 times the share when neither is.** This is the main thread of the project: tiredness depends on both how much sleep you got back and how much you spent yesterday, and the sleep score only sees the first. **The income side is robust**: sleeping 1 hour less on a single night raises next-day tiredness probability by 3.3 percentage points (95% credible interval 1.9–4.8), from a baseline of about 14.7%. The conclusion holds after correcting for missingness, with the negative-exposure control, and in all sensitivity analyses (post hoc).
- **The score explains only part of it.** After ≥ 7 h of sleep, 12.2% of days still report tiredness, versus 16.5% after < 7 h. Of the 40 people with at least one "good night", 15 (38%) have had a "slept well but still tired" day.
- **Three popular explanations were ruled out**: "keep a regular schedule" (pre-registered primary hypothesis, OR 1.09, 0.92–1.31), "warmer nights → worse mood" (within-person OR 1.00), and "not enough deep sleep" (OR 0.96 across all nights).
- **Side thread: after stratifying, the male-female gap is in mood, not in tiredness.** Women sleep 28 minutes longer on average and report tiredness at a similar rate (15.4% vs 14.3%), yet report negative mood about twice as often as men (23.6% vs 13.1%). Looking only at sleep and tiredness, this gap is invisible. See [Side thread: sex stratification](#side-thread-sex-stratification).

### Key words
Personalization, causal inference, observational time series, within-person effects, wearable product, Bayesian

## Background

The core selling point of products such as Whoop, Oura and Apple Watch is "recovery" and "readiness" advice based on personal data. This project started from my own experience with a wearable: some days the sleep score is high and duration and deep sleep are both fine, yet I am tired the next day.

The project began by testing the most common advice in the industry, "keep a regular schedule". The pre-registered test did not support it, and the question worth asking changed: users feel tired while the data looks normal, so how common is that, what causes it, and which users are affected most? That turn is preserved in [Results](#results), and every result is labelled with its level of evidence.

Existing public work has three common problems: it mixes between-person and within-person effects, it splits train and test sets randomly by day and leaks information, and it adjusts the analysis after seeing the results. The more useful question for a product is **within-person**: when something changes for the same person on one day, what happens to the next day? Regular sleepers are healthier overall, but that between-person comparison is confounded by personality, work, age and much else, so it cannot answer this question.

**The project has three innovations.** First, it treats tiredness as the outcome; earlier work on LifeSnaps largely excluded it. Second, it replaces "predict tiredness" with "estimate the absolute effect of one change", which a product can use directly for decisions. Third, it writes false negatives, confounding and missingness as testable hypotheses instead of leaving them in a limitations paragraph.

I chose LifeSnaps [1] (CC-BY-4.0, freely downloadable) over GLOBEM [2] (requires PhysioNet credentialed access) because LifeSnaps moods are answered **daily**, finer than GLOBEM's weekly questionnaires. The model is a Bayesian hierarchical model (Bambi/PyMC) because with 53 people, frequentist models often hit singular fits when estimating random slopes; the Bayesian approach gives the posterior of the slope standard deviation directly and does not quietly estimate it as 0.

## Methods in brief

The full data processing, model specification, reproduction commands and project structure are in [SUPPLEMENT.md](SUPPLEMENT.md) (bilingual).

**Data.** LifeSnaps, 1,587 person-days from 53 people. The outcome is whether the first EMA of the day (Ecological Momentary Assessment, a short mood check-in pushed during daily life) was "tired". All exposures are computed relative to the person's own baseline.

**Estimand.** Shift each day's actual exposure by a fixed amount and compare the tiredness probability before and after the shift. The main quantity is the risk difference (percentage points).

| | E1: income | E2: spending |
|---|---|---|
| Intervention | Actual sleep on one night −1 hour | Vigorous activity the previous day +30 minutes |
| Key adjustment | Control for yesterday's activity (confounder) | Do not control for last night's sleep (mediator) |

**Problems and approaches.**

| Problem | Approach |
|---|---|
| Individual differences | Within/between-person decomposition, hierarchical model with random slopes |
| Absolute effect | Bayesian g-computation |
| Time-varying confounding | Adjustment set fixed by temporal order |
| About 43% of person-days missing | Two-step IPW plus an MNAR tipping-point analysis |
| Unmeasured confounding | Negative-exposure controls and E-values |

**Decision rule** (frozen). The causal reading is stated only if all three hold: the Bayesian risk-difference interval excludes 0 in the expected direction, IPW agrees in direction, and the negative-control interval includes 0. Then the wording is "supports a causal interpretation under the stated assumptions".

**Lock the analysis before looking at results.** The main analysis was run on outcome-blinded data before the plan was committed (`4f44e67`). The causal analysis is post hoc, but its estimands and decision rule were also frozen first (`e15e766`).

**Levels of evidence.** Everything below is labelled **pre-specified** (frozen before unblinding), **post hoc** (with a written specification) or **exploratory** (not specified in advance, hypothesis-generating only).

## Results

### 1. How large is the gap: the score explains part of it, not all (exploratory)

- Across all days, 42.5% followed ≥ 7 h of sleep; among the 233 tired days, 35.2% did. Sleeping 7 h or more helps, but it separates poorly: 12.2% tired vs 16.5%.
- A "good night" is defined as ≥ 7 h of sleep with efficiency at or above the median: 384 nights (24% of all days) from 40 people. The tired share after these nights is 9.6% versus 14.7% overall, yet 16% of tired days still come after them.
- 15 of the 40 people have had at least one "slept well but still tired" day.

**Stratifying by both sides of the ledger (unadjusted, descriptive).** Crossing whether last night was shorter than the person's usual with whether yesterday's activity was above the person's usual:

| Share tired on the first check-in the next day | Yesterday's activity not above usual | Yesterday's activity above usual |
|---|---|---|
| **Last night not shorter than usual** | 9.6% (6.8–12.7) | 13.3% (8.7–18.4) |
| **Last night shorter than usual** | 16.6% (12.1–21.2) | **21.5% (14.6–29.3)** |

*1,587 days, 53 people; brackets are 95% person-level bootstrap intervals. This is an unadjusted exploratory description; adjusted effects follow below.*

When both sides are bad (21.5%), the tired share is about 2.2 times that when neither is (9.6%). Adjusted effects are in sections 3 to 5 below.

### 2. Explanations that were ruled out

**Schedule regularity (pre-specified)**

![Main model](reports/figures/main_or.png)

*Figure 1: Posterior median OR per 1 SD of each exposure with 95% credible intervals (weekend is a yes/no variable; its OR is weekend vs weekday). Values are printed to the right.*

| Parameter | OR (median) | 95% credible interval |
|---|---|---|
| **Sleep midpoint deviation, within person (H1)** | **1.09** | **0.92–1.31** |
| Sleep midpoint deviation, between people | 1.23 | 0.96–1.56 |
| Sleep duration deviation, within person | 0.73 | 0.63–0.85 |
| Sleep duration deviation, between people | 0.94 | 0.78–1.12 |
| Weekend | 1.35 | 0.97–1.86 |
| Random-slope SD (logit scale) | 0.20 | 0.01–0.47 |

- **H1 is not supported.** Under the decision rule written in advance (the interval must exclude 1), deviation in sleep timing shows no detectable within-person link to next-day tiredness. P(β > 0) = 0.83, leaning positive, but the effect is smaller than the design can detect.
- **H2 (individual differences) cannot be judged.** The posterior of the random-slope SD runs from 0.01 to 0.47. That implies person-level ORs of roughly 0.76–1.56, too wide to tell "everyone is the same" from "some people are sensitive and others are not".
- **The H3 negative control also supports "no specificity".** Using the deviation of the *following* night to "predict" today's tiredness gives OR 1.04, almost the same as the main estimate of 1.09.

![Robustness](reports/figures/robustness_forest.png)

*Figure 2: Point estimates and 95% intervals for the within-person sleep midpoint effect under each robustness check. The dashed line is the smallest OR detectable with 80% power (1.35, analysis plan section 6).*

The ORs from the 9 robustness analyses all lie between 0.93 and 1.10 and none has an interval excluding 1; the FDR-adjusted GEE p-values are all ≥ 0.71. Yesterday's tiredness predicts neither a missing report the next day (OR 0.85, 0.65–1.12) nor a missing sleep record that night (OR 1.07, 0.85–1.34). Leaving out one person at a time, the GEE OR stays between 1.03 and 1.10, so no single person drives the result.

**Nightly skin temperature (post hoc)**

Earlier work [3] reported that higher nightly temperature is the strongest predictor of feeling sad or tense, but it did not separate between-person from within-person variation. The supplementary plan is in `analysis_addendum_temperature.md`, written before the analysis was run. The sample is 1,551 days from 51 people.

| Outcome | Pooled (as in the original study) | Within person | Between people (sex-adjusted) | Women |
|---|---|---|---|---|
| Tense/anxious or sad | **1.24** (1.08–1.43), p = 0.002 | 1.00 (0.81–1.20) | 1.09 (0.76–1.57) | **2.50** (1.14–5.57) |
| Happy | **0.85** (0.73–0.97), p = 0.02 | 1.00 (0.85–1.21) | 0.82 (0.58–1.22) | 1.87 (0.83–4.39) |
| Tired | 0.90 (0.79–1.04) | 1.06 (0.87–1.31) | 0.79 (0.59–1.05) | 1.09 (0.56–2.09) |

Pooled, we **reproduced** the original association. But on days when a person's temperature is higher than their own usual, negative mood does not increase (OR 1.00). After controlling for sex, the between-person temperature effect also largely disappears. The association mostly reflects *who* (especially sex), not *which day*.

**Other sleep and physiology measures (exploratory)**

Among "good nights", ten within-person deviation measures were screened one at a time (`reports/posthoc_good_nights/screen.csv`):

| Compared with the person's usual | OR (per 1 SD) | p |
|---|---|---|
| More vigorous activity the previous day (1 SD ≈ 31 min) | **1.65** (1.24–2.20) | 0.001 |
| Deep-sleep share vs the person's 30-day mean | **0.72** (0.59–0.89) | 0.002 |
| Sleep midpoint shift; wake time | 0.76; 0.80 | ≥ 0.20 |
| Resting HR; NREM HR; HRV | 0.89; 1.05; 0.94 | ≥ 0.47 |
| Sleep debt over the previous 3 nights; last night shorter than usual | 0.93; 0.94 | ≥ 0.71 |

Deep-sleep share is not reliable: in the same model it is only marginal in the good-night subset (0.78, p = 0.04) and 0.96 (0.81–1.13) across all nights.

### 3. Income side: 1 hour less sleep (post hoc)

Sleep-duration deviation was only a control variable in advance, but its association is strong, so a negative control was added: in the same sample, the OR for the previous night is 0.71 (0.60–0.85) and for the following night 1.06 (0.94–1.20). The absolute effect was then estimated under the frozen plan.

**E1 passes every decision rule.** Sleeping 1 hour less on one night raises next-day tiredness probability by 3.3 percentage points (1.9–4.8). The result holds in every sensitivity analysis, shown in the table below.

### 4. Spending side: 30 more minutes of training (post hoc + exploratory)

Exploratory analysis found the lead first: among good nights, the OR for more vigorous activity the previous day is 1.76 (1.24–2.50), across all nights 1.22 (1.04–1.44), and the negative control using the *next* day's activity gives 0.95 (0.83–1.08). The good-night subset has only 37 tired days, so the 1.76 should not be read as an effect size.

**E2 also passes the decision rule, but its evidence is clearly weaker than E1's.** Training 30 minutes more the previous day raises next-day tiredness probability by 3.1 percentage points (1.0–5.5). Vigorous activity is 0 minutes on 52% of days, so linearity is a strong assumption; with a quadratic term or `log1p`, the intervals include 0. Controlling for last night's sleep, the direct effect is +2.7 (0.9–5.1), close to the total effect, which suggests most of the effect of activity does not run through sleep duration.

### 5. The full ledger (`reports/causal/`)

About 1,560 days from 50 people; baseline tiredness probability about 14.7%. The 3 people missing relative to the analysis set each contribute 1 day and lack the previous 3 nights of sleep. RD is in percentage points.

| Analysis | E1: 1 h less sleep | E2: 30 min more training |
|---|---|---|
| **Bayesian g-computation (primary)** | **+3.3 (1.9–4.8)** | **+3.1 (1.0–5.5)** |
| Risk ratio | 1.23 (1.13–1.33) | 1.21 (1.07–1.37) |
| IPW for missingness | +3.4 (1.5–5.5) | +2.5 (0.6–5.2) |
| Negative-exposure control | −0.3 (−1.5–0.8) | −0.6 (−2.3–0.9) |
| Unweighted logistic | +3.4 (1.7–5.4) | +2.3 (0.5–4.8) |
| Adding yesterday's tiredness | +3.6 (1.5–5.6) | +2.9 (0.9–6.4) |
| First report before 13:00 only | +3.9 (1.8–6.2) | +3.0 (**−0.4**–5.7) |
| Adding sleep midpoint deviation | +3.1 (1.6–5.0) | n/a |
| Quadratic term | +3.4 (1.4–5.4) | +1.6 (**−0.7**–4.2) |
| `log1p` activity | n/a | +1.8 (**−0.7**–4.6) |
| E-value (point / interval end) | 1.76 / 1.51 | 1.71 / 1.35 |
| MNAR tipping point δ | between 2 and 3 | between 0.5 and 1 |

- **Reading δ.** δ = 2 means that on the unfavourable missing days, the odds of tiredness are about 7.4 times what the model predicts. E1 flips only beyond roughly this level; for E2 the interval already includes 0 at about 2.7 times (δ = 1).
- **Reading the E-value.** An unmeasured confounder would need to be associated with both the exposure and the outcome by about 1.35–1.51 times to make the interval include 1. That is not high; illness or work stress could reach it.
- **Model difference.** The unweighted logistic has no random effects, so its E2 estimate of 2.3 is lower than the Bayesian 3.1; this is a model difference. All parameters converged: R-hat ≤ 1.007, bulk ESS ≥ 952.
- **Feedback confounding.** Adding yesterday's tiredness does not shrink either estimate, so it is not a major threat for now.

## Side thread: sex stratification

Epidemiology stratifies first because a pooled average can hide differences and create artefacts at the same time. Products are the same: if you look only at the average over all users, none of the gaps below appear. So this side thread is not just a subgroup analysis; it determines how a product's baseline, evaluation and release gates should work (post hoc + exploratory).

**User pain point.** Women's sleep data looks fine but their emotional burden is heavier; their temperature and heart rate also change normally with the cycle, and a generic score can read that change as "poor recovery".

### Evidence from the data

`reports/causal/sex_strata.csv`, 51 people with sex recorded:

| Stratified measure | Men (31 people, 970 days) | Women (20 people, 598 days) |
|---|---|---|
| Share of days with a first report of tired | 14.3% | 15.4% |
| Share of days with a first report of tense/anxious or sad | 13.1% | **23.6%** |
| Negative-mood share, person-level median | 7.5% | **23.4%** |
| Mean actual sleep | 6.50 h | 6.97 h |

- **The gap is in mood, not in tiredness.** Women sleep 28 minutes longer on average and report tiredness at a similar rate, yet report negative mood about twice as often (OR 2.50 after adjustment). Neither the sleep score nor the tiredness check-in shows this gap.
- **Sex is both a confounder and a dimension that must be stratified.** Pooled, the OR for "warmer night → worse mood" is 1.24; within person it is 1.00, and also close to 1 in each sex (men 1.12, women 0.88). Women's mean temperature is 0.38 °C higher and their negative mood is more frequent, so an unstratified model learns "who she is" as "how she is today".
- **The effects in the ledger show no clear male-female difference for now.** For 1 hour less sleep: women +3.9 (0.6–7.6), men +2.9 (0.6–5.5), difference 1.0 (−3.2–5.3). For 30 more minutes of training: women +3.3 (−2.6–8.4), men +1.9 (0.1–4.9), difference 1.4 (−4.7–7.2). The intervals are wide, so we can claim neither that they are the same nor that they differ.
- **These data cannot attribute the gap to the menstrual cycle.** The dataset has no cycle information, and the within-person temperature variation of women and men is almost identical (median SD 0.43 °C vs 0.42 °C). That compares only the amplitude of variation and does not show that a device cannot detect the cycle. The within-person OR of temperature on tiredness is 0.93 (0.71–1.21) in women and 1.17 (0.85–1.61) in men.

### Literature and existing products

- **The cycle signal is real.** In an Oura ring study of 26 healthy women with regular cycles, sleep architecture barely changed across the cycle, but luteal-phase skin temperature and sleep heart rate were higher and HRV tended to fall [4]. In mcPHASES (42 people, 192 complete cycles), nightly wrist skin temperature and resting heart rate both differ significantly across phases (F(3,123) = 11.63 and 10.26, p < .001), lowest in the follicular phase and highest in the luteal phase [5]. This is exactly the situation where sleep metrics look normal while recovery metrics get worse.
- **Symptoms may be more useful than phase.** Two small studies in athletes found that symptom burden relates to sleep and recovery more clearly than cycle phase or hormone levels (24 and 8 participants respectively) [6,7]. This is only a lead and cannot be generalized to ordinary users.
- **Apple Watch can already estimate ovulation retrospectively.** Series 8 and later and all Ultra models use wrist temperature to detect the post-ovulatory biphasic rise, and the feature becomes available only after about 2 cycles of wearing the watch to sleep [8]. In a prospective cohort (262 people, 899 cycles), among completed cycles with a wrist-temperature signal of at least 0.2 °C, 80.8% produced an estimate, with a mean absolute error of 1.22 days and 89.0% within ±2 days [9].
- **The limits of this feature shape the product design.** It is **retrospective**: ovulation is known only after it has happened; about a fifth of cycles get no estimate; ovulation may occur without a clear biphasic shift, and temperature is also affected by factors such as the sleep environment. Apple states that it must not be used for contraception and that an estimate does not guarantee ovulation occurred [8].
- **The study populations are narrow.** The large Whoop study (2,596 people, 42,759 cycles) found that shorter sleep goes with more irregular cycles, but excluded women using hormonal contraception, pregnant women and perimenopausal women [10]. The mcPHASES participants are young Canadians with a mean age of 20.9, and anyone who had used hormonal therapy or contraception in the three months before the study was excluded. Real users are far more varied than these studies.

### Product opportunities

- **Make sex stratification the default workflow.** Report accuracy, false-alarm rate and calibration by sex for every score and alert, and do not ship if a subgroup metric falls short. If the female sample is too small, that alone is a reason to block release.
- **Two baseline layers, fitted to the "retrospective" limit.**

  | Layer | Information available | Product behaviour |
  |---|---|---|
  | Real-time (today) | Cycle day, user logs, recent temperature and heart rate | Only say "consistent with your usual changes at this point"; do not judge the current phase |
  | Retrospective (once an ovulation estimate exists) | Retrospective ovulation day | Re-label phases, update the baseline and revise the interpretation: "3 days of lower recovery last week are explained by your cycle" |

- **Decide by user state; do not assume all women are the same.**

  | User state | Product behaviour |
  |---|---|
  | Biphasic signal and an ovulation estimate | Turn on the cycle-aware baseline |
  | No estimate, or weak signal | Fall back to the personal rolling baseline and say clearly "not enough data for this cycle" |
  | Hormonal contraception, pregnancy, perimenopause or amenorrhea | Do not apply ovulation logic; let the user choose a state and use a separate baseline |
  | Does not want to log the cycle | All core features keep working; no data is required |

- **Add the cycle to the explanation layer, but do not blame everything on it.** "Last night's temperature and heart rate are above your usual baseline, but in line with your previous luteal phases" avoids a false "poor recovery". If values exceed the cycle-aware baseline, or last unusually long, they are still handled like the [body-load alerts](#a-the-reverse-gap-the-body-is-under-load-but-the-user-feels-fine-exploratory). Negative mood should not be explained away as hormonal by default: these data have no such evidence, and users may well dislike the claim.
- **One-tap symptom logging.** Record mood, cramps, headache and sleep disruption at almost no cost. It would test "symptoms matter more than phase" and supplies a label generic wearable data lacks.
- **Make emotional burden its own signal.** The main female gap is in negative mood, so a tiredness check-in and a sleep score are not enough.
- **Privacy and compliance are part of the product.** Cycle data must be opt-in, processed locally where possible, and explicitly not used for contraception or diagnosis.

### How to validate

- **Offline.** Use mcPHASES [5] (it has hormone-based cycle phases, but the labels come from Mira's proprietary algorithm and are not an independent gold standard) to compare the generic baseline with the cycle-aware baseline and see how many false "poor recovery" alerts in the luteal phase it removes; also compare "cycle day only" with "re-staged by retrospective ovulation". mcPHASES is restricted-access PhysioNet data: the code can be public, the data cannot.
- **Online.** A/B test the explanation layer, with analysis by sex and cycle state specified in advance and sample size calculated for the female subgroup. The primary metric is "agreement between score and feeling"; guardrails are anxiety feedback, the share who turn off the cycle feature, and retention.
- **Personal.** Use an Apple Health export and symptom check-ins for an n-of-1 study, reusing this project's within-person model.

## Product insights

Each follows the order "user pain point → evidence from the data → product opportunity → how to validate".

### 1. A recovery score must record both income and spending (post hoc + exploratory)

- **Pain point.** When the score is high and the person is tired, the user can only doubt the device or doubt themselves.
- **Evidence.** Short sleep and extra training are each linked to higher next-day tiredness; on days when both are bad the tired share is 21.5%, versus 9.6% when neither is. The training-load half is weaker evidence and stays a hypothesis for now.
- **Product opportunity.**
  - **Explanation layer.** When the sleep score is high and the user still feels tired, say why, for example "yesterday's training was 40% above your usual", instead of leaving the user to doubt the device.
  - **Include training load in the recovery score**, not sleep alone.
  - **One-tap subjective check-in.** Collect cases where the score and the feeling disagree; this is itself the most valuable personalization training data.
- **How to validate.** Set the north-star metric to "agreement between score and feeling". A/B test cards that show the training-load explanation and measure check-in rate, trust in the score and 4-week retention. Test training load first as a pre-specified hypothesis on PMData [11].

### 2. Compare with "your usual", not only with absolute thresholds (post hoc)

- **Evidence.** The effect of 1 hour less sleep on one night is robust (+3.3 percentage points); the absolute "7 h of sleep" threshold separates poorly (12.2% vs 16.5%).
- **Product opportunity.** Phrase every prompt relative to the user's baseline; new users have no baseline in the first 1–2 weeks, so the cold-start period needs its own design.

### 3. A "regular schedule" reminder should not promise next-day results (pre-specified)

- **Evidence.** Deviation in sleep timing has no detectable link to next-day tiredness (OR 1.09, 0.92–1.31, consistent across the 9 robustness analyses).
- **Product opportunity.** If a "keep a regular schedule" reminder stays, phrase it as a long-term benefit, not "you'll feel more energetic tomorrow"; run an experiment before investing in development.

### 4. Build the personal baseline first, then the complex model (pre-specified + literature)

- **Evidence.** Differences between people are far larger than day-to-day fluctuation (person-intercept SD 0.72), and a third of the people with good-night records never reported tiredness. In earlier work [12], under random splits with personalized models, the "user mean" baseline beat the paper's multimodal model on LifeSnaps (AUC 80.4 vs 74.6) but lost on PMData (84.1 vs 89.0).
- **Product opportunity.** Ship a personal baseline and user segments first, then consider complex models; any complex model must beat the personal mean as a release gate.

### 5. Subjective labels are scarce, so check-ins must cost almost nothing (dataset description)

- **Evidence.** The EMA response rate is only 43%, and it fell by about 18% during the study. About 43% of person-days are missing, which is also why the causal analysis has to handle missingness.
- **Product opportunity.** Make the one-tap check-in nearly free, for example a lock-screen widget needing one tap; or ask only when the score and behaviour look unusual, to reduce interruptions.

## Extensions

The two questions below follow from the main thread but are not the ledger itself. Both are exploratory and only generate hypotheses.

### A. The reverse gap: the body is under load but the user feels fine (exploratory)

The main thread is "data looks normal but I'm tired"; here it is the other way round: physiological measures deviate from the person's baseline, yet the user feels nothing. A common explanation is that acute stress raises cortisol and adrenaline, which mask fatigue. But this dataset has no hormone measurements, so **this mechanism cannot be tested here and stays a hypothesis**.

- **Evidence** (`reports/posthoc_good_nights/masked_strain.csv`; 37 people, 1,086 days with heart rate and HRV):
  - A "strain day" is one on which resting HR or NREM HR is more than 1 SD above the person's mean, or RMSSD is more than 1 SD below. Such days are 29% of all days, and on 78% of them no tiredness was reported.
  - "Strong strain days", with at least 2 of the 3 signals deviating together, are 12% of days; the tired share is 32% (14% on other days), so **68% still do not feel tired**. These people report "happy" or "alert" more often (40% vs 28%), consistent with a state of arousal, but exercise, alcohol or caffeine could equally explain it.
  - **"Under load but not tired" does not predict being more tired over the next 3 days**: OR 1.03 (0.67–1.59). So the feature cannot be sold with "you will crash later"; its value has to be shown with outcomes other than tiredness.
  - **Cost of alert rules** ([interactive simulator](https://arcadianlyric.github.io/WearableTech_Product/)). Baselines use only the previous 14 days, which is what a real product would have. The default rule is 2 signals, 2 consecutive days, 1 SD: on average 1.0 alerts per person per month (0.8–1.2); the tired share on alert days is 26% (10%–40%) against a base rate of 16%, with overlapping intervals; only 6.9% of tired days are covered. The default rule was fixed in advance; the other 26 rules are sensitivity exploration only.
  - Physiological background: in chronic sleep restriction experiments, subjective sleepiness stops rising quickly while cognitive performance keeps declining [13]. "Feeling fine" is not the same as "recovered".
- **Product opportunity.**
  - **Keep body-signal alerts separate from subjective feeling**: "your body is under load even though you feel fine". A deviation in a single signal is too common (29% of days) and daily alerts cause alert fatigue. Require **several signals deviating together for 2–3 days or more**.
  - **Attribute first, then alert.** For load explained by training, alcohol, dinner timing or the luteal phase, a "take it easier today" prompt is enough; **unexplained load that persists for days** is the signal worth attention.
  - **A graded escalation path.** Persistently raised resting heart rate together with raised temperature and respiratory rate may precede infection symptoms [14,15], which can justify "you may be getting ill, rest up". Only signals such as arrhythmia or low blood oxygen warrant seeing a doctor, and that must follow medical-device regulation. Throughout, no diagnosis is made, and wording should avoid causing anxiety.
- **How to validate.** Use outcomes other than tiredness, such as sick leave, infection or injury (PMData has injury records); measure the precision and false-alarm rate of alerts; A/B test whether users adjust their plans and whether alerts raise anxiety or churn.

### B. Attributing early waking: stress and cortisol, or something else? (exploratory)

A common complaint: when stressed, I wake very early and cannot go back to sleep. A wearable can record "woke earlier than usual" but cannot measure cortisol or tell what caused it.

- **Physiological background.** Cortisol has a circadian rhythm: it is lowest soon after sleep onset, rises through the second half of the night, and peaks 30–45 minutes after waking (the cortisol awakening response, CAR). The second half of the night is exactly when cortisol rises, so overactivity of the stress-driven HPA axis (hypothalamic-pituitary-adrenal axis) naturally shows up as early waking and difficulty falling back asleep. Supporting evidence:
  - Patients with chronic insomnia have higher evening and night-time cortisol and ACTH [16].
  - Merely expecting to wake early raises ACTH before waking [17], so this axis prepares for waking in advance.
  - Early-morning waking is also a classic symptom of depression.
- **A watch does not measure cortisol.** Heart rate, HRV and electrodermal activity (EDA) reflect the sympathetic and adrenal-medullary system, which acts fast, in minutes; cortisol belongs to the HPA axis, which acts slowly, over tens of minutes to hours. The two often change together but cannot substitute for each other. Calling "low HRV" "high cortisol" is wrong.
- **Data signatures of different causes** (a first attribution without hormones):

| Possible cause | Signature in wearable data | Extra records needed |
|---|---|---|
| Stress and hyperarousal | Normal sleep onset, **earlier final awakening**, long wakefulness afterwards; higher heart rate and lower HRV in the 1–2 hours before waking | Previous day's stress score, work events |
| Advanced circadian phase | **The whole sleep period shifts earlier** (earlier onset too), duration roughly unchanged, for several days in a row | Evening light, routine |
| Rebound after alcohol | High heart rate and low HRV in the first half of the night, fragmented sleep in the second half | Alcohol log |
| Night-time urination | Brief awakenings **accompanied by steps** | Fluid intake timing |
| Environment | Waking time matches sunrise; more common in summer | Room temperature, light, noise |
| Luteal phase | Raised nightly skin temperature, more awakenings | Cycle day |

- **Data that could link wearable data to cortisol more directly.**
  - **Salivary cortisol.** Samples at waking, 30 minutes and 45 minutes after waking, plus one before bed. This is the standard way to measure the CAR and a home kit is enough. The drawback is that timing must be exact: sampling a few minutes late underestimates the response.
  - **Hair cortisol.** Each 1 cm of hair reflects roughly one month of accumulated levels; it suits comparison with stress and sleep trends over weeks to months, not with a single night.
  - **Urinary hormone tests** (for example dried-urine hormone tests). They cover a whole-day cortisol curve but are costly.
  - **Sweat cortisol sensors.** Research prototypes exist but no consumer product yet; a long-term direction to watch.
  - **Public data.** MMASH [18] (22 healthy young men) has salivary cortisol and melatonin, RR intervals, actigraphy and sleep data, and could test whether nocturnal heart rate and HRV predict morning cortisol. It contains only men, and the 24-hour recordings are short.
- **A feasible n-of-1 design.** Over 2–4 weeks, collect salivary cortisol with the method above on both stressful and ordinary days; record stress, alcohol, caffeine and cycle day; from the watch extract the time of the final awakening, wake duration in the last 2 hours, and heart rate and HRV before waking. Then use this project's within-person model to test the two links "previous-day stress → early waking" and "early waking → cortisol awakening response".
- **Preliminary test on LifeSnaps** (`src/posthoc_early_waking.py` → `reports/posthoc_early_waking/early_waking.csv`; 3,280 nights, 64 people):
  - "Early waking" is a final awakening at least 60 minutes earlier than the person's usual (median computed separately for weekdays and weekends). **Normal sleep onset with only an early awakening** is 9.3% of nights, with a median of 89 minutes earlier; **the whole sleep period shifting earlier** is 3.5%.
  - **A report of "tense/anxious" the previous day goes with a higher chance of waking early the next day**: OR 1.41 (0.92–2.17). The direction agrees with "stress → early waking", but the interval crosses 1, so no conclusion. The comparison outcomes show no such signal: for the previous day's tension against "whole sleep period earlier" the OR is 0.76, and the negative control using the next day's tension gives 0.91.
  - **Fitbit's own stress score does not predict early waking at all**: OR 0.98, and 0.99 for its "responsiveness" component, which reflects HRV and EDA. On this question a single subjective check-in carries more information than the device's stress score.
  - **A weak sign of arousal physiology.** On early-waking nights NREM heart rate is higher than the person's usual (OR 1.18 per SD, 1.02–1.36), with no difference in RMSSD (0.98). Heart rate in the hour before waking is 2.2 bpm higher than on **other nights at the same clock time while still asleep** (0.9–3.6), in the same direction for 61% of people. But heart rate rises before any awakening, so this difference cannot separate "stress arousal" from "the normal waking process". Comparing the hour before waking directly with the whole-night mean would also be confounded by clock time, because early waking is closer to the circadian minimum of heart rate.
  - **The data cannot see "unable to fall back asleep".** Fitbit's sleep record ends at the final awakening, and the median trailing wake duration is 0 minutes. How long someone lay in bed after waking early is not recorded.
- **Implication for products.** If early waking can be attributed to stress, "early waking with long wakefulness afterwards" can serve as a stress-overload signal alongside the body-signal alerts above, and drive targeted advice such as relaxation training from cognitive behavioural therapy or checking the clock less at night, rather than a generic "go to bed earlier". The test above also exposes two product gaps: the device cannot see "unable to fall back asleep", which a one-tap morning check-in ("Did you lie awake after waking?") could fill; and the device's stress score is useless here, while a subjective stress check-in carries more signal.

## Discussion

**What the main thread shows.** In this sample, "sleeping less than one's own usual" explains next-day tiredness better than "sleeping later or earlier than usual". If the product has to give one next-day tip, duration is the best-supported signal. Training load suggests a recovery score cannot rely on sleep alone, but that half of the ledger is still a hypothesis with some evidence. The value of schedule regularity may show up on longer time scales (circadian stability over weeks or more) or only for a subset of people, but this amount of data cannot answer either question.

**When do these results count as causal?** Passing the decision rule does not establish causation. The causal reading rests on an assumption that cannot be verified: given the adjustment set, there is no unmeasured confounding. Work stress, alcohol and illness were not measured, and today's tiredness may also affect later sleep and activity, so the negative controls rule out only part of the problem. All results are post hoc, and the direction was seen before the plan was written, so confirmation needs PMData.

**Limitations.**

- 53 people with a median of 29 days each; the minimum detectable effect is about OR 1.35, so smaller true effects will likely be missed.
- Mood is a single choice among 7: a person may feel both "tired" and "relaxed" but can pick only one, so measurement is coarse.
- Only 66% of days have a first report before 13:00, so "the next morning" is not precisely defined.
- `very_active_minutes` is not training load and cannot distinguish types of exercise.
- A shift represents a change on one night or one day and cannot be extrapolated to a long-term change in schedule or training plan.
- Only 20 women; the stratified intervals are wide, and the dataset has no cycle information.
- Fitbit sleep timing has not been validated against polysomnography; participants are self-selected European adults.

**To-do.**

- [ ] Test sleep duration as a **pre-specified primary hypothesis** on PMData (16 people, daily 1–5 fatigue and readiness scores) for independent replication; write the supplementary plan before running.
- [ ] Test "previous-day training → next-day tiredness" as a pre-specified hypothesis on PMData with a cumulative-logit mixed model, also improving the functional form of activity.
- [ ] Distributed-lag models: training over the previous 1–3 days and the acute:chronic workload ratio, to test whether spending accumulates.
- [ ] Use mcPHASES to test how many false alerts a cycle-aware baseline removes.
- [ ] n-of-1 extension: parse an Apple Health export, add a template for daily tiredness and cycle day, and reuse the same within-person model to test the effects of cycle phase and symptoms directly.
- [ ] Add physiological outcomes: deviation of HRV (RMSSD) and nightly resting heart rate from the personal baseline.
- [ ] Next steps for early waking: write "previous-day stress → early waking" as a pre-specified hypothesis on PMData or n-of-1 data; add a morning one-tap "did you lie awake after waking?" check-in; use MMASH to test the relation between nocturnal HRV and morning salivary cortisol.
- [ ] A light model comparison: personal base rate, a hand-crafted-feature model and a simple sequence model under leave-one-subject-out cross-validation, to test whether a complex model can beat the personal baseline (about 8–10 hours). Multimodal deep learning is a separate project and is not part of this one.
- [ ] Use GLOBEM (497 people) as a large sample to test schedule regularity on a weekly time scale.

## References

This repository does not include the raw data. LifeSnaps data: Zenodo 7229547, CC-BY-4.0.

1. Yfantidou, S. *et al.* LifeSnaps, a 4-month multi-modal dataset capturing unobtrusive snapshots of our lives in the wild. *Scientific Data* 9, 663 (2022). [doi:10.1038/s41597-022-01764-x](https://doi.org/10.1038/s41597-022-01764-x)
2. Xu, X. *et al.* GLOBEM Dataset: multi-year datasets for longitudinal human behavior modeling generalization. *NeurIPS Datasets and Benchmarks Track* (2022). [arXiv:2211.02733](https://arxiv.org/abs/2211.02733)
3. Karim, H. T., Matin, A. & Goel, M. Passive sensing with psyche: utilizing data from wearable technology to predict emotion states. *medRxiv* (2025) (preprint, not peer reviewed). [doi:10.1101/2025.02.13.25322254](https://doi.org/10.1101/2025.02.13.25322254)
4. Alzueta, E. *et al.* Tracking sleep, temperature, heart rate, and daily symptoms across the menstrual cycle with the Oura Ring in healthy women. *International Journal of Women's Health* 14, 491–503 (2022). [doi:10.2147/IJWH.S341917](https://doi.org/10.2147/IJWH.S341917)
5. Lin, G. *et al.* A longitudinal dataset of physiological, hormonal, metabolic, and self-reported menstrual health data. *Scientific Data* 13, 411 (2026). [doi:10.1038/s41597-026-06805-3](https://doi.org/10.1038/s41597-026-06805-3) (the mcPHASES dataset)
6. Pearson, M. A. *et al.* Menstrual cycle symptoms, but not oestrogen or progesterone concentrations, are associated with sleep in female athletes. *European Journal of Sport Science* 25, e70038 (2025). [doi:10.1002/ejsc.70038](https://doi.org/10.1002/ejsc.70038)
7. Kullik, L. *et al.* The impact of menstrual cycle phase and symptoms on sleep, recovery, and stress in elite female basketball athletes: a longitudinal study. *Frontiers in Physiology* 16, 1663657 (2025). [doi:10.3389/fphys.2025.1663657](https://doi.org/10.3389/fphys.2025.1663657)
8. Apple. [Receive retrospective ovulation estimates on Apple Watch](https://support.apple.com/120357); [Cycle Tracking Instructions for Use](https://www.apple.com/legal/ifu/cycle-tracking/ct-ifu-en_US.pdf).
9. Wang, Y. *et al.* Performance of algorithms using wrist temperature for retrospective ovulation day estimate and next menses start day prediction: a prospective cohort study. *Human Reproduction* 40, 469–478 (2025). [doi:10.1093/humrep/deaf005](https://doi.org/10.1093/humrep/deaf005)
10. Gonzalez, A. *et al.* The menstrual cycle through the lens of a wearable device: insights into physiology, sleep, and cycle variability. *npj Digital Medicine* 9, 633 (2026). [doi:10.1038/s41746-026-02799-9](https://doi.org/10.1038/s41746-026-02799-9)
11. Thambawita, V. *et al.* PMData: a sports logging dataset. *Proc. 11th ACM Multimedia Systems Conference*, 231–236 (2020). [doi:10.1145/3339825.3394926](https://doi.org/10.1145/3339825.3394926)
12. Yang, Z., Yu, H. & Sano, A. Contrastive pretraining for stress detection with multimodal wearable sensor data and surveys. *Proceedings of Machine Learning Research* 287, 166–178 (2025). [PMC12975034](https://pmc.ncbi.nlm.nih.gov/articles/PMC12975034/)
13. Van Dongen, H. P. A. *et al.* The cumulative cost of additional wakefulness: dose-response effects on neurobehavioral functions and sleep physiology from chronic sleep restriction and total sleep deprivation. *Sleep* 26, 117–126 (2003). [doi:10.1093/sleep/26.2.117](https://doi.org/10.1093/sleep/26.2.117)
14. Mishra, T. *et al.* Pre-symptomatic detection of COVID-19 from smartwatch data. *Nature Biomedical Engineering* 4, 1208–1220 (2020). [doi:10.1038/s41551-020-00640-6](https://doi.org/10.1038/s41551-020-00640-6)
15. Radin, J. M. *et al.* Harnessing wearable device data to improve state-level real-time surveillance of influenza-like illness in the USA: a population-based study. *The Lancet Digital Health* 2, e85–e93 (2020). [doi:10.1016/S2589-7500(19)30222-5](https://doi.org/10.1016/S2589-7500(19)30222-5)
16. Vgontzas, A. N. *et al.* Chronic insomnia is associated with nyctohemeral activation of the hypothalamic-pituitary-adrenal axis: clinical implications. *Journal of Clinical Endocrinology & Metabolism* 86, 3787–3794 (2001). [doi:10.1210/jcem.86.8.7778](https://doi.org/10.1210/jcem.86.8.7778)
17. Born, J. *et al.* Timing the end of nocturnal sleep. *Nature* 397, 29–30 (1999). [doi:10.1038/16166](https://doi.org/10.1038/16166)
18. Rossi, A. *et al.* A public dataset of 24-h multi-levels psycho-physiological responses in young healthy adults. *Data* 5, 91 (2020). [doi:10.3390/data5040091](https://doi.org/10.3390/data5040091) (the MMASH dataset)
