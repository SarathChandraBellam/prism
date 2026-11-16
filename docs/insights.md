# Insight catalogue

> **Status: draft.** Follows [ADR 0004](adr/0004-scope-organisation-decisions.md). This is the list of decisions that Prism serves and what each one reads from traces. The same list is kept as data in [`catalogue.json`](../research/decision-study/catalogue.json), and [round 5](research/decision-study.md) tested every row. Work that serves no row here is out of scope.

## How to read a row

Each decision has:

- an **owner**: the role that can act on the answer;
- a **metric**: the number that answers it, and the **unit** it is counted in ([ADR 0005](adr/0005-task-as-unit-of-work.md));
- the **evidence** it rests on: `counted`, `linked`, `labelled` or `checked` ([ADR 0006](adr/0006-insight-card-contract.md));
- what it **reads** from spans in the [trace schema](trace-schema.md), and what it needs from **outside** the traces;
- a **bar**: what the evidence must show before a card may say `act`;
- its **state** after round 5.

## The six decisions

| | Decision | Owner | Metric | Unit | Evidence | State after round 5 |
|---|---|---|---|---|---|---|
| D1 | Which seats do we pay for? | finance | Task starts per seat, and the chance that a seat this quiet is quiet by luck | task | linked | Ready. Two weeks of data are not enough to cancel a seat |
| D2 | What work goes to AI? | leadership | Share of tasks by domain and task type, per role and platform | task | labelled | Ready by domain on similar platforms. Task type does not compare across platforms |
| D3 | Which tool for which job? | platform owner | Share of checked answers that are correct, per platform and task type; cost per correct task | task | checked | Blocked until answers are checked. About 30 checks per period settle the platform |
| D4 | What do we build next: skills, connectors, context? | enablement | Tasks re-done on another platform or ended on trouble, by the capability that was missing | task | linked | Ready where the platform has tools |
| D5 | Where does sensitive work go? | security | Share of sessions with sensitive content, per platform | session | labelled | Blocked. No sensitivity label or policy exists |
| D6 | How do I work with AI? | the individual | Personal report: topics, task types, time patterns, corrections and refinements | session | labelled | Ready. Studied in rounds 1 to 3 |

## What each decision reads

All decisions read `gen_ai.conversation.id` to group traces into sessions and `service.name` on the resource to know the platform. The table lists the rest.

| | From the root span of each turn (`invoke_agent`) | From model and tool calls | From outside the traces | Without content |
|---|---|---|---|---|
| D1 | `user.id`; the first prompt, to link a re-ask to its first session | | Seat list with prices; a directory that gives one identity per person | Falls back to sessions, so a fallback counts as use |
| D2 | `user.id`; the user's message and the visible reply | Tool names, one line per call | Directory with roles; session labels from a small model | Blocked |
| D3 | `user.id`; the user's message | Tokens and the model that answered, for cost; the `gen_ai.evaluation.result` event, for the outcome | Checked answers; a price table per model; session labels | Blocked |
| D4 | `user.id`; the first prompt; the visible reply | Tool names, skill names, error types | Directory | Blocked |
| D5 | The user's message | Tool arguments | A sensitivity policy and label | Blocked |
| D6 | `user.id`; the user's message and the visible reply | Tool names | Session and prompt labels from a small model | Blocked |

- **Content is opt-in in the conventions, and five of six decisions need it.** Prism needs the user's message and the visible reply of each turn. It needs no tool results, no system prompts and no retrieved documents ([privacy model](privacy.md)).
- **Four things are not in the conventions and are derived:** cost (tokens times a price table), turn order (start time), the MCP server of a tool (the prefix of the tool name) and the platform (the resource's `service.name`).
- **One thing is in the conventions and in no trace:** the outcome of a checked answer ([ADR 0007](adr/0007-outcome-signal.md)).

## The bar for action

| | A card may say `act` when |
|---|---|
| D1 | The chance of seeing this few task starts on the seat, if the holder really used it for 10% of their tasks, is under 5% |
| D2 | The label agrees with a reference set (kappa 0.6 or more), and every group shown is at or above the minimum group size |
| D3 | The interval of the difference in correct answers between two platforms excludes zero, with the task or test script as the unit |
| D4 | The same missing capability shows in at least 5 tasks that were re-done or ended on trouble |
| D5 | A sensitivity label with measured agreement exists, and every group shown is at or above the minimum group size |
| D6 | No bar. The report goes to the person, who judges it |

Below the bar a card says `check first` or `watch`, and states what more it needs. The numbers in these bars are first proposals. Round 5 used them on simulated data.

## What round 5 found for each

- **D1.** Seats cost 304 times the token cost of the work done on them, so the seat is the cost that matters. Seven of 24 seats were quiet and none met the bar. A holder must make 29 task starts before an unused seat is evidence.
- **D2.** Domain labels agree between the two agent platforms (kappa 0.85). Task type agrees on all three platforms for 11 of 32 scripts. The work map is usable by domain and not yet by task type.
- **D3.** Half of the wrong answers leave no sign in the trace, so trace signals cannot stand in for checks. Ten checked turns per platform picked the best of three platforms in 96% of simulated samples.
- **D4.** Every task that left the chat platform used company data on the next one. Three of seven tasks that left the platform without skills used the same skill on the next one.
- **D5.** Not studied. 26 of 77 sessions name an order, ticket or SKU id in a prompt. An id is not sensitivity.
- **D6.** No new work in round 5. The task ([ADR 0005](adr/0005-task-as-unit-of-work.md)) gives the personal report one new line: tasks that the person had to re-do on another tool.

## Adding a decision

A seventh decision needs an ADR that states its owner, metric, unit, evidence, needs and bar, and what the owner would do differently with the answer. If nobody would act on it, it is a metric, not a decision.
