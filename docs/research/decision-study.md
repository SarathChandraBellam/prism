# Decision study (round 5): six decisions, and how sure the traces can be

Status: round 5 · 2026-11-16 · Previous: [round 4](cross-platform-study.md) · Code and data: [research/decision-study](../../research/decision-study/)

Rounds 1 to 4 asked what can be read from chats and traces. This round starts from the other end. A company with several AI tools has a few decisions to make, each with an owner: which seats to pay for, which tool to use for which job, what to build next. The round lists six such decisions in an [insight catalogue](../insights.md) and asks two things of each. Can it be answered from traces in the [trace schema](../trace-schema.md)? And how wrong can the answer be?

It uses the complete round 4 data: a simulated company with 12 staff, three platforms and two weeks of work. No new model calls were needed. The ground truth is used only to score, and in one design study that says so.

## TL;DR

1. **The trace schema carries the data.** The first transformer converts the round 4 lake into spans that follow the schema, with no non-standard name left. Four source attributes have no standard name (cost, turn index, MCP server name, HTTP status). Each has a workaround. One Required attribute, `gen_ai.provider.name`, is missing on 174 of 492 model calls, because two of the three sources never recorded it.
2. **Three of six decisions can be answered from traces today.** Seats, the work map and the personal report are ready on all three platforms. "What to build next" is ready where a platform has tools. "Which tool for which job" and "where does sensitive work go" are blocked on every platform by an input that is in no trace. With content switched off, nothing is ready.
3. **The session is the wrong unit.** The chat platform had 21% of the sessions and 11% of the finished tasks. 13% of the token cost went to sessions that the person then re-did elsewhere. A verified-correct task cost 2.0 times the cost of a session.
4. **The cost is in the seats.** Licences cost 304 times the token cost of the work done on them. A seat decision matters far more than a token decision at this level of use.
5. **Half of the wrong answers leave no sign in the trace.** 19 of 37 turns that failed a check show no error, no empty reply and no "I can't". A failed tool call marked a wrong answer in only 4 of 18 turns.
6. **Thirty checks settle the platform. Routing by task type needs a planned test.** 10 checked turns per platform picked the best platform in 96% of simulated samples. A choice per task type needs about 210 checks, and two weeks of use left 16 of 21 cells short.
7. **Two weeks cannot settle a seat.** The rule "under 10% of the holder's task starts" flagged 7 seats, 3 of them wrongly. In a simulation it flags a seat that is in use in 97% of two-week windows. A rule that waits for evidence made almost no wrong flag, but needs 29 task starts by the holder first: 4 to 56 more weeks here.
8. **A switch says what was missing.** Every task that left the chat platform used the shop data server on the next one. 3 of 7 tasks that left the platform without skills used the weekly sales report skill on the next one.
9. **Task type does not compare across platforms.** The same script got the same task type on all three platforms in 11 of 32 cases. Domain agrees well between the two agent platforms (kappa 0.85) and less with the chat platform (0.44 and 0.55).
10. **Nine cards, and they no longer look equally sure.** Each card states its kind of evidence, its measured error and a readiness. Four say `act`, two say `check first`, three say `watch`.

## Setup

| Item | Detail |
|------|--------|
| Data | The complete round 4 lake: 12 people in 3 roles, 3 platforms, 2 working weeks, 64 tasks, 77 sessions, 171 turns, 1,062 spans |
| Platforms | **Atlas**: an agent with three MCP servers and skills. **Beacon**: the same agent without skills. **Chatly**: chat only, no tools |
| Transformer | `conform.py` converts the lake to the trace schema and counts every change. All analyses read only the converted spans, the directory and the seat list |
| Catalogue | Six decisions, each with an owner, a metric, the span attributes it needs, a kind of evidence and a bar for action ([insights.md](../insights.md), `catalogue.json`) |
| Tasks | Rebuilt from spans by the round 4 rule, fixed in advance: same person, another platform, within 30 minutes, first prompts share words (0.10) or an id |
| Ground truth | Round 4's `truth.json`: which sessions belong together, how each ended, per-turn checks, the full matrix of 32 scripts on 3 platforms, designed idle seats. Used to score |
| Model requests | None in this round. Round 4 was finished first: 15 Chatly turns and 64 session labels |

## Q1. Does the trace schema carry what the decisions need?

[ADR 0003](../adr/0003-otel-trace-as-base.md) says Prism reads only OpenTelemetry GenAI traces. The research data predates the schema and used names of its own. The transformer makes it conform. Full tables: [coverage.md](../../research/decision-study/data/coverage.md).

| What the transformer did | Items | Examples |
|---|---|---|
| Renamed | 3 | cached and reasoning tokens, the `tool_calls` finish reason |
| Restructured | 2 | input and output text into `gen_ai.input.messages` and `gen_ai.output.messages` |
| Moved | 1 | the platform into the resource, as `service.name` |
| Inferred | 3 | the skill name from the tool arguments, the MCP method from the tool-name prefix, the finish reason of a message |
| Dropped | 4 | `gen_ai.usage.cost`, `session.turn_index`, `mcp.server.name`, `http.status_code` |
| Required but missing | 1 | `gen_ai.provider.name` on 4 of 322 Atlas, 148 of 148 Beacon and 22 of 22 Chatly model calls |

- **Nothing a decision needs was lost.** Cost is tokens times a price table. Turn order is the start time. The MCP server is the prefix of the tool name.
- **Two of those workarounds are habits of one harness.** Another vendor may name tools differently, and then the server and the skill are gone. The conventions have no attribute for a local MCP server.
- **A Required attribute can be missing at the source.** No transformer can invent the provider. Prism must accept spans that do not fully conform and say what it could not compute.

Each decision was then tested against each platform's spans. A cell is `ready` when every attribute the decision needs is on at least 99% of the spans where it applies, and every input from outside the traces exists.

| Decision | Evidence | Atlas | Beacon | Chatly | With content off |
|---|---|---|---|---|---|
| D1 Which seats do we pay for? | linked | ready | ready | ready | sessions only |
| D2 What work goes to AI? | labelled | ready | ready | ready | blocked |
| D3 Which tool for which job? | checked | blocked | blocked | blocked | blocked |
| D4 What do we build next? | linked | ready | partial | blocked | blocked |
| D5 Where does sensitive work go? | labelled | blocked | blocked | blocked | blocked |
| D6 How do I work with AI? | labelled | ready | ready | ready | blocked |

- **10 of 18 cells are ready, 1 is partial and 7 are blocked.**
- **D3 is blocked by a missing input, not by the schema.** The conventions define a `gen_ai.evaluation.result` event for a checked answer. It is on 0 of 1,062 spans. Nobody checks answers and writes the result down.
- **D5 is blocked because no sensitivity label or policy exists.**
- **D4 is blocked on Chatly because Chatly has no tools.** A platform's missing capability shows up as missing spans.
- **Content is the price of almost everything.** The conventions record no content by default. Without the user's message and the visible reply, only seat use by session count survives.

## Q2. What changes when the unit is the task?

A task is one piece of work by one person, across sessions and platforms. The fixed rule rebuilt 64 of 64 tasks and all 13 links, with no false link. That is the easy case: every re-ask came within 12 minutes and was the only similar prompt nearby. Full tables: [tasks.md](../../research/decision-study/data/tasks.md).

| Platform | Sessions | Task starts | Tasks finished there | Share of sessions | Share of finished tasks |
|---|---|---|---|---|---|
| Atlas | 38 | 33 | 26 | 49% | 58% |
| Beacon | 23 | 22 | 14 | 30% | 31% |
| Chatly | 16 | 9 | 5 | 21% | 11% |

"Finished" means the task's last session is on the platform and its last turn shows no trouble. 19 tasks did not finish by that measure.

- **Session counts flatter the weakest platform.** Chatly's sessions include failures and use as a fallback. By finished tasks its share halves.
- **Re-done work is visible.** 13 of 77 sessions were re-done on another platform. They hold 13% of the token cost and 8% of people's time. Against the truth this estimate is exact, because the links are.
- **Abandoned work is only bounded.** Adding the sessions that ended on trouble gives 34% of cost. The truth is 18%. The flag "ended on trouble" was right for 9 of its 19 sessions.

| Started on | Tasks | Cost per session | Cost per task, all sessions | Correct of checked tasks | Cost per correct task | Ratio to a session |
|---|---|---|---|---|---|---|
| Atlas | 33 | 0.0148 | 0.0162 | 26 of 32 | 0.0203 | 1.4 |
| Beacon | 22 | 0.0109 | 0.0143 | 8 of 21 | 0.0383 | 3.5 |
| Chatly | 9 | 0.0037 | 0.0049 | 4 of 9 | 0.0111 | 3.0 |
| All | 64 | 0.0116 | 0.0140 | 38 of 62 | 0.0231 | 2.0 |

Costs are shadow costs in USD: tokens at the list price of the paid twin of the free model that answered.

- **The cheapest platform per session is not the cheapest per result.** Beacon costs less than Atlas per session and almost twice as much per correct task.
- **Licences dwarf tokens.** The licences for the window cost 271.43 and the tokens 0.89, a ratio of 304. Per task started, the licence is 4.24 and the tokens 0.014. Tokens would equal the seat price at about 1,700 tasks per seat per month. The simulated staff did 2.7 tasks per person per week.
- **That ratio is the first thing a finance owner should see.** At light use the decision is the number of seats. Token cost matters only for heavy agent use.

## Q3. What does the outcome signal cost?

Round 4 found that proxies from the trace did not rank platforms as the checks did. This round looks at single turns. Full tables: [sampling.md](../../research/decision-study/data/sampling.md).

| Platform | Checked turns | Failed | Failed with no sign in the trace | Turns with a sign that were correct |
|---|---|---|---|---|
| Atlas | 82 | 8 | 4 | 13 |
| Beacon | 34 | 15 | 10 | 2 |
| Chatly | 18 | 14 | 5 | 1 |
| All | 134 | 37 | 19 (51%, interval 36% to 67%) | 16 |

A sign is a failed tool call, an empty reply or an inability phrase such as "I can't access".

| Sign | Turns flagged | Of which failed a check | Share of all 37 failures found |
|---|---|---|---|
| Failed tool call | 18 | 4 (22%) | 11% |
| Empty reply | 4 | 4 (100%) | 11% |
| Inability phrase | 13 | 11 (85%) | 30% |

- **The trace misses half of the failures.** The answers that are wrong but look normal are the largest group. On Beacon they are 10 of 15.
- **A failed tool call says little.** Agents retry. On Atlas, 12 of 13 turns with a tool error still passed their checks. Counting tool errors as failures punishes the platform that has tools and uses them.
- **An inability phrase is honest.** When a tool says it cannot reach something, it is usually right. That is a signal about a missing capability (Q5), not a quality score.
- **Flags tell a reviewer where to look.** A flagged turn failed 53% of the time, against 28% on average. A rate must still come from a random sample: unflagged turns failed 19% of the time.

| Checked turns per platform | Best platform picked | Whole order right |
|---|---|---|
| 3 | 74% | 47% |
| 5 | 85% | 67% |
| 10 | 96% | 90% |
| 20 | 100% | 99% |

The table is a simulation that takes the observed pass rates (88%, 49%, 15%) as true.

- **The platform-level answer is cheap.** 30 checked turns in a period are enough here.
- **The task-type answer is not.** About 10 checks per platform and task type are needed, 210 in all. The window produced 134 checkable turns, and 16 of 21 cells had fewer than 10. Close pairs need far more: 50 per cell for the task type where Atlas and Beacon are nearest.
- **Use cannot fill the cells.** People choose platforms by habit, so some cells stay small however long the window. Routing by task type needs a test set that is run on purpose.
- **Even the full matrix supports little per task type.** With every script on every platform, 9 of 21 comparisons inside a task type are significant, and 7 after correction for many tests. Overall the three platforms differ clearly, also with the script as the unit (Atlas against Beacon: +39 points, interval +24 to +53).

## Q4. When can a seat be called unused?

Round 4 flagged seats under 10% of the holder's use. This round adds a rule that asks for evidence: flag a seat only when so few task starts would be unlikely (under 5%) if the holder really used it for 10% of their tasks. Full tables: [seats.md](../../research/decision-study/data/seats.md).

| Rule | Flagged | Correct | Wrong | Missed | Monthly price of the wrong flags |
|---|---|---|---|---|---|
| Under 10% of sessions | 6 | 3 | 3 | 1 | 60 |
| Under 10% of task starts | 7 | 4 | 3 | 0 | 60 |
| Evidence rule | 0 | 0 | 0 | 4 | 0 |

- **The evidence rule flags nothing in two weeks, and that is the honest answer.** A seat with no start is evidence only after its holder has made 29 task starts. The busiest holder made 9.
- **Waiting takes long at this level of use.** At the observed rates, holders with several seats need 4 to 56 more weeks.
- **A seat used only after failures is not idle.** One seat had 2 sessions and no task start. Its holder went there when another platform failed. Cancelling it removes the fallback.

A design study simulated longer windows from the designed habits and the observed task rates (4,000 runs each).

| Weeks | Share rule: precision | Share rule: windows with a wrong flag | Evidence rule: idle seats found | Evidence rule: windows with a wrong flag |
|---|---|---|---|---|
| 2 | 0.56 | 97% | 0% | 0% |
| 4 | 0.71 | 85% | 0% | 0% |
| 8 | 0.83 | 61% | 6% | 0% |
| 13 | 0.90 | 38% | 40% | 0.1% |
| 26 | 0.97 | 14% | 68% | 0.1% |

- **The share rule is fast and often wrong.** It finds the idle seats at once and flags a seat in use in most short windows.
- **The evidence rule is slow and almost never wrong.** It suits an action that costs something to undo.
- **Volume changes everything.** With five times the task rate, the evidence rule finds 64% of the idle seats in 4 weeks and all of them in 26.
- **The two rules fit two actions.** The share rule decides whom to ask. The evidence rule decides what to cancel.

## Q5. What does a switch say about what to build?

When a person re-does a task on another platform, the second session shows what the first platform lacked. For each of the 13 switches, the study lists the tools, skills and MCP servers used at the destination that never appear on the origin platform. Full tables: [demand.md](../../research/decision-study/data/demand.md).

| From | To | Switches | Used at the destination, never seen at the origin |
|---|---|---|---|
| Chatly | Atlas or Beacon | 3 | the `shop` MCP server (3 of 3) |
| Beacon | Atlas | 3 | the skill `weekly-sales-report` (3 of 3) |
| Beacon | Chatly | 4 | nothing |
| Atlas | Chatly | 3 | nothing |

- **6 of 13 switches point at a missing capability.** For Chatly it is company data. For Beacon it is one skill.
- **The chat platform tells you itself.** 11 of 22 Chatly turns carry an inability phrase, and 8 more tasks ended there on one. With the 3 switches, 11 tasks failed for want of company data.
- **The other 7 switches went to a platform with fewer tools.** The trace cannot say why. In 3 of them the first session shows no sign of trouble at all.
- **Skills are again the lever.** Round 3 found 88% correct with skills and 49% without. Here the trace shows which skill people went looking for.

By task type, lookups failed most: 7 of 10 lookup tasks were re-done or ended on trouble, and 5 of 10 reports. The task type is a label, and Q6 shows how far to trust it.

## Q6. Can the work map be compared across platforms?

Every script was recorded on all three platforms, so each has three labels. If the label depends on the work and not on the tool, the three should agree.

| Label | Atlas and Beacon | Atlas and Chatly | Beacon and Chatly | All three agree | Equals the designed label (Atlas, Beacon, Chatly) |
|---|---|---|---|---|---|
| Domain | 91%, kappa 0.85 | 72%, kappa 0.55 | 66%, kappa 0.44 | 21 of 32 | 88%, 78%, 69% |
| Task type | 66%, kappa 0.59 | 41%, kappa 0.31 | 50%, kappa 0.40 | 11 of 32 | 66%, 59%, 50% |

- **Domain compares between the two agent platforms.** It is good enough for a work map by domain there.
- **Task type does not compare.** The same work gets a different task type on another platform two times in three.
- **The chat platform reads differently.** Its transcripts have no tool lines and many replies that say what it cannot do. The label follows the transcript, not the request.
- **The labels came from many small free models.** A single stronger model would agree with itself more. The gap between platforms is still a warning: a label must be tested across sources before two platforms are compared by it.

## Q7. The cards

`cards.py` fills the card contract of [ADR 0006](../adr/0006-insight-card-contract.md) by fixed rules. Full cards: [cards.md](../../research/decision-study/data/cards.md).

| # | Card | Decision | Evidence | Readiness |
|---|---|---|---|---|
| 1 | The cost is in the seats, not in the tokens | D1 | counted | act |
| 2 | Atlas gets the most answers right | D3 | checked | act |
| 3 | Quiet seats, not yet unused seats | D1 | linked | watch |
| 4 | Chatly lacks the MCP server shop | D4 | linked | act |
| 5 | Half of the wrong answers leave no sign in the trace | D3 | checked | act |
| 6 | Work that is done twice | D4 | linked | check first |
| 7 | Beacon lacks the skill weekly-sales-report | D4 | linked | check first |
| 8 | Not enough checks to route by task type | D3 | checked | watch |
| 9 | The work map cannot be compared across platforms yet | D2 | labelled | watch |

- **Round 4's seat card said "7 seats nobody uses, worth 150 per month".** The same data now says: 7 quiet seats, none proven unused, ask or wait.
- **Round 4's routing card said "send each task type to the platform that gets it right".** Now the platform-level choice says `act` and the task-type choice says `watch`, with the number of checks it needs.
- **Three cards say `watch`.** That is a result. It tells the owner what the data cannot support yet and what would change that.
- **Two decisions have no card.** D5 has no label. D6 is the personal report and is not for the organisation.
- **The `checked` cards use the simulation's ground truth in the place of real checks.** A company would have them only after setting up the sample of [ADR 0007](../adr/0007-outcome-signal.md).

## What changes in our understanding

| Topic | After round 5 | Confidence |
|---|---|---|
| Trace schema | Enough for all six decisions. Cost, turn order and the MCP server are derived. A Required attribute can be missing at the source | Medium |
| Content | Almost every decision needs the user's message and the visible reply. A deployment without content gets seat use by session and nothing else | High |
| Unit | The task, not the session, for use, cost and quality. Linking works on the easy case | Medium for the need, low for the rule |
| Cost | At light use, seats cost hundreds of times the tokens | Medium |
| Outcome | Trace signals miss half of the failures. A random sample of about 10 checks per platform settles a large gap. Task-type routing needs a planned test set | Medium |
| Tool errors | A failed tool call is a cost, not a sign of a wrong answer | Medium |
| Seats | A share rule is for asking. An evidence rule is for cancelling, and it needs months at light use | Medium |
| Unmet demand | The session after a switch shows the missing capability. An inability phrase is a reliable sign of one | Low-medium |
| Labels | Domain compares across similar platforms. Task type does not compare across platforms | Medium |
| Cards | A card needs its kind of evidence, its error and a readiness. Without them, counted and guessed numbers look the same | High |

## Limitations

- **The company is simulated.** Users react by rule: they notice a failed check with probability 0.8 and switch with probability 0.7. Real people switch for other reasons and at other times.
- **The linking rule had an easy case.** Every re-ask came 2 to 12 minutes later, on another platform, and no person started two similar tasks in a row. A retry on the same platform and a task resumed days later are not in the data.
- **The ground truth stands in for checks.** The full matrix of 32 scripts on 3 platforms is a planned test set. A company gets one only by running it.
- **Gaps between platforms are large.** 88%, 49% and 15% are easy to tell apart. The sample sizes in Q3 do not carry over to platforms that are close.
- **Small numbers.** 64 tasks, 13 switches, 37 failed turns, 24 seats. Most per-platform cells hold fewer than 20 observations.
- **Staff are light users.** 2.7 tasks per person per week. The licence-to-token ratio and the waiting times for seats depend on this.
- **Shadow costs are list prices** of the paid twins of free models. Failed requests carry no tokens and count as zero.
- **The seat simulation draws from the designed habits.** It shows how the rules behave, not how real use varies from week to week.
- **Labels belong to recordings.** A session takes the label of the script it resembles most on its platform. 76 of 77 sessions matched the right script.
- **Roles have four people.** The [privacy model](../privacy.md) proposes a minimum group of five, so the per-role tables here would not be shown.

## Suggested next steps

1. **Harder cases for the linking rule.** Add a retry on the same platform, a task resumed the next day, and two similar tasks in a row. Measure precision and recall again before [ADR 0005](../adr/0005-task-as-unit-of-work.md) is accepted.
2. **A check sampler.** A small tool that draws a random sample of turns per platform, takes a verdict and writes it as a `gen_ai.evaluation.result` event. It turns D3 from blocked to ready.
3. **Closer platforms.** Re-run the sampling budget with platforms that differ by 10 points, not 40, and with a platform that wins only some task types.
4. **One labelling model.** Label all recordings with one model and test the agreement across platforms again. If task type still disagrees, change the label, not the model.
5. **A sensitivity label.** Define it in the privacy model and test it on the lake, so that D5 has a first card.
6. **Real traces.** One real source in the trace schema, even a small one, would test the transformer, the rule and the cards on data that nobody designed.
