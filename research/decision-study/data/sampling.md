# What the outcome signal costs

Data: the decision-study lake (spans only) for the signals; ground truth only to score them (parts 1 and 4) and to set the true rates of a simulation (part 3). Rates show k/n and a 95% Wilson interval. 'small n' marks fewer than 5 observations.

## 1a. Silent failures per turn (trace signal `trouble` against the checks)

| Platform | Verifiable turns | Failed | Silent failures (share of failed) | False alarms | Precision of trouble | Recall of trouble | Kappa |
|---|---|---|---|---|---|---|---|
| Atlas | 82 | 8 | 50% (4/8, 22–78%) | 13 | 24% (4/17, 10–47%) | 50% (4/8, 22–78%) | 0.216 |
| Beacon | 34 | 15 | 67% (10/15, 42–85%) | 2 | 71% (5/7, 36–92%) | 33% (5/15, 15–58%) | 0.242 |
| Chatly | 18 | 14 | 36% (5/14, 16–61%) | 1 | 90% (9/10, 60–98%) | 64% (9/14, 39–84%) | 0.289 |
| All | 134 | 37 | 51% (19/37, 36–67%) | 16 | 53% (18/34, 37–68%) | 49% (18/37, 33–64%) | 0.33 |

- 19 of 37 failed turns (51% (19/37, 36–67%)) show no trouble in the trace. The trace misses about half of the failures.
- Silent failures are highest on Beacon: 67% (10/15, 42–85%). On that platform a failed turn usually looks normal in the trace. The cells are small.
- 16 turns with trouble passed their checks. Precision of trouble is 53% (18/34, 37–68%); recall is 49% (18/37, 33–64%).
- Agreement beyond chance is low: kappa 0.33 over 134 turns. Per-platform cells are small.

## 1b. Each part of the trouble signal

| Signal | Platform | Flagged turns | Precision | Recall |
|---|---|---|---|---|
| trouble | Atlas | 17 | 24% (4/17, 10–47%) | 50% (4/8, 22–78%) |
| trouble | Beacon | 7 | 71% (5/7, 36–92%) | 33% (5/15, 15–58%) |
| trouble | Chatly | 10 | 90% (9/10, 60–98%) | 64% (9/14, 39–84%) |
| trouble | All | 34 | 53% (18/34, 37–68%) | 49% (18/37, 33–64%) |
| no_answer | Atlas | 2 | 100% (2/2, 34–100%) small n | 25% (2/8, 7–59%) |
| no_answer | Beacon | 2 | 100% (2/2, 34–100%) small n | 13% (2/15, 4–38%) |
| no_answer | Chatly | 0 | – (0/0) | 0% (0/14, 0–22%) |
| no_answer | All | 4 | 100% (4/4, 51–100%) small n | 11% (4/37, 4–25%) |
| tool_error | Atlas | 13 | 8% (1/13, 1–33%) | 12% (1/8, 2–47%) |
| tool_error | Beacon | 5 | 60% (3/5, 23–88%) | 20% (3/15, 7–45%) |
| tool_error | Chatly | 0 | – (0/0) | 0% (0/14, 0–22%) |
| tool_error | All | 18 | 22% (4/18, 9–45%) | 11% (4/37, 4–25%) |
| inability | Atlas | 3 | 67% (2/3, 21–94%) small n | 25% (2/8, 7–59%) |
| inability | Beacon | 0 | – (0/0) | 0% (0/15, 0–20%) |
| inability | Chatly | 10 | 90% (9/10, 60–98%) | 64% (9/14, 39–84%) |
| inability | All | 13 | 85% (11/13, 58–96%) | 30% (11/37, 18–46%) |

- The strongest part is `inability`: recall 30% (11/37, 18–46%) overall.
- `tool_error` flags 18 turns, with precision 22% (4/18, 9–45%). Agents often recover from a failed tool call.
- Chatly made no tool calls in the window, so `tool_error` cannot fire there. That is a property of the platform, not of its quality.

## 1c. Silent failures per session (any failed check against any trouble turn)

| Platform | Sessions with checks | With a failed check | Silent (share of failed) | False alarms | Precision | Recall | Kappa |
|---|---|---|---|---|---|---|---|
| Atlas | 37 | 8 | 25% (2/8, 7–59%) | 9 | 40% (6/15, 20–64%) | 75% (6/8, 41–93%) | 0.334 |
| Beacon | 22 | 15 | 53% (8/15, 30–75%) | 1 | 88% (7/8, 53–98%) | 47% (7/15, 25–70%) | 0.256 |
| Chatly | 16 | 14 | 36% (5/14, 16–61%) | 1 | 90% (9/10, 60–98%) | 64% (9/14, 39–84%) | 0.077 |
| All | 75 | 37 | 40% (15/37, 26–56%) | 11 | 67% (22/33, 50–80%) | 60% (22/37, 44–74%) | 0.306 |

- At session level 15 of 37 sessions with a failed check (40% (15/37, 26–56%)) show no trouble at all.
- Precision is 67% (22/33, 50–80%): a session with trouble usually does hold a failed check, but many failing sessions look clean.
- Sessions with no verifiable turn are left out; they cannot be scored.

## 1d. Where a reviewer should look first: failure rate given the signal

| Platform | P(failed) base rate | P(failed | trouble) | P(failed | no trouble) | Lift |
|---|---|---|---|---|
| Atlas | 10% (8/82, 5–18%) | 24% (4/17, 10–47%) | 6% (4/65, 2–15%) | 2.41 |
| Beacon | 44% (15/34, 29–60%) | 71% (5/7, 36–92%) | 37% (10/27, 22–56%) | 1.62 |
| Chatly | 78% (14/18, 55–91%) | 90% (9/10, 60–98%) | 62% (5/8, 31–86%) | 1.16 |
| All | 28% (37/134, 21–36%) | 53% (18/34, 37–68%) | 19% (19/100, 12–28%) | 1.92 |

- A turn with trouble fails 53% (18/34, 37–68%) of the time, against a base rate of 28% (37/134, 21–36%) (lift 1.92).
- So review flagged turns first: each check there finds more failures.
- Do not report the flagged-turn failure rate as the platform's rate. Unflagged turns still fail 19% (19/100, 12–28%) of the time; a rate from flagged turns only is biased upwards and ranks platforms by how loudly they fail.

## 2a. Pass rate in the full recordings matrix (every script on every platform)

| Task type | Scripts | Atlas | Beacon | Chatly |
|---|---|---|---|---|
| all | 32 | 88% (66/75, 79–94%) | 49% (37/75, 38–60%) | 15% (11/75, 8–24%) |
| advise | 3 | 100% (4/4, 51–100%) small n | 50% (2/4, 15–85%) small n | 25% (1/4, 5–70%) small n |
| analysis | 7 | 87% (13/15, 62–96%) | 73% (11/15, 48–89%) | 13% (2/15, 4–38%) |
| decide | 4 | 83% (10/12, 55–95%) | 17% (2/12, 5–45%) | 8% (1/12, 2–35%) |
| draft | 4 | 100% (7/7, 65–100%) | 71% (5/7, 36–92%) | 57% (4/7, 25–84%) |
| lookup | 7 | 100% (15/15, 80–100%) | 87% (13/15, 62–96%) | 7% (1/15, 1–30%) |
| report | 5 | 69% (11/16, 44–86%) | 19% (3/16, 7–43%) | 0% (0/16, 0–19%) |
| triage | 2 | 100% (6/6, 61–100%) | 17% (1/6, 3–56%) | 33% (2/6, 10–70%) |

- Overall the order is Atlas 88% (66/75), Beacon 49% (37/75), Chatly 15% (11/75). 0 of 3 pairs of overall intervals overlap.
- Within a task type the cells hold 4 to 16 verifiable turns, so most intervals are wide.
- Each cell comes from one recording per script; repeated runs of the same script could differ.

## 2b. Fisher's exact test for every pair of platforms

| Group | Pair | Correct A | Correct B | Difference | p (two-sided) | Holm at 0.05 |
|---|---|---|---|---|---|---|
| all | atlas-beacon | 66/75 | 37/75 | +39 pts | 4.432e-07 | – |
| all | atlas-chatly | 66/75 | 11/75 | +73 pts | 1.43e-20 | – |
| all | beacon-chatly | 37/75 | 11/75 | +35 pts | 8.441e-06 | – |
| advise | atlas-beacon | 4/4 | 2/4 | +50 pts | 0.4286 | no |
| advise | atlas-chatly | 4/4 | 1/4 | +75 pts | 0.1429 | no |
| advise | beacon-chatly | 2/4 | 1/4 | +25 pts | 1.0 | no |
| analysis | atlas-beacon | 13/15 | 11/15 | +13 pts | 0.6513 | no |
| analysis | atlas-chatly | 13/15 | 2/15 | +73 pts | 0.0001451 | kept |
| analysis | beacon-chatly | 11/15 | 2/15 | +60 pts | 0.002509 | kept |
| decide | atlas-beacon | 10/12 | 2/12 | +67 pts | 0.003329 | kept |
| decide | atlas-chatly | 10/12 | 1/12 | +75 pts | 0.0006442 | kept |
| decide | beacon-chatly | 2/12 | 1/12 | +8 pts | 1.0 | no |
| draft | atlas-beacon | 7/7 | 5/7 | +29 pts | 0.4615 | no |
| draft | atlas-chatly | 7/7 | 4/7 | +43 pts | 0.1923 | no |
| draft | beacon-chatly | 5/7 | 4/7 | +14 pts | 1.0 | no |
| lookup | atlas-beacon | 15/15 | 13/15 | +13 pts | 0.4828 | no |
| lookup | atlas-chatly | 15/15 | 1/15 | +93 pts | 2.063e-07 | kept |
| lookup | beacon-chatly | 13/15 | 1/15 | +80 pts | 2.187e-05 | kept |
| report | atlas-beacon | 11/16 | 3/16 | +50 pts | 0.01134 | no |
| report | atlas-chatly | 11/16 | 0/16 | +69 pts | 6.771e-05 | kept |
| report | beacon-chatly | 3/16 | 0/16 | +19 pts | 0.2258 | no |
| triage | atlas-beacon | 6/6 | 1/6 | +83 pts | 0.01515 | no |
| triage | atlas-chatly | 6/6 | 2/6 | +67 pts | 0.06061 | no |
| triage | beacon-chatly | 1/6 | 2/6 | -17 pts | 1.0 | no |

- Of 21 comparisons within a task type, 9 are significant at 0.05 and 7 remain after Holm.
- Overall, 3 of 3 platform pairs differ at 0.05.
- A non-significant pair is not evidence that two platforms are equal; the cells are too small to tell.

## 2c. Overall difference with the script as the unit (cluster bootstrap)

| Pair | Difference | 95% CI, turns resampled | 95% CI, scripts resampled | Width ratio |
|---|---|---|---|---|
| atlas-beacon | +39 pts | +25 to +52 pts | +24 to +53 pts | 1.089 |
| atlas-chatly | +73 pts | +61 to +84 pts | +60 to +85 pts | 1.118 |
| beacon-chatly | +35 pts | +20 to +48 pts | +20 to +51 pts | 1.112 |

- Resampling whole scripts changes the interval width by a factor of 1.089 to 1.118 (5000 resamples each).
- The script bootstrap is paired: the same scripts are drawn for both platforms, which removes script difficulty from the difference. Clustering widens the interval; pairing narrows it. The ratio shows the net effect.
- 3 of 3 pairs keep an interval that excludes zero.

## 3a. Checks per platform needed to pick the best platform (simulation)

Monte Carlo, 5000 draws per n. The overall pass rates in 2a are taken as the true rates.

| Checked turns per platform | P(best is right) | P(whole order right) | Mean regret (pts) |
|---|---|---|---|
| 3 | 73.9% | 47.3% | 6.6 |
| 5 | 85.1% | 66.8% | 3.8 |
| 10 | 95.9% | 90.0% | 1.1 |
| 20 | 99.6% | 98.7% | 0.1 |
| 30 | 99.9% | 99.7% | 0.0 |
| 50 | 100.0% | 100.0% | 0.0 |
| 100 | 100.0% | 100.0% | 0.0 |

- With true gaps this large, 10 checked turns per platform pick the best platform at least 90% of the time.
- The full order needs more: 10 per platform for 90%.
- Real gaps may be smaller than in this simulated company; smaller gaps need many more checks.

## 3b. Checks per platform and task type (simulation)

| Task type | n=3 | n=5 | n=10 | n=20 | n=30 | n=50 | n=100 | First n at 90% |
|---|---|---|---|---|---|---|---|---|
| advise | 86% | 97% | 100% | 100% | 100% | 100% | 100% | 5 |
| analysis | 46% | 56% | 69% | 80% | 88% | 94% | 99% | 50 |
| decide | 92% | 98% | 100% | 100% | 100% | 100% | 100% | 3 |
| draft | 53% | 76% | 96% | 100% | 100% | 100% | 100% | 10 |
| lookup | 34% | 51% | 75% | 94% | 99% | 100% | 100% | 20 |
| report | 82% | 93% | 99% | 100% | 100% | 100% | 100% | 5 |
| triage | 96% | 100% | 100% | 100% | 100% | 100% | 100% | 3 |
| mean over types | 70% | 82% | 91% | 96% | 98% | 99% | 100% | 10 |

- Cells show P(the best platform for that type is right). Regret and full order are in sampling.json.
- The mean over types reaches 90% at n=10 per cell.
- The hardest type is analysis (n=50): its two best platforms are close (87% (13/15) against 73% (11/15)).
- Every type reaches 90% within the list.
- True cell rates come from 2 to 7 scripts each, so the simulated gaps are themselves uncertain.

## 3c. The budget against what two weeks produced

| n | Checks, platform level | Checks, per task type | Verifiable lake turns | Fraction (platform) | Fraction (task type) | Cells short of n |
|---|---|---|---|---|---|---|
| 3 | 9 | 63 | 134 | 7% | 47% | 7 of 21 |
| 5 | 15 | 105 | 134 | 11% | 78% | 12 of 21 |
| 10 | 30 | 210 | 134 | 22% | 157% | 16 of 21 |
| 20 | 60 | 420 | 134 | 45% | 313% | 20 of 21 |
| 30 | 90 | 630 | 134 | 67% | 470% | 21 of 21 |
| 50 | 150 | 1050 | 134 | 112% | 784% | 21 of 21 |
| 100 | 300 | 2100 | 134 | 224% | 1567% | 21 of 21 |

- The window produced 134 verifiable turns in 21 platform-by-type cells (2 to 21 per cell).
- At n=5 per cell, 12 cells did not even produce 5 verifiable turns. A fraction above 100% means the window cannot supply the sample.
- The platform-level choice is affordable; a per-task-type choice needs a longer window or a planned test set.
- Lake cells follow the people's habits: a platform few people use for a type fills its cell slowly however long the window.

Verifiable lake turns per cell:

| Task type | Atlas | Beacon | Chatly |
|---|---|---|---|
| advise | 3 | 2 | 2 |
| analysis | 13 | 11 | 2 |
| decide | 16 | 2 | 3 |
| draft | 4 | 5 | 4 |
| lookup | 21 | 7 | 3 |
| report | 19 | 5 | 2 |
| triage | 6 | 2 | 2 |

## 4. Trace proxies at session level against checks and fate

| Proxy | Flagged sessions | Precision vs failed check | Recall vs failed check | Precision vs not completed | Recall vs not completed | Precision vs switched | Recall vs switched |
|---|---|---|---|---|---|---|---|
| ends_in_trouble | 25/77 | 72% (18/25, 52–86%) | 49% (18/37, 33–64%) | 60% (15/25, 41–77%) | 58% (15/26, 39–74%) | 24% (6/25, 12–43%) | 46% (6/13, 23–71%) |
| any_trouble_turn | 33/77 | 67% (22/33, 50–80%) | 60% (22/37, 44–74%) | 48% (16/33, 32–65%) | 62% (16/26, 42–78%) | 21% (7/33, 11–38%) | 54% (7/13, 29–77%) |
| switched_away | 13/77 | 100% (13/13, 77–100%) | 35% (13/37, 22–51%) | 100% (13/13, 77–100%) | 50% (13/26, 32–68%) | 100% (13/13, 77–100%) | 100% (13/13, 77–100%) |

- `switched_away` matches the designed switch fate: precision 100% (13/13, 77–100%), recall 100% (13/13, 77–100%). The replay makes users switch only after a noticed failure, so this link is built in.
- Against a failed check, the best recall is 60% (22/37, 44–74%), by `any_trouble_turn`. No proxy finds most failing sessions without false alarms.
- 'Failed check' uses the 75 sessions with a verifiable turn; fate uses all 77.
- 'Not completed' is fate abandoned or switched; a completed session can still hold a failed check.

