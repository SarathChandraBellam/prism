# Tasks: what changes when the unit is the task

Computed by `tasks.py` from 77 sessions and 171 user turns in `data/lake_otel.jsonl`. Tasks are rebuilt with the fixed rule in `base.rebuild_tasks`: 64 tasks. Columns marked (truth) use the ground truth and are there to score the estimate; a real deployment would need sampled checks for them.

## Rebuild quality (scored against truth)

| Measure | Value |
|---|---|
| Rebuilt tasks | 64 |
| True tasks | 64 |
| Rebuilt chains equal to a true chain | 100% (64/64) |
| 'B continues A' links: precision | 100% (13/13) |
| 'B continues A' links: recall | 100% (13/13) |

- 64 of 64 true chains are rebuilt exactly.
- The rule finds 13 of 13 true links and adds 0 false ones.
- Every re-ask here was re-worded and came 2 to 12 minutes later by design, so the rule has an easy case. Real switches may be slower or vaguer.

## Platform share, three ways

Session share: sessions on the platform. Task starts: the first session of a rebuilt task. Finished: the last session of the task is on the platform and its last turn shows no trouble; the share is of finished tasks.

| Platform | Sessions | Task starts | Tasks finished | Session share − finished share | Truly completed there (truth) |
|---|---|---|---|---|---|
| Atlas | 49% (38/77) | 52% (33/64) | 58% (26/45) | -8 pp | 34 |
| Beacon | 30% (23/77) | 34% (22/64) | 31% (14/45) | -1 pp | 13 |
| Chatly | 21% (16/77) | 14% (9/64) | 11% (5/45) | +10 pp | 4 |
| Not finished (ends in trouble) |  |  | 19 of 64 tasks |  | 13 |

- Chatly moves most between the views: 21% (16/77) of sessions against 11% (5/45) of finished tasks.
- 19 of 64 tasks end in trouble by the spans; the truth says 13 did not complete. The trouble flag counts some good endings as trouble (see the scoring table).
- The session share counts a fallback session as new use. The task view counts the work once, where it started and where it ended.

## Rework by session class

redone: a later session of the same rebuilt task follows it. ended in trouble: the last session of its task, and its last turn has no answer, a tool error or an inability phrase. clean: the rest. Cost is shadow cost in USD; time is session end minus start.

| Platform | Class | Sessions | User turns | Model requests | Tokens in+out | Shadow cost | People minutes |
|---|---|---|---|---|---|---|---|
| Atlas | redone | 3 small n | 6 | 18 | 79,392 | 0.0364 | 5 |
| Atlas | ended in trouble | 9 | 22 | 88 | 424,114 | 0.1520 | 25 |
| Atlas | clean | 26 | 78 | 216 | 1,080,755 | 0.4171 | 81 |
| Atlas | all | 38 | 106 | 322 | 1,584,261 | 0.6054 | 111 |
| Beacon | redone | 7 | 8 | 43 | 203,821 | 0.0789 | 8 |
| Beacon | ended in trouble | 2 small n | 3 | 16 | 84,160 | 0.0272 | 4 |
| Beacon | clean | 14 | 32 | 89 | 452,320 | 0.1711 | 32 |
| Beacon | all | 23 | 43 | 148 | 740,301 | 0.2771 | 44 |
| Chatly | redone | 3 small n | 3 | 3 | 950 | 0.0013 | 0 |
| Chatly | ended in trouble | 8 | 9 | 9 | 3,938 | 0.0035 | 3 |
| Chatly | clean | 5 | 10 | 10 | 9,638 | 0.0058 | 7 |
| Chatly | all | 16 | 22 | 22 | 14,526 | 0.0106 | 10 |
| Total | redone | 13 | 17 | 64 | 284,163 | 0.1165 | 13 |
| Total | ended in trouble | 19 | 34 | 113 | 512,212 | 0.1826 | 32 |
| Total | clean | 45 | 120 | 315 | 1,542,713 | 0.5939 | 119 |
| Total | all | 77 | 171 | 492 | 2,339,088 | 0.8931 | 165 |

- 13 of 77 sessions were re-done elsewhere and 19 ended their task in trouble.
- People minutes include the time a person reads and types between turns, so they are the span of a session, not effort. A one-turn session counts only the wait for its reply, so time is low for Chatly.
- Re-done sessions are short: 17 user turns in 13 sessions. People stop at the first failed turn, so a re-done session is short and costs less than a clean one.

## Share spent on work that was re-done

Re-done is a lower bound of waste. At risk (re-done + ended in trouble) is an upper bound, because the trouble flag over-counts.

| Platform | Sessions (n) | Cost re-done | Cost at risk | Time re-done | Time at risk | Note |
|---|---|---|---|---|---|---|
| Atlas | 38 | 6% | 31% | 5% | 28% |  |
| Beacon | 23 | 28% | 38% | 19% | 27% |  |
| Chatly | 16 | 13% | 45% | 2% | 33% |  |
| Total | 77 | 13% | 34% | 8% | 28% |  |

- Across all 77 sessions, 13% of shadow cost and 8% of people time went to work that was re-done.
- Up to 34% of cost and 28% of time is at risk.
- Chatly has the largest share of cost at risk.

## Rework estimate against truth

True fates of the 77 sessions: abandoned 13, completed 51, switched 13.

| Share of | Shadow cost | People time |
|---|---|---|
| estimate redone (spans) | 13% | 8% |
| true switched (truth) | 13% | 8% |
| estimate at risk (spans) | 34% | 28% |
| true waste (truth) | 18% | 13% |

| Spans class | Truth fate | Precision | Recall |
|---|---|---|---|
| redone | switched | 100% (13/13) | 100% (13/13) |
| ended in trouble | abandoned | 47% (9/19) | 69% (9/13) |
| redone or ended in trouble | switched or abandoned | 69% (22/32) | 85% (22/26) |

- The re-done share of cost is 13% from spans against 13% truly switched.
- The true waste (switched or abandoned) is 18% of cost and 13% of time; the spans bracket it at 13% to 34% of cost.
- 'Ended in trouble' finds 9 of 13 abandoned sessions, and 10 of its 19 flags are false.
- 'Re-done' finds 13 of 13 switched sessions with 0 false.

## Cost per task, with and without rework

Grouped by the platform where the task started. Cost from spans (shadow USD). A task is verified correct (truth) when its final session has at least one checked turn, every checked turn in it is correct, it is not cut short and its fate is completed. Tasks whose final session has no checked turn are left out of the last two columns. In practice this column needs sampled checks of answers.

| Started on | Sessions | Tasks | Cost per session | Cost per task, first session only | Cost per task, all sessions | Correct of checked (truth) | Unchecked | Cost per correct task | Correct-task cost / session cost |
|---|---|---|---|---|---|---|---|---|---|
| Atlas | 36 | 33 | 0.0148 | 0.0161 | 0.0162 | 26 of 32 | 1 | 0.0203 | 1.4x |
| Beacon | 29 | 22 | 0.0109 | 0.0123 | 0.0143 | 8 of 21 | 1 | 0.0383 | 3.5x |
| Chatly | 12 | 9 | 0.0037 | 0.0008 | 0.0049 | 4 of 9 | 0 | 0.0111 small n | 3.0x |
| Total | 77 | 64 | 0.0116 | 0.0127 | 0.0140 | 38 of 62 | 2 | 0.0231 | 2.0x |

- Over all 64 tasks, a task costs 0.0140 against 0.0116 per session.
- Per verified-correct task the cost is 0.0231, 2.0 times the cost per session (38 correct of 62 checked; 2 tasks have no checked turn).
- The per-platform cells rest on few correct tasks; read the ratio as a direction, not a measure.

## Licence against tokens

Licence in the window = monthly price × seats × 10/21 (working days in the data / working days in a month). Per task and per correct task use the platform where the task started. Break-even: the tasks per seat per month at which shadow token cost per task (all sessions) times tasks equals the mean seat price.

| Platform | Seats | Price per month | Licence in window | Shadow token cost in window | Licence / tokens | Licence per task started | Licence per correct task | Break-even tasks per seat per month |
|---|---|---|---|---|---|---|---|---|
| Atlas | 9 | 270 | 128.57 | 0.6054 | 212x | 3.90 | 4.95 | 1,854 |
| Beacon | 7 | 140 | 66.67 | 0.2771 | 241x | 3.03 | 8.33 | 1,397 |
| Chatly | 8 | 160 | 76.19 | 0.0106 | 7,221x | 8.47 | 19.05 small n | 4,064 |
| Total | 24 | 570 | 271.43 | 0.8931 | 304x | 4.24 | 7.14 | 1,702 |

- In the window the seats cost 271.43 and the tokens 0.8931 at list price: the licence is 304 times the token cost. A seat decision should look at the licence first.
- A seat would cost the same as tokens at about 1,702 tasks per seat per month. The simulated staff did 2.7 tasks per person per week (64 tasks, 12 people, 2 weeks).
- Shadow cost is the list price of paid twins of the free models that answered, not a bill. Heavy real users would close the gap.
