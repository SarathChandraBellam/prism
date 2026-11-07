# Context study, round 1: results

Status: round 1 · 2026-11-07 · Plan: [context-study-proposal.md](context-study-proposal.md) · Code: [research/study](../../research/study/)

## TL;DR

1. **Some labels can't be measured reliably yet.** On full traces, two strong models agree well on domain and task (κ 0.60–0.63) but poorly on collaboration pattern (κ 0.34), outcome (κ 0.35) and context re-explanation (κ 0.11). The "directive" share a user would see is **30% or 9% depending only on which reference model labels it**.
2. **A compact view is enough.** User messages plus agent activity plus the head and tail of each reply (C3, about 2k tokens) matched or beat the full trace (C6, about 15k tokens, 7× more) for every label with cheap models. The strong model also reached 84–89% of its own full-trace labels from C3.
3. **Assistant replies matter, tool outputs didn't.** Adding reply snippets lifts outcome from 40% to 76%. Adding tool-error excerpts (C4) added nothing measurable.
4. **20–51% of "user" turns in agent logs are not typed by a person.** Keeping that text broke one label: re-explanation fell from 95% to 64%.
5. **Folding traces in one at a time drifted.** The folded record matched the same model's whole-session label on only 56–65% of fields, and agreed with the reference less than whole-session labelling did.
6. **Batched turn labelling is fragile.** 56% of batched calls returned the wrong number of turns. The turn-level results are therefore inconclusive.
7. **It's cheap when thinking is truly off.** C3 costs $0.00006–0.00033 per session with cheap models. The pilot's "thinking tokens dominate cost" was largely a configuration error: `reasoning: {enabled: false}` was not honoured, while `effort: none` was.

## Setup

| Item | Detail |
|------|--------|
| Sessions | 125 with ≥3 human turns: own Claude Code logs (19), Fable-5 Claude Code traces (6), DataClaw Claude Code sessions (50, one other developer), WildChat chats (50; 25 English, 25 other languages) |
| Not yet included | SWE-chat: its gated terms have not been accepted yet |
| Context conditions | C1 user messages · C2 + agent activity (tool counts, errors) · C3 + head and tail of the final reply per turn · C4 + tool-error excerpts · C6 near-full trace (all text, thinking and tool I/O, items truncated, capped at about 100k tokens) · C3H = C3 with harness-injected text kept |
| Labels | domain, task type, collaboration pattern (Economic Index's five), outcome, context re-explained |
| Cheap models | Gemma-4-26B, Qwen3.7-Flash, DeepSeek-v4.1-Flash |
| References | Claude Haiku 5.5 and GPT-6-Luna on C6. The "consensus" for a label is the sessions where both agree. |
| Other runs | Turn-level acts at four context layers (46 sessions). Turn-by-turn fold with Qwen (25 sessions). |
| Spend | $1.93 for this round. Reasoning disabled via `effort: none`. No-retention providers. |

**How to read the numbers:**
- Agreement is measured against the reference consensus, so it covers only sessions where both references agree. Those are easier sessions, which flatters absolute accuracy.
- Comparisons *between* conditions are fair, because every condition is scored on the same sessions.
- The consensus is built from the full trace (C6), which biases the comparison towards C6, not against it.
- Ranges are 95% bootstrap intervals.

## Results

### 1. Measurability: reference models on the full trace

| Label | Agreement | κ |
|---|---|---|
| domain | 73% | 0.63 |
| task type | 65% | 0.60 |
| collaboration pattern | 55% | 0.34 |
| outcome | 53% | 0.35 |
| context re-explained | 70% | 0.11 |

The two references describe the same 122 sessions very differently:

| Labels from | directive | feedback loop | task iteration | learning | validation |
|---|---|---|---|---|---|
| Claude Haiku 5.5, C6 | 30% | 16% | 37% | 13% | 4% |
| GPT-6-Luna, C6 | 9% | 11% | 70% | 11% | 0% |

The user-facing "how much do you delegate" number currently reflects the labelling model as much as the person. Agreement also varies by source; for collaboration pattern it ranges from 47% (own logs) to 59% (DataClaw).

### 2. Context curve: cheap models against the reference consensus

| Condition | domain | task | collab | outcome | reexpl | tokens/session |
|---|---|---|---|---|---|---|
| C1 user only | 82% | 76% | 69% | **40%** | 88% | 811 |
| C2 + activity | 83% | 78% | 67% | 51% | 89% | 922 |
| **C3 + reply head/tail** | **86%** | **81%** | **73%** | **76%** | **95%** | 2,079 |
| C4 + error excerpts | 86% | 81% | 73% | 75% | 95% | 2,098 |
| C6 near-full | 83% | 78% | 73% | 74% | 94% | 14,797 |

The intervals are about ±5 points. For example, C3 outcome is 76% (70–82), against 40% (34–47) for C1.

**The strong model itself** (Haiku against the consensus): C1 42–83%, C3 84–89%, C4 84–88%. C6 is circular here, because Haiku on C6 is one of the references.

**By source,** at C3 vs C6: on our own and Fable logs, outcome needs the replies (22% at C1 against 86% at C3). On WildChat, outcome stays hard even with context (58–62%). For DataClaw, task type stays flat around 70% whatever the context.

### 3. Harness-injected text

**Measured on the same 55 sessions that contain injected text, C3 vs C3H:**
- Domain, task, collaboration pattern and outcome: unchanged within ±4 points.
- **Re-explanation: 95% → 64%.** Repeated skill instructions and notifications look like the user repeating context.

**Share of "user" turns that are injected:**
- own logs: 20%
- DataClaw: 25%
- Fable: 51%

### 4. Models (mean over the five labels)

| Model | C1 | C3 | C6 | $/session C3 | $/session C6 |
|---|---|---|---|---|---|
| DeepSeek-v4.1-Flash | 78% | **88%** | 87% | $0.00033 | $0.00214 |
| Gemma-4-26B | 76% | 86% | 79% | $0.00019 | $0.00123 |
| Qwen3.7-Flash | 64% | 75% | 77% | $0.00006 | $0.00116 |
| Claude Haiku 5.5 | 72% | 86% | (ref) | $0.00049 | $0.00472 |
| GPT-6-Luna | – | 92% | (ref) | $0.00036 | $0.00199 |

Gemma does *worse* on the full trace (79%) than on C3 (86%). Long, noisy input hurts small models.

### 5. Incremental fold

| Session length | fold = same model, whole session | fold vs consensus | whole session vs consensus |
|---|---|---|---|
| 6–10 turns | 65% | 61% | 70% |
| 11–25 turns | 56% | 66% | 72% |

The fold drifts away from the whole-session label as sessions grow. It is less accurate, and it needs one call per turn instead of one per session.

### 6. Turn-level acts (inconclusive)

- **The references agreed on only 60% of 48 turns.**
- **200 of 360 batched calls (56%) returned the wrong number of turns.** Sessions had a median of 7 turns and a maximum of 30.
- **On the 29 consensus turns,** cheap models scored 79–84% at every layer, with no clear effect of context.

Batched turn labelling needs a different output format, such as one call per turn or keyed outputs, before this question can be answered.

## What this means for the research questions

| RQ | Round 1 answer | Confidence |
|---|---|---|
| RQ1 unit | Whole-session labelling beat turn-by-turn folding. Turn-level acts are untestable with batched output. | Medium (fold), low (turn) |
| RQ2 context amount | **C3 is enough**, even for a strong model. More context did not help cheap models and sometimes hurt. | Medium-high for domain, task and outcome |
| RQ3 composition | User messages + activity summary + reply head/tail carry the signal. Tool outputs and thinking added nothing measurable. Injected text must be removed. | Medium. Tool outputs were only available for 25 sessions. |
| RQ4 incrementality | The fold drifts, and drift grows with session length | Medium (25 sessions, one model) |
| RQ5 models | DeepSeek-Flash and Gemma at C3 are about $0.0002–0.0003 per session. Turning reasoning off correctly matters most. | Medium |
| RQ6 generalisation | The direction holds across all four sources. Absolute levels differ by source, especially for outcome on chats. | Low-medium (no SWE-chat yet) |
| RQ7 measurability | **Collaboration pattern, outcome and re-explanation are not reliably measurable as currently defined**: κ 0.11–0.35 between strong models | Medium-high |

## Limitations

- **No human labels.** All agreement is with model references. RQ7 suggests that some labels need better definitions before human labels would agree either.
- **The consensus covers only the easier sessions** (where both references agree), so absolute accuracy is optimistic.
- **Small samples:** own (19) and Fable (6) are small, and only those two have tool outputs, so the C4 result is weak.
- **DataClaw is one developer and WildChat is chat only.** Real human-in-the-loop agent data from many people (SWE-chat) is still missing.
- **One prompt and codebook,** with no paraphrase robustness check.

## Proposed round 2

1. **Add SWE-chat.** Needs the terms accepted on Hugging Face. It adds human-in-the-loop agent sessions from many people, with tool outputs, and labels the authors checked against human experts. Use those to check validity for prompt intent and pushback.
2. **Fix the label definitions before measuring more.**
   - Collaboration pattern: test a multi-label or share-based version, and Microsoft's user-goal vs AI-action split.
   - Outcome: separate "resolved" from "abandoned" with explicit evidence rules.
   - Re-explanation: define it with quoted evidence.
   - Re-measure agreement between references; a label must reach κ ≥ 0.6 before we optimise context for it.
3. **Repeat the turn-level test with keyed, per-turn outputs.**
4. **Run a small human audit** (30 sessions) on the redefined labels to anchor validity.
5. **Check prompt robustness:** two paraphrases of the codebook.
