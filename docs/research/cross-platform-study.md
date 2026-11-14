# Cross-platform study (round 4): three AI platforms, one set of traces

Status: round 4 · partial run (quota) · 2026-11-14 · Previous: [round 3](agent-trace-study.md) · Code and data: [research/cross-platform](../../research/cross-platform/)

Round 3 studied one agent. A company with more than one AI platform has three problems that one agent hides. The traces come in different formats. People move between platforms when one fails them. And nobody sees the whole picture: who pays for seats nobody uses, and which platform does which job best.

This round simulates a company with 12 staff and three platforms, exports their traces in three vendor formats, and tests what can be recovered from the traces alone. The ground truth is kept apart and used only to score.

**This is a partial run.** The free tier's daily limit stopped the recording of the third platform after 85 of 100 turns. The study uses the 26 of 32 scripts that are recorded on all three platforms, which gives 52 of the planned 64 task instances. The session labels for two platforms (64 requests) are not yet made, so the label-based methods are pending. Every number below is from this partial run and will change when the run is finished (see [Suggested next steps](#suggested-next-steps)).

## TL;DR

1. **Three formats fit one shape without loss of what the analyses need.** After conversion, sessions, turns, model requests, failed requests, tool calls, tool errors and tokens equal the source counts exactly on all three platforms (64 sessions, 144 turns). What the formats cannot express is listed in Q1. One blind spot (failed requests on the chat platform) could not be measured, because no request failed there.
2. **Switching is easy to detect here, and that is partly by construction.** A 30-minute window finds all 12 switches but with precision 0.60 (20 candidate pairs). Adding word overlap of the first prompts gives precision 0.92 and recall 1.00. Every re-ask was re-worded, so the overlap is low (median 0.31): a threshold above 0.3 loses 42% of them. Shared order or ticket ids alone find only 3 of 12.
3. **Outcome proxies do not rank platforms on their own.** The composite picked the same best platform as the checks in 1 of 4 task groups (8 cells, Spearman 0.07). Switch-away is the one proxy that agrees with the checks (Spearman 0.77), but the replay rule links the two. Tool-error rate runs the other way (-0.88), because the chat platform has no tools.
4. **Unused seats are findable, with false alarms.** Flagging seats under 10% of the holder's sessions found 3 of 4 designed idle seats and 4 false ones. Flagging by task starts found all 4 and the same 4 false ones. The flagged seats are 150 to 170 of 570 per month. The users behind the false alarms had 1 to 3 tasks in the window, so a seat can look idle by chance.
5. **Routing has a trivial answer in this data.** Atlas is best on all 7 task types: 87% of verifiable turns correct on the recordings, against 48% for Beacon and 16% for Chatly. Sending every task to its best platform lifts the simulated staff from 61% to 87% correct turns, at 40% more shadow cost per task (0.0205 against 0.0146 USD). The cheapest platform per correct turn is Chatly (0.0043 USD), but only where a task can be answered from the prompt alone.
6. **Seven insight cards come out of the results by rule,** each with evidence, an action and an owner. Two of them depend on the tuning of the detector and the abandonment flag, which over-counts (precision 0.47).
7. **The simulated users limit all of this.** They react by rule to scripted transcripts that repeat across users. The study shows what the traces can carry. It does not measure how real people switch.

## Setup

| Item | Detail |
|------|--------|
| Platforms | **Atlas**: the round 3 agent with three MCP servers and skills. Export: OpenTelemetry GenAI spans. **Beacon**: the same agent without skills. Export: run tree, users by email. **Chatly**: new, chat only, no tools or skills, one request per turn, history kept. Export: one conversation per line, users by employee id |
| Recordings | Atlas and Beacon from round 3. Chatly recorded now: 85 turns, 85 requests, 0 failed, 11 different models served by `openrouter/free` |
| Users | 12: 4 support, 4 operations, 4 management. 24 seats, 570 per month (Atlas 30, Beacon 20, Chatly 20). 3 users hold one seat, 4 designed idle seats |
| Tasks | The 32 round 3 scripts, each assigned to 2 of the 4 users of its role: 64 drawn, 52 run (26 scripts) |
| Replay | The user starts on a seat by habit and gets that platform's recording. At the first turn whose checks failed, the user notices with probability 0.8. The session then ends. With probability 0.7 and a free seat, the user re-does the task 2 to 12 minutes later on another platform, with the first message re-worded by hand (32 paraphrases). Otherwise the task is abandoned |
| Result of the replay | 52 tasks, 64 sessions (Atlas 29, Beacon 20, Chatly 15), 144 turns. 12 tasks switched (none twice), 12 abandoned, 28 ran to the end on the first platform. 24 of 33 sessions with a failed turn were noticed |
| Time | Working days 2 to 13 November 2026, role-typical hours. About half of a user's tasks follow another of theirs within 3 to 25 minutes |
| Ground truth | `truth.json` only: chains, switches, per-turn check results, designed task types, designed idle seats. Not in the exports or the lake |
| Model requests | 87 in total: 1 test, 85 recorded turns, 1 refused with the daily limit. Labels: 0 of the planned 64 |

## Q1. Can three formats become one shape?

| Platform | Source | Sessions | Turns | Model requests | Failed requests | Tool calls | Tool errors | Tokens in | Tokens out |
|---|---|---|---|---|---|---|---|---|---|
| Atlas | recording = export = lake | 29 | 85 | 258 | 11 | 187 | 17 | 1,202,908 | 74,331 |
| Beacon | recording = export = lake | 20 | 38 | 133 | 0 | 152 | 9 | 646,631 | 29,274 |
| Chatly | recording = export = lake | 15 | 21 | 21 | 0 | 0 | 0 | 6,447 | 7,725 |

The "recording" column counts what the replay played, the "export" column counts the file by its own format, and the "lake" column counts the converted spans. All three agree on every field and platform.

- **Yes for what the analyses use.** Identity resolves through the directory by handle, email or employee id for all 12 users. Turn order, the answer text, tokens, errors and tool names survive.
- **What each format cannot say.** Beacon has no turn index (the adapter uses the order of the runs in a thread), no tool server name (taken from the tool-name prefix), and no reasoning or cached tokens. Chatly has no record of failed requests, no per-request latency (only the user and assistant timestamps), and tokens only for the successful request. A turn without a reply is inferred from a user message with no assistant message after it. Atlas lost nothing, but its internal attributes (`prism.*`, `eval.*`) were removed.
- **The Chatly blind spot is untested.** The platform had no failed request in 85 turns, so the export loses nothing here. On a busy day it would hide the retries and show a lower request count than the provider bills. The same applies to Beacon, which had no failed request either.
- **Atlas shows its failures:** 11 of 258 requests failed (4%) and 2 turns ended with no answer. Beacon shows no failed request but 3 turns with no answer.

## Q2. Can platform switching be detected, and with which signals?

Candidate pairs: same user, different platform, second session starts within 30 minutes after the first ends. There are 20 candidates, 12 of them true pairs. Scores are against the replay.

| Method | Predicted | Precision | Recall | F1 |
|---|---|---|---|---|
| a. Time window only | 20 | 0.60 | 1.00 | 0.75 |
| b. + word overlap of first prompts (best threshold 0.10) | 13 | 0.92 | 1.00 | 0.96 |
| c. + shared order, ticket or SKU ids | 3 | 1.00 | 0.25 | 0.40 |
| c2. ids or word overlap | 13 | 0.92 | 1.00 | 0.96 |
| d. + same labelled domain and task type | pending | | | |
| e. Best combination (ids or overlap at 0.10) | 13 | 0.92 | 1.00 | 0.96 |

| Overlap threshold | 0.05 | 0.10 | 0.20 | 0.30 | 0.40 | 0.50 | 0.60 |
|---|---|---|---|---|---|---|---|
| Precision | 0.92 | 0.92 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 |
| Recall | 1.00 | 1.00 | 0.75 | 0.58 | 0.42 | 0.33 | 0.08 |

- **The window alone has perfect recall by construction.** The replay puts the re-ask 2 to 12 minutes after the failed session. The 8 false candidates come from the placement rule that starts a user's next task 3 to 25 minutes after the last one.
- **A re-ask is hard to match by words.** All 12 switch sessions carry a re-worded first prompt. The median overlap of true pairs is 0.31, against 0.00 for false pairs. If the user had pasted the original prompt again, the scores at the same threshold would be the same (precision 0.92, recall 1.00), so at this threshold the re-wording costs nothing. It costs recall only at higher thresholds.
- **Ids help little.** Only 3 of 12 true pairs share an order, ticket or SKU, because most tasks name none. They never produce a false alarm in this data.
- **The tuning is optimistic.** The best threshold is chosen on the same data it is scored on. The separation is wide because a user's neighbouring tasks are different scripts. Two similar tasks in a row (two weekly reports for different weeks) would be the hard case, and the replay did not produce one.
- **Label-based methods are pending.** Labels exist per recording and Atlas already has them. Beacon and Chatly need 64 requests.

## Q3. Do proxies without ground truth rank platforms like the checks do?

Proxies come from the lake only: turns with no answer, switch-away (a detected follow-up on another platform), abandonment (the session ends on a turn with no answer, a tool error or an inability phrase such as "I can't access", and has no detected follow-up), turns with a tool error, and failed requests. Truth is the share of verifiable turns that passed all checks, on the turns that were replayed.

| Platform | Sessions | Verifiable turns | Correct (checks) | No answer | Switch-away | Abandonment | Tool error | Failed request | Composite (lower is better) |
|---|---|---|---|---|---|---|---|---|---|
| Atlas | 29 | 64 | 91% | 2% | 10% | 28% | 15% | 4% | 0.120 |
| Beacon | 20 | 32 | 56% | 8% | 30% | 10% | 16% | 0% | 0.127 |
| Chatly | 15 | 17 | 24% | 0% | 27% | 47% | 0% | 0% | 0.147 |

The composite is the unweighted mean of the five rates. It orders the three platforms like the checks do, but the gaps are small (0.120, 0.127, 0.147).

By group, the labelled-domain cut is pending (no labels for two platforms). The cut by designed task type is a second cut that uses the designed type, which a real company would not have. Cells with fewer than 3 sessions or 3 verifiable turns are left out.

| Task type | Best by checks | Best by composite | Match |
|---|---|---|---|
| analysis | Atlas (92%, Beacon 73%) | Beacon | no |
| decide | Atlas (83%, Chatly 0%) | Chatly | no |
| lookup | Atlas (100%, Chatly 0%) | Atlas | yes |
| report | Atlas (84%, Beacon 0%) | Beacon | no |

- **Agreement is poor.** The best platform by composite equals the best by checks in 1 of 4 groups. Of 4 platform pairs compared, 1 was ordered the same way. Spearman between composite and checks over 8 cells: 0.07.
- **Each proxy tells a different story.** Spearman against the checks, over the same 8 cells: switch-away 0.77, no answer 0.12, abandonment -0.47, failed request -0.49, tool error -0.88. Tool errors and failed requests fall on platforms that call tools. Chatly makes neither and is still the worst.
- **Switch-away works, with a caveat.** The replay makes a user switch only after a failed check, so the proxy and the truth are linked by construction. Real users switch for other reasons too.
- **The abandonment flag over-counts.** Against the replay it has precision 0.47 and recall 0.67 (8 true, 9 false, 4 missed). Atlas sessions often end on a tool error that the agent recovered from.
- **Small cells.** The smallest have 3 sessions and 3 verifiable turns. A cell moves by 33 points with one turn.

## Q4. Can unused and duplicate seats be found?

24 seats, 570 per month. The designed idle seats are four seats where the person starts under 5% of tasks. Flag: under 10% of the holder's sessions in the window (2 to 13 November).

| Rule | Flagged | Saving per month | TP | FP | FN | Precision | Recall |
|---|---|---|---|---|---|---|---|
| Under 10% of sessions | 7 | 150 | 3 | 4 | 1 | 0.43 | 0.75 |
| Under 10% of task starts (sessions that are not detected follow-ups) | 8 | 170 | 4 | 4 | 0 | 0.50 | 1.00 |

Flagged by sessions: hana on Beacon and Chatly, ines on Beacon and Chatly, freya on Beacon and Chatly, ben on Atlas. The designed list saves 90 per month.

- **The rule finds the idle seats and some more.** The four false alarms are seats the person keeps with a real habit weight (30% to 40%) that the draw did not use: hana had 3 tasks, ines 1, freya 3. In two weeks, that is not enough to call a seat unused.
- **A seat used only after a failure is a different case.** dmitri's Chatly seat had 2 sessions (25%), both follow-ups after a failure on Atlas, and no task start. The session rule misses it. The task-start rule finds it. It is a seat used as a fallback.
- **Duplicates.** Four users hold two or three seats and use one platform (hana, ines, freya and ben). Keeping a second seat is a decision, not waste, if the first platform fails often. Q3 says it does for Beacon and Chatly.
- **Saving.** Cancelling the confirmed idle seats saves at most 90 per month (16% of spend). Acting on the full flag list would cancel seats that real users still need.

## Q5. What would routing each task type to its best platform gain?

Full 3 x 26 recordings matrix (this is truth). Pass rate is the share of verifiable turns that passed all checks. Cost is shadow cost: tokens at the paid list price of the model that served the call, per 1,000 turns.

| Task type | Scripts | Verifiable turns | Atlas | Beacon | Chatly | Atlas $/1k | Beacon $/1k | Chatly $/1k |
|---|---|---|---|---|---|---|---|---|
| advise | 3 | 4 | 100% | 50% | 25% | 9.15 | 9.92 | 0.77 |
| analysis | 7 | 15 | 87% | 73% | 13% | 7.01 | 5.75 | 0.46 |
| decide | 3 | 9 | 89% | 11% | 11% | 3.14 | 7.02 | 0.31 |
| draft | 3 | 7 | 100% | 71% | 57% | 3.73 | 4.41 | 0.48 |
| lookup | 4 | 9 | 100% | 78% | 11% | 7.29 | 5.15 | 0.36 |
| report | 5 | 16 | 69% | 19% | 0% | 5.83 | 8.19 | 0.43 |
| triage | 1 | 3 | 100% | 33% | 33% | 5.98 | 3.94 | 1.20 |

| What the 52 task instances got | Verifiable turns | Correct | Pass rate | Shadow cost | Per task |
|---|---|---|---|---|---|
| Actual (final session of each task, unplayed turns count as failed) | 126 | 77 | 61% | 0.760 | 0.0146 |
| No switching (full session on the start platform) | 126 | 80 | 64% | 0.899 | 0.0173 |
| Routed to the best platform per task type | 126 | 110 | 87% | 1.067 | 0.0205 |
| Routed, best platform chosen without the task's own script | 126 | 110 | 87% | 1.067 | 0.0205 |

| Role | Actual | No switching | Routed |
|---|---|---|---|
| Support | 62% | 69% | 95% |
| Operations | 56% | 61% | 74% |
| Management | 70% | 60% | 100% |

- **Atlas wins every task type,** so routing means "use Atlas". The leave-one-script-out choice is the same, for the same reason. A real routing decision needs types where the winner changes.
- **The gain is large and costs more.** 61% to 87% correct turns for 40% more shadow cost per task. Atlas pays for skills and tools in every request: 6.28 USD per 1,000 turns against 0.51 for Chatly.
- **Per correct verifiable turn the order flips.** Atlas 0.0097 USD, Beacon 0.0191, Chatly 0.0043. Beacon costs about the same per turn as Atlas and gets far fewer turns right.
- **The only real trade-off is drafting.** Chatly gets 57% of draft turns right at 0.48 USD per 1,000 turns, Atlas 100% at 3.73. On the 55 verifiable turns of Chatly with text checks only, it passed 10. The other 8 verifiable turns need a database change, which Chatly cannot make.
- **Switching did not pay in this replay.** Actual (61%) is below no switching (64%) because the sessions cut short at the failed turn lose the rest of the script. Management gained from switching (70% against 60%). Support and operations did not.

## Q6. Insight cards

`insights.py` turns the results into cards by fixed rules, ranked by the share of tasks, turns or spend they touch ([insights.md](../../research/cross-platform/data/insights.md)). People-level findings are per role. Only seat flags name a holder.

| # | Finding | Owner |
|---|---|---|
| 1 | Beacon has the same tools as Atlas but no skills, and gets 30 points or more fewer verifiable turns right on 4 task types (decide 11% against 89%, report 19% against 69%) | skill author |
| 2 | The proxy composite picked the same best platform as the checks in 1 of 4 task groups | platform owner |
| 3 | 7 of 24 seats had no or almost no use, worth 150 per month | finance |
| 4 | Routing every task type to its best platform lifts correct turns from 61% to 87% | team lead |
| 5 | 11 of 51 tasks were re-done on another platform as far as the detector can tell | platform owner |
| 6 | In the operations group, 45% of tasks ended on trouble with no follow-up (upper bound) | team lead |
| 7 | 78% of the tasks started on Chatly were re-done elsewhere or ended on trouble | platform owner |

- **Each card is a sentence a manager can act on,** with the numbers behind it and a named owner.
- **Cards 5 and 6 rest on detected quantities,** not on truth: the detector found 13 pairs where 12 were true, so it rebuilt 51 tasks instead of 52. The operations rate of card 6 over-counts, as Q3 shows, and the card says so.
- **Card 3 is unsafe to act on alone.** The flags come from two weeks and three or fewer tasks per user.
- **A card is skipped when its analysis is pending.** The labelled-domain cut and the label-based detection are listed under "Not yet available".

## What changes in our understanding

| Topic | After round 4 | Confidence |
|---|---|---|
| Trace formats | An OpenTelemetry-GenAI-shaped span is enough as a common shape for three formats. Counts reconcile. Failed-request visibility depends on the vendor and was not testable here | Medium |
| Identity | A directory of handle, email and employee id is enough to join platforms. A shared task id would be better | Medium |
| Switching | A time window plus word overlap finds re-worded re-asks when a user's neighbouring tasks are unrelated. Ids alone are not enough. Harder cases are untested | Low-medium |
| Outcome proxies | Do not replace sampled checks. Switch-away is the best single signal. Tool and request error rates cannot be compared across platforms with different tools | Low-medium |
| Seats | Under 10% of sessions in two weeks gives false alarms. Task starts separate fallback seats from idle ones | Low-medium |
| Routing | The value depends on whether the winner changes by task type. Here it did not | Low |
| Skills (from round 3) | Reproduced on the recordings in scope: 87% with skills, 48% without (round 3: 88% and 49%) | Medium |

## Limitations

- **Users react by rule.** Noticing (0.8) and switching (0.7) are draws. The replay creates the switches and the detector is tested on recovering them. How real people switch, and why, is not measured.
- **The same 32 scripts are replayed across users,** two users per script, so transcripts repeat. The later turns of a switch session equal the first session's. Whole-session word overlap would therefore be inflated, and the detector uses the first prompt.
- **A user notices only a failed check.** A turn with no answer and no check is never noticed. The no-answer proxy can therefore not show up as a switch.
- **Time is simulated,** and the placement of tasks sets the number of false candidates.
- **Partial run.** 26 of 32 scripts, 52 of 64 task instances, no Beacon or Chatly labels. Support has 14 task instances instead of 26.
- **Labels belong to recordings.** A lake session would take the label of the recording its text matches best (63 of 64 sessions matched the right script). This stands in for labelling every replayed session.
- **Each recording was made once.** `openrouter/free` serves a different model per request. Round 3 saw about 4 points of noise between runs.
- **Truth is checks.** They cover 63 of the turns in scope per platform and are imperfect. Chatly fails the checks on database state by construction.
- **Shadow costs are list prices of the paid twins** of free models, not what any vendor charges.
- **Very small cells.** 12 switches, 17 verifiable Chatly turns, cells of 3 to 8 sessions.

## Suggested next steps

1. **Finish the run after the quota reset (00:00 UTC, 15 November):** `python3 chatly.py` (15 turns), `python3 labels.py` (64 requests), `./run_all.sh`, `python3 tables.py`. Then replace the numbers here. This adds 12 task instances, the label-based method d and the labelled-domain cut.
2. **Add hard negatives to the replay:** the same user starting two similar tasks in a row on different platforms (two weekly reports). Re-test the thresholds.
3. **Reactive users:** let a model play the user, so that noticing depends on what the platform said, and switching can follow a no-answer turn that has no check.
4. **A longer window,** four weeks and more tasks per user, before any seat is called unused.
5. **Make the platforms differ by task type.** Routing needs a task type where the cheaper platform is good enough, such as drafting with a better chat model.
6. **Propose a shared task or conversation reference across platforms** as a field the adapters can read. It would turn Q2 from inference into a join.
