# When can a seat be called unused?

Window: 2 weeks of spans. A task start is the first session of a rebuilt task. R1: under 10% of the holder's sessions. R2: under 10% of the holder's task starts. R3: P(X ≤ k | n, 0.10) < 0.05 for k starts on the seat out of n by the holder. 'Designed idle' (start weight under 5%) comes from ground truth and is used only to score.

## 1a. Per-seat evidence from spans

| Holder | Platform | $/month | Sessions (share) | Task starts k/n | P(X ≤ k) | Last use | R1 | R2 | R3 | Verdict | Designed idle |
|---|---|---|---|---|---|---|---|---|---|---|---|
| priya | Atlas | 30 | 67% (4/6, 30–90%) | 75% (3/4, 30–95%) small n | 0.9999 | 2026-11-05 |  |  |  | in use |  |
| priya | Chatly | 20 | 33% (2/6, 10–70%) | 25% (1/4, 5–70%) small n | 0.9477 | 2026-11-05 |  |  |  | in use |  |
| tomas | Atlas | 30 | 100% (9/9, 70–100%) | 100% (9/9, 70–100%) | 1.0 | 2026-11-10 |  |  |  | in use |  |
| hana | Atlas | 30 | 83% (5/6, 44–97%) | 83% (5/6, 44–97%) | 1.0 | 2026-11-10 |  |  |  | in use |  |
| hana | Beacon | 20 | 17% (1/6, 3–56%) | 17% (1/6, 3–56%) | 0.8857 | 2026-11-03 |  |  |  | in use |  |
| hana | Chatly | 20 | 0% (0/6, 0–39%) | 0% (0/6, 0–39%) | 0.5314 | never | yes | yes |  | quiet, not enough evidence | yes |
| jonas | Beacon | 20 | 58% (7/12, 32–81%) | 86% (6/7, 49–97%) | 1.0 | 2026-11-13 |  |  |  | in use |  |
| jonas | Chatly | 20 | 42% (5/12, 19–68%) | 14% (1/7, 3–51%) | 0.8503 | 2026-11-12 |  |  |  | in use |  |
| kofi | Atlas | 30 | 58% (7/12, 32–81%) | 44% (4/9, 19–73%) | 0.9991 | 2026-11-11 |  |  |  | in use |  |
| kofi | Beacon | 20 | 42% (5/12, 19–68%) | 56% (5/9, 27–81%) | 0.9999 | 2026-11-11 |  |  |  | in use |  |
| lucia | Beacon | 20 | 100% (6/6, 61–100%) | 100% (6/6, 61–100%) | 1.0 | 2026-11-09 |  |  |  | in use |  |
| dmitri | Atlas | 30 | 75% (6/8, 41–93%) | 100% (6/6, 61–100%) | 1.0 | 2026-11-09 |  |  |  | in use |  |
| dmitri | Chatly | 20 | 25% (2/8, 7–59%) | 0% (0/6, 0–39%) | 0.5314 | 2026-11-04 |  | yes |  | quiet, not enough evidence, fallback only | yes |
| ines | Atlas | 30 | 100% (1/1, 21–100%) small n | 100% (1/1, 21–100%) small n | 1.0 | 2026-11-04 |  |  |  | in use |  |
| ines | Beacon | 20 | 0% (0/1, 0–79%) small n | 0% (0/1, 0–79%) small n | 0.9 | never | yes | yes |  | quiet, not enough evidence |  |
| ines | Chatly | 20 | 0% (0/1, 0–79%) small n | 0% (0/1, 0–79%) small n | 0.9 | never | yes | yes |  | quiet, not enough evidence | yes |
| rosa | Chatly | 20 | 25% (1/4, 5–70%) small n | 33% (1/3, 6–79%) small n | 0.972 | 2026-11-12 |  |  |  | in use |  |
| rosa | Atlas | 30 | 75% (3/4, 30–95%) small n | 67% (2/3, 21–94%) small n | 0.999 | 2026-11-12 |  |  |  | in use |  |
| omar | Chatly | 20 | 100% (6/6, 61–100%) | 100% (6/6, 61–100%) | 1.0 | 2026-11-13 |  |  |  | in use |  |
| freya | Atlas | 30 | 100% (3/3, 44–100%) small n | 100% (3/3, 44–100%) small n | 1.0 | 2026-11-09 |  |  |  | in use |  |
| freya | Beacon | 20 | 0% (0/3, 0–56%) small n | 0% (0/3, 0–56%) small n | 0.729 | never | yes | yes |  | quiet, not enough evidence |  |
| freya | Chatly | 20 | 0% (0/3, 0–56%) small n | 0% (0/3, 0–56%) small n | 0.729 | never | yes | yes |  | quiet, not enough evidence |  |
| ben | Beacon | 20 | 100% (4/4, 51–100%) small n | 100% (4/4, 51–100%) small n | 1.0 | 2026-11-06 |  |  |  | in use |  |
| ben | Atlas | 30 | 0% (0/4, 0–49%) small n | 0% (0/4, 0–49%) small n | 0.6561 | never | yes | yes |  | quiet, not enough evidence | yes |

- 7 seats are quiet (R2 flags them) but R3 finds not enough evidence. 0 seats are unused on the evidence rule.
- The largest holder sample is 9 task starts in 2 weeks; R3 needs 29 with zero on the seat.
- 1 seat is fallback only (sessions but no task start): dmitri/Chatly. Such a seat is used after a failure elsewhere; cancelling it removes the fallback.

## 1b. The three rules against the designed idle seats

| Rule | Flagged | Correct | Wrong | Missed | Precision | Recall | Saving of the flags $/month | Price of wrong flags $/month |
|---|---|---|---|---|---|---|---|---|
| R1 | 6 | 3 | 3 | 1 | 50% (3/6, 19–81%) | 75% (3/4, 30–95%) small n | 130 | 60 |
| R2 | 7 | 4 | 3 | 0 | 57% (4/7, 25–84%) | 100% (4/4, 51–100%) small n | 150 | 60 |
| R3 | 0 | 0 | 0 | 4 | – (0/0) | 0% (0/4, 0–49%) small n | 0 | 0 |

- R1 flags 6 seats with 3 wrong; R2 flags 7 with 3 wrong. 4 seats are designed idle, worth 90 $/month.
- R3 flags 0 seats. In 2 weeks no holder has enough task starts for the evidence rule to fire.
- The scores use 24 seats and one window; one seat moves precision by many points.

## 1c. How long until zero starts is evidence

Zero task starts on a seat passes R3 once the holder has made 29 task starts (0.9^n < 0.05).

| Holder | Seats | Task starts in 2 weeks | Starts per week | Weeks to reach n* | More weeks needed |
|---|---|---|---|---|---|
| kofi | 2 | 9 | 4.5 | 6.4 | 4.4 |
| tomas | 1 | 9 | 4.5 | 6.4 | 4.4 |
| jonas | 2 | 7 | 3.5 | 8.3 | 6.3 |
| dmitri | 2 | 6 | 3.0 | 9.7 | 7.7 |
| hana | 3 | 6 | 3.0 | 9.7 | 7.7 |
| lucia | 1 | 6 | 3.0 | 9.7 | 7.7 |
| omar | 1 | 6 | 3.0 | 9.7 | 7.7 |
| ben | 2 | 4 | 2.0 | 14.5 | 12.5 |
| priya | 2 | 4 | 2.0 | 14.5 | 12.5 |
| freya | 3 | 3 | 1.5 | 19.3 | 17.3 |
| rosa | 2 | 3 | 1.5 | 19.3 | 17.3 |
| ines | 3 | 1 | 0.5 | 58.0 | 56.0 |

- For holders with more than one seat, the extra wait runs from 4.4 to 56.0 weeks at their observed rate.
- The rate comes from one two-week window; for holders with one or two tasks it is very uncertain.
- Holders with one seat cannot have a seat flagged: their only seat holds every start.

## 2a. Window length, observed task rates (design study: simulated from the designed habits)

4000 runs per window. Precision and recall pool all runs. Saving counts correctly flagged seats only.

| Rule | Weeks | Mean flagged | Precision | Recall | Mean saving $/month | Mean price of wrong flags $/month | Runs with a wrong flag | Break-even cost ratio |
|---|---|---|---|---|---|---|---|---|
| R2 | 2 | 6.21 | 0.556 | 0.863 | 78.9 | 64.6 | 97% | 1.25 |
| R2 | 4 | 5.27 | 0.71 | 0.936 | 84.9 | 35.6 | 85% | 2.45 |
| R2 | 8 | 4.75 | 0.827 | 0.982 | 88.5 | 19.0 | 61% | 4.79 |
| R2 | 13 | 4.42 | 0.901 | 0.994 | 89.5 | 10.2 | 38% | 9.06 |
| R2 | 26 | 4.14 | 0.966 | 0.999 | 89.9 | 3.4 | 14% | 28.0 |
| R3 | 2 | 0.0 | – | 0.0 | 0.0 | 0.0 | 0% | – |
| R3 | 4 | 0.0 | 1.0 | 0.0 | 0.0 | 0.0 | 0% | no wrong flags |
| R3 | 8 | 0.25 | 1.0 | 0.063 | 5.1 | 0.0 | 0% | no wrong flags |
| R3 | 13 | 1.6 | 1.0 | 0.399 | 35.0 | 0.0 | 0% | no wrong flags |
| R3 | 26 | 2.72 | 1.0 | 0.68 | 64.4 | 0.0 | 0% | no wrong flags |

- R2 has a wrong flag in 97% of 2-week runs and 14% of 26-week runs.
- R3 has a wrong flag in at most 0.1% of runs at any window. The price is recall: 0.0 at 2 weeks, 0.68 at 26 weeks.
- R3 finds half the idle seats first at 26 weeks.

## 2b. Window length, task rates x 5 (design study: simulated from the designed habits)

4000 runs per window. Precision and recall pool all runs. Saving counts correctly flagged seats only.

| Rule | Weeks | Mean flagged | Precision | Recall | Mean saving $/month | Mean price of wrong flags $/month | Runs with a wrong flag | Break-even cost ratio |
|---|---|---|---|---|---|---|---|---|
| R2 | 2 | 4.59 | 0.863 | 0.99 | 89.2 | 14.7 | 51% | 6.27 |
| R2 | 4 | 4.21 | 0.947 | 0.998 | 89.9 | 5.2 | 20% | 18.05 |
| R2 | 8 | 4.05 | 0.988 | 1.0 | 90.0 | 1.2 | 5% | 80.0 |
| R2 | 13 | 4.01 | 0.998 | 1.0 | 90.0 | 0.2 | 1% | 421.05 |
| R2 | 26 | 4.0 | 1.0 | 1.0 | 90.0 | 0.0 | 0% | no wrong flags |
| R3 | 2 | 0.86 | 1.0 | 0.214 | 17.5 | 0.0 | 0% | no wrong flags |
| R3 | 4 | 2.55 | 1.0 | 0.637 | 60.6 | 0.0 | 0% | no wrong flags |
| R3 | 8 | 2.95 | 1.0 | 0.738 | 69.0 | 0.0 | 0% | no wrong flags |
| R3 | 13 | 3.74 | 1.0 | 0.936 | 84.9 | 0.0 | 0% | no wrong flags |
| R3 | 26 | 4.0 | 1.0 | 1.0 | 90.0 | 0.0 | 0% | no wrong flags |

- R2 has a wrong flag in 51% of 2-week runs and 0% of 26-week runs.
- R3 never flags a seat in use in any of the 4000 runs at any window. The price is recall: 0.214 at 2 weeks, 1.0 at 26 weeks.
- R3 finds half the idle seats first at 4 weeks.

- The break-even ratio is p/(1−p) for precision p. Acting on a flag pays when the cost of wrongly cancelling a seat (lost work, re-buying it) is below that ratio times the monthly saving. At precision 0.5 the cost must be below one month's saving; at 0.9, below nine.

## 2c. How often each designed idle seat is flagged (design study)

| Seat | Designed start weight | R2/R3 at 2 wk | R2/R3 at 4 wk | R2/R3 at 8 wk | R2/R3 at 13 wk | R2/R3 at 26 wk | R3 at 2 wk, busy | R3 at 26 wk, busy |
|---|---|---|---|---|---|---|---|---|
| ben/atlas | 0.0 | 98% / 0% | 100% / 0% | 100% / 0% | 100% / 31% | 100% / 100% | 3% | 100% |
| dmitri/chatly | 0.03 | 85% / 0% | 88% / 0% | 94% / 7% | 98% / 33% | 100% / 72% | 22% | 100% |
| hana/chatly | 0.0 | 100% / 0% | 100% / 0% | 100% / 18% | 100% / 96% | 100% / 100% | 61% | 100% |
| ines/chatly | 0.0 | 62% / 0% | 87% / 0% | 98% / 0% | 100% / 0% | 100% / 0% | 0% | 100% |

- dmitri/chatly is designed idle with a start weight of 0.03, so it is used sometimes. Both rules compare the share with 10%, so with enough starts they flag it and count the flag as correct: R3 flags it in 72% of 26-week runs. Each start on it delays R3, which needs more evidence for a share of 1 in n than for 0 in n. In the window it had 2 sessions and 0 task starts: the rules count starts, not fallback use.
- The seat in use that R2 flags most often is rosa/atlas (start weight 0.2): 51% of 2-week runs and 6% of 26-week runs.
- A zero-weight seat can only be flagged once its holder has enough starts; holders with few tasks keep their idle seats unflagged.

