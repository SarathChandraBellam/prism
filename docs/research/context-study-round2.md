# Context study, round 2: results

Status: round 2 · 2026-11-07 · Previous: [round 1](context-study-round1.md) · Plan: [proposal](context-study-proposal.md) · Code: [research/study](../../research/study/) (`round2.py`, `analyze2.py`)

## TL;DR

1. **Counts are reliable; categories are not.** Redefining collaboration pattern and outcome as better-specified categories did not make the two reference models agree more (κ 0.22–0.34). Simple **counts of observable behaviour** did agree: corrections, feedback relays, refinements and understanding questions reached Spearman ρ 0.62–0.77 between references, and 73–88% were within ±1.
2. **The counts also match an external, human-validated source.** On SWE-chat, our count of feedback relays tracks SWE-chat's failure-report labels (ρ 0.68–0.70), and our count of understanding questions tracks its "understand" intent (ρ 0.59–0.66). Corrections track less well (ρ 0.25–0.41), most likely because SWE-chat defines "correction" much more broadly.
3. **Requiring evidence fixes re-explanation.** Asking for the turn numbers where the user repeated themselves raised reference agreement from κ 0.09 to **κ 0.48**.
4. **Outcome is meaningful but hard to pin down.** Our redefined outcome tracks SWE-chat's session success score (completed ≈ 82–86, partial ≈ 74–77, failed or abandoned ≈ 45–54), but the two references still disagree on the exact category (κ 0.22–0.29).
5. **Per-prompt labels: less context is better.** Against SWE-chat's labels, intent was most accurate from **the prompt alone** (73–75%, κ 0.68–0.71). Adding the previous reply and activity lowered it to 65%, and adding previous prompts lowered it to 60–62%. Pushback was poor at every context level (κ 0.23–0.35).
6. **The compact view still holds on many people's agent data.** On SWE-chat (32 sessions, 32 people), C3 (about 1.5k tokens) matched the full trace (about 35k tokens, 24× more) on domain, task, outcome and re-explanation. The full trace was better only on collaboration pattern (91% vs 82%, n=22).

## Setup

| Item | Detail |
|------|--------|
| New data | **SWE-chat v2**: 32 Claude Code sessions from 32 different people, with 3–25 prompts each, transcripts under 6 MB, stratified by length. 252 of their prompts were matched to SWE-chat's per-prompt labels (intent, pushback). SWE-chat's own labelling model was validated against human expert labels. |
| Round 1 data reused | 125 sessions (own logs, Fable, DataClaw, WildChat) |
| A: codebook v2 | Both references (Claude Haiku 5.5, GPT-6-Luna) labelled 156 sessions at C3 with the original v1 labels and the redefined v2 labels. v2 adds collaboration *shares*, a "handed over upfront" flag, four behaviour counts, evidence-based outcome and evidence-based re-explanation. |
| B: per-turn | One call per prompt (no batching), at three context layers, with Gemma-4-26B and DeepSeek-v4.1-Flash, scored against SWE-chat's prompt labels |
| C: context curve | Gemma and DeepSeek at C1, C3, C6 and C3H on SWE-chat sessions, against the consensus of the two references on C6 |
| Spend | $1.09 this round ($3.22 across both rounds) |

**Note on SWE-chat's labels:** they are model labels that the SWE-chat authors validated against human experts ("moderate to high" agreement). They are the closest thing to human labels we have, not human labels themselves.

## A. Redefined labels: do the references agree more?

Both references, same 156 sessions, same C3 view:

| Label | Definition | Agreement | κ |
|---|---|---|---|
| domain | v1 | 71% | 0.56 |
| task type | v1 | 67% | 0.62 |
| collaboration pattern | v1 (single category) | 57% | 0.35 |
| collaboration, dominant share | v2 (shares) | 54% | 0.34 |
| outcome | v1 | 59% | 0.43 |
| outcome | v2 (evidence rules, 5 categories) | 45% | 0.22 |
| outcome | v2, completed categories merged | 56% | 0.29 |
| context re-explained | v1 (yes or no) | 73% | 0.09 |
| **context re-explained** | **v2 (turn numbers as evidence)** | **84%** | **0.48** |
| handed over upfront | v2 | 96% | −0.01 (almost always "no", so the label carries no information) |

The collaboration shares also differ between references by **36 percentage points** on average.

**Behaviour counts (v2):**

| Count | Within ±1 | Spearman ρ between references |
|---|---|---|
| corrections | 88% | 0.72 |
| feedback relays | 84% | 0.74 |
| refinements | 73% | 0.62 |
| understanding questions | 82% | 0.77 |

**External check against SWE-chat** (32 sessions):

| Our count | SWE-chat label count | ρ (Haiku) | ρ (Luna) |
|---|---|---|---|
| feedback relays | failure reports | 0.70 | 0.68 |
| understanding questions | "understand" intent | 0.59 | 0.66 |
| corrections | correction pushback | 0.41 | 0.25 |

SWE-chat labels 44% of the aligned prompts as "correction", so its definition is far broader than ours.

| Our outcome (v2) | Mean SWE-chat session success (Haiku labels, n) | (Luna labels, n) |
|---|---|---|
| completed, confirmed | 86 (4) | – (0) |
| completed, unconfirmed | 84 (18) | 82 (21) |
| partial | 77 (4) | 74 (5) |
| failed or abandoned | 54 (3) | 45 (2) |
| unclear | 63 (3) | 84 (4) |

The ordering is sensible, but the groups are tiny.

## B. Per-prompt labels against SWE-chat, by context

| Context | Model | Intent acc | Intent κ | Pushback acc | Pushback κ | Correction recall | Correction precision |
|---|---|---|---|---|---|---|---|
| **L1 prompt only** | Gemma | 73% | 0.68 | 55% | 0.23 | 13% | 88% |
| **L1 prompt only** | DeepSeek | **75%** | **0.71** | 59% | 0.33 | 14% | 88% |
| L3 + previous reply, activity, errors | Gemma | 65% | 0.59 | 56% | 0.24 | 17% | 76% |
| L3 + previous reply, activity, errors | DeepSeek | 65% | 0.59 | 60% | 0.35 | 15% | 89% |
| L4 + previous prompts | Gemma | 60% | 0.54 | 55% | 0.23 | 14% | 73% |
| L4 + previous prompts | DeepSeek | 62% | 0.56 | 59% | 0.34 | 14% | 88% |

- **Intent:** this matches how SWE-chat itself labels intent (from the raw prompt only). Extra context *distracts* the model towards the previous task.
- **Pushback:** when our models flag a correction, it is right 73–89% of the time, but they find only 13–17% of SWE-chat's corrections. The two definitions differ (see A), so this measures definition mismatch as much as model skill.
- **Batching:** one call per prompt removed round 1's turn-count errors entirely (0 failures in 1,512 calls).

## C. Context curve on SWE-chat

The two references agree on SWE-chat at these rates (C6): domain 84%, task 58%, collaboration pattern 71%, outcome 61%, re-explanation 77%.

| Condition | domain | task | collab | outcome | reexpl | tokens/session |
|---|---|---|---|---|---|---|
| C1 user only | 88% | 61% | 84% | 55% | 98% | 577 |
| **C3 compact** | **90%** | **75%** | 82% | **71%** | **100%** | 1,465 |
| C6 full | 90% | 69% | **91%** | 66% | 98% | 34,647 |
| C3H (injected text kept) | 93% | 72% | 87% | 78% | 98% | 2,027 |

n is 18–26 sessions per cell, so differences under about 10 points are noise. Unlike round 1, keeping injected text did not hurt re-explanation on SWE-chat. The injected text there is different in kind, and SWE-chat's re-explanation base rate is low.

## What changes in our understanding

| RQ | After round 2 | Confidence |
|---|---|---|
| RQ1 unit | **Per prompt** for intent-like labels (prompt only). **Per session** for topic, domain, task and outcome. Behaviour counts per session work and are validated externally. | Medium |
| RQ2 context | Per session: the compact view (C3) is enough, confirmed on many people's agent data. Per prompt: the prompt alone is best for intent. | Medium-high |
| RQ3 composition | Unchanged: user text + activity + reply head/tail. Filter injected text (it mattered on round 1 data; not harmful on SWE-chat). | Medium |
| RQ7 measurability | **Holistic categories** (collaboration pattern, outcome category, "handed over") **are not reliably measurable**, even after redefinition. **Observable counts are**, and they agree with external labels. Re-explanation becomes measurable with turn-level evidence. | Medium-high |

**Design implication to evaluate, not yet decided:** report behaviour as counts and rates. For example: "you corrected the agent in 4 of 12 turns" and "you relayed errors 3 times", instead of "your session was task iteration". Derive any summary category from those counts, transparently.

## Limitations

- **The external labels are SWE-chat's model labels,** validated against humans by the SWE-chat authors. They are not our own human labels.
- **Small samples:** 32 SWE-chat sessions. The outcome groups have 2–21 sessions.
- **Coding bias:** Claude Code only for SWE-chat, and the pushback and correction definitions differ between SWE-chat and us.
- **One prompt wording per label.** Paraphrase robustness is still untested.
- **Budget:** about $0.90 of OpenRouter credit remains. Further runs should use free model variants (for example `google/gemma-4-26b-a4b-it:free`), which have daily request limits.

## Suggested round 3

1. **Test whether counts work as a reporting unit.** Check that counts are stable across prompt wordings and models, using free models.
2. **Small human audit (30 sessions):** count corrections, feedback relays and re-explanations by hand. This is cheap because counting is concrete.
3. **Align our correction definition with SWE-chat's,** or adopt their four-way pushback scheme, then re-measure.
4. **More SWE-chat sessions (100+)** to tighten the intervals, especially for outcome.
