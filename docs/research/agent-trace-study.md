# Agent trace study (round 3): observability and Prism on the same traces

Status: round 3 · 2026-11-14 · Previous: [round 2](context-study-round2.md) · Code and data: [research/agent-study](../../research/agent-study/)

Rounds 1 and 2 used other people's logs, with no ground truth and no control over the agent. This round builds a small agent of our own, with MCP servers and skills, runs it through scripted sessions and logs every turn as a trace. Because the sessions are scripted, each one has **designed labels** and many turns have **verifiable answers**. The same traces are then read in two ways:

- **Part A, observability:** how the agent, its MCP servers and its skills performed, and what a correct answer costs.
- **Part B, Prism:** how the three people worked, and how well Prism's labels recover what was designed.

## TL;DR

1. **`openrouter/free` is enough to run the whole study.** About 830 model requests, $0 spent. It routes each request to one of about a dozen free models, so results describe the router, not one model.
2. **Skills were the best value in the system.** With skills, 88% of verifiable turns were correct; with the skills removed, 49%. On outcome checks only (numbers, database state, files) it was 80% against 24%. Skills cost no extra tokens. The control group of sessions that need no skill did not move (100% against 96%).
3. **Skills are found, but not always followed.** The right skill was loaded in 20 of 20 sessions, yet weekly reports were right only 71% of the time. The usual failure was date arithmetic and guessed column names, not the skill.
4. **MCP tool schemas are 68% of all input tokens.** The custom `shop` server made 80% of the tool calls with 7% of the input tokens. The reference `memory` server cost 21% of input tokens for 5 calls. Attaching only the servers a session uses would cut input tokens by 36%.
5. **Reliability is the price of free.** 12% of model requests failed (HTTP 400, empty replies, rate limits), 6 of 100 turns ended with no answer, and p95 turn latency was 107 seconds.
6. **Prism's cheap view holds on agent traces.** A compact view of about 290 tokens per session (0.6% of what the agent consumed) gave the designed domain in 84–90% of sessions. Per-prompt act labels reached 79% (κ 0.66), in line with round 2.
7. **Counts work, with one rule each.** Corrections were counted exactly from the prompt alone (4 of 4). Re-explanation needs the session (0 of 2 from the prompt alone). "Questions" were over-counted from the prompt alone (25 against 14), because a request phrased as a question looks the same.
8. **The two readings are worth more together.** Observability says the operations person got the worst service (74% correct against 94% and 100%). Prism says what that person was doing (reports and data analysis). Neither says both.

## Setup

| Item | Detail |
|------|--------|
| Agent | A tool-calling loop (at most 8 model requests per turn) acting as "operations assistant" of a fictional three-person coffee-gear shop |
| Model | `openrouter/free` for every call: the agent, the labels and the narrator |
| MCP servers (no auth, local stdio) | `shop`: custom, SQLite, 5 tools. `filesystem`: reference server from npm, 14 tools. `memory`: reference server from npm, 9 tools |
| Skills | 6 skills in `SKILL.md` format (refund eligibility, weekly sales report, ticket triage, customer reply, inventory reorder, price change memo). The agent sees names and descriptions and loads a body with `load_skill` |
| Sessions | 32 sessions, 100 user turns, 3 people (support lead, operations, founder), placed on 2 to 13 November 2026 |
| Ground truth | Per session: domain, task type, expected skill and servers. Per turn: the act it was written as. 75 turns have checks against the database, files or reply text |
| Traces | 1 trace per user turn: `invoke_agent` root, one `chat` span per model request (failed attempts included), one `execute_tool` span per tool call. 664 spans in the main run |
| Ablation | The same 32 sessions with the skills removed |

## Part A. Observability

Full tables: [observability.md](../../research/agent-study/data/observability.md).

### A1. Reliability

| Metric | Value |
|---|---|
| Model requests | 327, of which 38 failed (12%) |
| Failed request types | HTTP 400 from a provider: 21 · empty reply: 12 · rate limit: 4 · HTTP 502: 1 |
| Tool calls | 237, of which 20 errors (8%) |
| Turns with no answer | 6 of 100 (3 hit the step limit, 3 exhausted retries) |
| Model requests per turn | 3.3 mean, 8 max |
| Turn latency | p50 22.6 s, p95 107 s |
| Verifiable turns correct | 66 of 75 (88%) |

- **All 21 HTTP 400 errors came after the `weekly-sales-report` or `inventory-reorder` skill had been loaded,** and the ablation run without skills had 2 failed requests in total. A replay of that conversation shape did not reproduce the error, so the cause is not known. The tracer did not store the provider's error message. It does now (`error.message`).
- **Tool errors are almost all SQL.** 16 of 20 were `shop__run_sql`, mostly guessed column names (`oi.sku`, `o.order_id`). The agent called `list_tables` only 21 times in 100 turns. Putting the schema in the tool description would remove most of these.
- **The step limit hides real cost.** Two of the three step-limit turns spent all 8 requests recovering from guessed column names.

### A2. The free router

Eleven models answered. The largest share was 12% and the smallest 6%, so no model dominated. Only 4 tool calls were malformed (invalid JSON arguments or a made-up tool name). Per-model answer quality cannot be separated with this sample: the final answer of a turn came from each model fewer than 10 times.

### A3. MCP usage

| Server | Tools offered | Tools used | Calls | Error rate | Sessions using it | Schema tokens sent (share of input) | Schema tokens per call made |
|---|---|---|---|---|---|---|---|
| shop (custom) | 5 | 5 | 163 | 10% | 31 | 107,754 (7%) | 661 |
| filesystem (reference) | 14 | 8 | 35 | 6% | 13 | 579,464 (40%) | 16,556 |
| memory (reference) | 9 | 3 | 5 | 0% | 3 | 305,090 (21%) | 61,018 |

- Every server was used in every session designed to need it (shop 29/29, filesystem 9/9, memory 1/1), so the agent finds the right server.
- **12 of 28 tools were never called.** Tool schemas are sent with every model request whether used or not.
- **Schema tokens per call made** is the useful ratio. `memory` costs about 61,000 input tokens of schema for each call it actually served, `shop` about 660.
- Token shares are estimated by splitting each request's reported input tokens in proportion to characters.

### A4. Skill usage

| Skill | Sessions designed for it | Sessions that loaded it | Recall | Loads |
|---|---|---|---|---|
| weekly-sales-report | 6 | 8 | 6/6 | 8 |
| refund-eligibility | 4 | 6 | 4/4 | 6 |
| customer-reply | 4 | 9 | 4/4 | 9 |
| inventory-reorder | 3 | 4 | 3/3 | 4 |
| ticket-triage | 2 | 4 | 2/2 | 4 |
| price-change-memo | 1 | 1 | 1/1 | 1 |

- **Recall is 20 of 20.** In 15 of the 20 sessions the skill was loaded in the first turn.
- A skill was never loaded twice in a session, so the body stays usable in context.
- The extra loads are mostly sensible second skills, for example `customer-reply` after a refund decision. The session-level design has one main skill, so it cannot score these.

### A5. Value for money

Free models cost nothing, so cost is reported as **shadow cost**: tokens priced at the paid version of the model that served the call, or at the median of those prices where there is no paid version.

| Metric | Value |
|---|---|
| Actual spend | $0 |
| Shadow cost, 100 turns | $0.22 |
| Shadow cost per turn / per session | $0.0022 / $0.0069 |
| Share of cost on turns that failed their checks | 17% |
| Input tokens per turn | 15,234 |
| Input share of cost | 79% |
| Share of input that is MCP tool schema | 68% |
| Input tokens saved by attaching only the servers a session uses | 36% |

**Ablation: the same sessions without skills.**

| Turns | Arm | Verifiable turns correct | Input tokens per turn | Shadow cost per 1,000 turns | Shadow cost per 1,000 correct turns |
|---|---|---|---|---|---|
| All | with skills | 66/75 (88%) | 15,234 | $2.21 | $3.35 |
| | without | 37/75 (49%) | 16,017 | $2.78 | $7.51 |
| Skill designed, outcome checks only | with skills | 20/25 (80%) | 16,616 | $2.42 | $3.03 |
| | without | 6/25 (24%) | 18,041 | $2.59 | $10.80 |
| No skill designed (control) | with skills | 23/23 (100%) | 14,544 | $1.93 | $3.01 |
| | without | 22/23 (96%) | 13,748 | $2.66 | $4.35 |

The last column divides all spend in the group by the number of correct verifiable turns.

- **Skills more than halve the cost of a correct answer** and add no tokens: the six descriptions and the bodies loaded on demand are smaller than the extra exploration the agent does without them.
- **Part of the gap is by construction.** Skills hold house rules that exist nowhere else (net revenue excludes refunds; the reply sign-off), and some checks test exactly those. The "outcome checks only" rows leave out all checks on reply wording and still show 80% against 24%.
- **By skill:** refund eligibility 83% against 17%, ticket triage 100% against 17%, weekly sales report 71% against 18%. Inventory reorder stayed weak with the skill (60%): the formula needs multi-step SQL that the free models often got wrong.

### A6. What observability alone can and cannot say

It answers "is the tool used, does it fail, what does it cost". It does not say *why* the people came, or whether a correction was the person changing their mind or the agent being wrong. That is Part B.

## Part B. Prism

Full tables and the three narrated reports: [prism_report.md](../../research/agent-study/data/prism_report.md).

The pipeline follows the architecture: trace facts without a model, a compact chat view, labels, SQL aggregates, one narrator call per person. Labels were produced two ways, to test the open question on the labelling unit:

- **per session**, from the compact view, twice (draws A and B; the router picked 9 different models);
- **per prompt**, from the prompt alone, one call each (11 different models).

### B1. Extraction input

The compact view (user text, one line of tool activity per turn, reply head and tail; skill bodies and tool outputs left out) is about **291 tokens per session**. The agent consumed 47,606 input tokens per session, so the view is 0.6% of that.

### B2. Session labels against the design

| Label | Draw A correct | Draw B correct | A–B agreement |
|---|---|---|---|
| domain | 90% | 84% | 97%, κ 0.95 |
| task type | 68% | 66% | 81%, κ 0.77 |

The two draws agree with each other far more than with the design on task type. The label is stable; the design is the weaker side. Many misses are sessions with two tasks, for example a lookup that ends in a drafted reply, where "the main task" has no single answer. This supports labelling segments or prompts instead of forcing one task type on a session.

### B3. Behaviour counts against the design

| Count | Designed | Session label A | Session label B | Per-prompt | Per-prompt exact per session | Per-prompt ρ |
|---|---|---|---|---|---|---|
| corrections | 4 | 6 | 7 | 4 | 100% | 1.00 |
| feedback relays | 5 | 3 | 5 | 4 | 91% | 0.56 |
| refinements | 12 | 10 | 11 | 14 | 88% | 0.77 |
| understanding questions | 14 | 7 | 9 | 25 | 69% | 0.67 |
| sessions with re-explanation | 2 | 1 found | 1 found | 0 found | | |

- **Corrections:** the prompt alone is exact. Session-level labels over-count (6 and 7 against 4).
- **Understanding questions:** per-prompt labels over-count, session labels under-count. From the prompt alone, "How many open tickets do we have?" (a request for a fact) and "Why do we count from delivery?" (a question to understand) look alike. The definition needs to separate *asking for a fact* from *asking to understand*.
- **Re-explanation** cannot be seen from one prompt. This matches round 2, where it became measurable only with turn numbers as evidence inside the session.
- **Feedback relays:** small numbers, mixed results.

### B4. Per-prompt acts

Accuracy 79%, κ 0.66 (n=100). Round 2 measured 73–75% and κ 0.68–0.71 for intent on SWE-chat, so the result carries over from coding sessions to business tasks and from pinned models to the free router.

| Act | Designed | Predicted | Recall | Precision |
|---|---|---|---|---|
| request | 63 | 53 | 76% | 91% |
| refinement | 12 | 14 | 92% | 79% |
| correction | 4 | 4 | 100% | 100% |
| feedback relay | 5 | 4 | 40% | 50% |
| question | 14 | 25 | 100% | 56% |
| re-explain | 2 | 0 | 0% | – |

### B5. Aggregates and the narrated report

| Person | Sessions | Turns | Active days | Corrections | Refinements | Questions | Tool calls per turn | Sessions with a skill | Verified turns correct | When |
|---|---|---|---|---|---|---|---|---|---|---|
| Arjun (operations) | 11 | 36 | 10 | 1 | 4 | 7 | 2.7 | 7 | 20/27 | afternoons (8), mornings (3) |
| Lena (founder) | 8 | 25 | 7 | 1 | 6 | 8 | 2.7 | 6 | 15/15 | evenings |
| Maya (support) | 13 | 39 | 9 | 2 | 4 | 10 | 1.9 | 11 | 31/33 | mornings |

All numbers come from SQL over the records and trace facts ([prism.py](../../research/agent-study/prism.py)).

One narrator call per person received only these aggregates and four one-line summaries.

- **No invented numbers.** Every number in the three reports appears in the aggregates (automatic check).
- **The number check is not enough.** One report advised the person to "enable the feedback relay feature". No such feature exists: the narrator read a label name as a product feature. The narrator needs the definitions of the labels, and the validation needs more than numbers.
- The reports read as intended otherwise: when each person works, what on, which skills, and one concrete failure taken from a summary.

### B6. Where the two readings meet

Both analyses share one key, the session id, so they join in SQL.

- **Who is served worst.** Verified turns correct: Arjun 74%, Maya 94%, Lena 100%. Prism's records say why this splits by person: Arjun's sessions are reports and data analysis, the SQL-heavy work where the agent fails. An adoption dashboard would show Arjun as an active user. The joined view shows a user the tool is failing.
- **A correction is not always the agent's fault.** In one session the scripted user wrongly told the agent it had mixed up two orders. The agent checked again and correctly stood by its answer. Prism counts one correction. The check shows the agent was right. A report that says "you corrected the assistant twice" is more useful with "and it was wrong once".
- **Skill use per person** comes from trace facts, not from a model: Maya used a skill in 11 of 13 sessions, and those are the sessions where the ablation shows the largest gain.

Scripted users limit this part. Their corrections do not depend on what the agent did, so this study cannot measure whether corrections follow agent errors. That needs real or simulated-reactive users.

## What changes in our understanding

| Topic | After round 3 | Confidence |
|---|---|---|
| Compact chat view on agent traces | Enough for domain. About 290 tokens per session, under 1% of the agent's own input | Medium-high |
| Labelling unit | Per prompt for acts and corrections. Per session (with evidence) for re-explanation. Task type per segment or prompt, not one per session | Medium |
| Counts as the reporting unit | Corrections and refinements work. "Understanding questions" needs a sharper definition | Medium |
| Narrator | Does not invent numbers when given aggregates only. Can still misread label names | Medium |
| Trace facts | Skill loads, tool calls by server, errors and cost need no model and join cleanly to records | High |
| Free models | Usable for extraction and narration. Expect about 1 failed call in 30 and slow throughput | Medium |
| Observability and Prism | Complementary. Recommended: keep Prism out of observability (non-goal), but allow a join to answer quality where the platform has it | Proposal |

## Limitations

- **Scripted users.** Turns do not react to the agent. Designed acts are the ground truth for labels, not evidence about natural behaviour.
- **One author wrote both the sessions and the label definitions,** so the designed labels may fit the codebook better than real data would.
- **Small numbers.** 32 sessions, 100 turns, 4 corrections, 2 re-explanations.
- **The router is not reproducible.** A rerun gets different models per call. The ablation's control group moved by 4 points, which is a rough size for this noise.
- **Checks are imperfect.** Four checks were loosened after reading the failures (re-applied to the stored traces with `rescore.py`): one asked for a keyword where the agent was right in other words, one tested an ambiguous definition.
- **Token shares for tool schemas are estimates** from character counts.
- **Simulated time.** Time-of-day patterns are designed, not observed.

## Suggested next steps

1. **Trim the MCP surface and rerun:** attach servers per session, or expose only the tools used. Expected: about a third fewer input tokens at the same quality. This is a one-line change to `mcp_client.py`.
2. **Put the database schema in the `run_sql` description** and measure SQL errors and step-limit turns again.
3. **Reactive user simulation:** let a model play the three people and decide whether to correct, so that corrections depend on what the agent did. This makes B6 measurable.
4. **Split "question" into fact request and understanding question** in the codebook, and re-measure on these traces and on SWE-chat.
5. **Give the narrator the label definitions** and add a check for claims about features or events that are not in the aggregates.
6. **Write the OpenTelemetry adapter against this trace file.** It already uses the GenAI attribute names, so it can serve as the first fixture for Phase 1.
