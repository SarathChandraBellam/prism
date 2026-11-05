# Research proposal: what context does a model need to understand how people work with AI?

Status: draft v0.1 · 2026-11-05 · Project: Prism · Related: [architecture](../architecture.md), [ADR 0002](../adr/0002-session-level-extraction-from-traces.md) (proposed)

## 1. Summary

Prism aims to give people Reflect-style reports on how they work with AI assistants and agents: topics, task types, how much they delegate, outcomes and friction. Every such report depends on one upstream step: a model reading some slice of a person's activity and labelling it. We do not yet know **which slice, and how much of it, a model needs to label each aspect correctly**. That is especially unclear for agent traces, which are large, noisy and partly machine-generated.

This proposal sets out the research needed to answer that question on broader datasets before any solution is chosen. It covers the questions, the prior work reviewed so far, a small pilot on one user's data, and an analysis plan.

## 2. Background

- **Product inspiration.** Reflect in Claude.ai summarises a user's activity over 1, 3, 6 or 12 months and prompts reflection. Prism aims to offer this as an open, vendor-neutral framework that also covers agent traces.
- **Why context matters.**
  - **Cost:** full agent traces are expensive to feed to a model.
  - **Fit:** some sessions do not fit a context window at all.
  - **Meaning:** the meaning of one user message often depends on what came before ("try now").
  - **Privacy:** every extra piece of context sent to a model is more data exposed.
- **Terminology.**

| Level | Meaning |
|---|---|
| Turn | One user message and the visible reply |
| Trace | One agent run triggered by a turn: model calls, tool calls, subagents, retries |
| Session | All traces in one conversation |
| Segment | Part of a session with one coherent topic |
| Period | All sessions of a person in a reporting window |

## 3. Research questions

| # | Question |
|---|---|
| RQ1 | **Unit.** For each aspect we want to label, which unit gives valid labels: turn, trace, segment or session? |
| RQ2 | **Context amount.** For each aspect, what is the smallest context that matches labels made with full information? |
| RQ3 | **Context composition.** Which parts of a trace carry the signal: user messages, assistant replies, tool calls, tool outputs, errors, reasoning, harness-injected text? Which parts are noise or risk? |
| RQ4 | **Incrementality.** How do labels change as traces arrive over time? How stable is a label built incrementally compared with one built from the whole session? |
| RQ5 | **Model sensitivity.** How much do label quality and cost depend on model size, model family and reasoning ("thinking") behaviour? |
| RQ6 | **Generalisation.** Do the answers to RQ1–RQ5 hold across people, domains (coding and non-coding), platforms (chat apps and agents) and languages? |
| RQ7 | **Measurability.** Which aspects can humans themselves label consistently? An aspect that humans cannot agree on cannot be validated for a model either. |

**Aspects in scope:**
- topic
- domain
- task type
- collaboration pattern (the Economic Index's directive, feedback loop, task iteration, learning, validation)
- outcome
- context re-explanation
- turn-level interaction acts (instruct, relay feedback, correct, refine, ask to explain, request review, approve, re-explain)

**Out of scope:** choosing the production pipeline, the taxonomy design, narration and the UI. Those are decided after this research.

## 4. Prior work reviewed

| Work | What it does | Relevance and gap |
|---|---|---|
| **Clio** (Anthropic, 2024) | Per-conversation facets with a small model (Claude 3 Haiku); k-means plus LLM-built hierarchy; four privacy layers. About $0.0005 per conversation. | The cost assumes **1,000-token conversations**. One label per conversation. No incremental mode. |
| **Anthropic Economic Index** (Handa et al., 2025) | Classifies the whole conversation into five collaboration patterns, grouped as automation and augmentation. 90.7% judged correct on 150 hand-checked cases. | Forces one pattern per conversation ("most frequent"). The validation sample is skewed (conversations with user feedback). A secondary source reports that Claude Code's many API calls get labelled as separate tasks. |
| **How People Use ChatGPT** (OpenAI, NBER 2025) | LLM classifiers on de-identified, sampled messages. | Bounded cost per item. Later moved to uniform message sampling, which changed reported shares: **the unit choice changes the numbers**. A critic reports validation on only 149 conversations (unverified). |
| **Working with AI** (Microsoft, 2025) | Two labels per conversation: user goal and AI action. | The two did not overlap at all in **40%** of conversations. One label may hide the difference. |
| **LangSmith Insights** | Per-trace summaries, clustering, attributes. | For threads, uses only the most recent root run for run-level variables. One-off sampled reports. |
| **Transluce Docent** | Deep agent-transcript analysis: search, rubrics, clustering, counterfactuals. | Built for evals and debugging over full transcripts, not for privacy-first personal reports. |
| **Kura** | Open-source reimplementation of Clio. | Suggests 1,000+ conversations for robust clustering; batch only. |
| **Recursive summarisation** (Wang et al., 2023) | Folds new dialogue into a running summary. | The authors report fabricated facts and error propagation, and evaluated only the final summary. **Drift over many folds is unmeasured.** |
| **Dialogue topic segmentation** (TS-WikiDialog, Def-DTS, segmentation metric critique) | LLM topic-shift detection. | LLMs struggle with segmentation. Reported scores depend heavily on annotation granularity. |
| **LLM annotation reliability** (several studies) | LLM-human agreement compared with human-human agreement. | Agreement ranges from kappa 0.25 (conversation completion on WildChat, even between humans) to about 0.9 (concrete labels). Subjective aspects are hard for humans too. |
| **Debiasing LLM labels** (PPI, DSL) | Combines many LLM labels with a small human-labelled set to get unbiased estimates. | The relevant statistics for population and org views. Guarantees at small sample sizes are debated. |
| **OpenTelemetry GenAI and Claude Code telemetry** | `invoke_agent` spans and `gen_ai.conversation.id`. Claude Code redacts prompts and tool content by default. | Real-world traces may lack content unless users opt in. `/clear` and cloud sessions change session ids. |

Links are in [§13 References](#13-references).

**Gap:** the reviewed work covers conversation-level labelling of chats and analyst-facing trace analysis. None of it measures **how much and which context is needed per aspect, for agent traces, incrementally**. That is the question this proposal targets.

## 5. Pilot findings (one user, Claude Code logs)

**Data:** 33 sessions with 196 traces, from one person's local Claude Code logs. Secrets and emails were redacted before any model call.

**Models** (via OpenRouter):
- cheap: GLM-5.3-flash, Qwen3.7-flash, DeepSeek-v4.1-flash
- reference: GLM-5.3 reading the full trace

**Spend:** about $0.83.

**Caveat:** this is a **single-user, coding-only pilot**. It shows that the questions are real, not what the answers are.

| Finding | Evidence | Bears on |
|---|---|---|
| The compact chat view is **about 7% of trace tokens**: median 1.1k vs 6.9k per session; largest 13k vs 343k. Two sessions exceed 128k tokens in full. | Token measurement, no model | RQ2, RQ3 |
| **48%** of user messages are under 80 characters, and about **31%** look context-dependent ("try now", "done ?", "give me url"). Only 7 of 33 sessions have a single trace. | Heuristic count | RQ1, RQ2 |
| Labelling each trace alone and combining gave the **wrong** collaboration pattern on a checked session (directive instead of task iteration). | One session inspected | RQ1 |
| Turn-act agreement with the reference rose with context: **62%** with the message only, 62% adding agent activity, **70%** adding the previous reply, **72%** adding the previous user turn. In one call the model invented a turn that does not exist. In another, it returned `unclear` for every turn of a 9-turn session. | 6 sessions, 40 turns | RQ2, RQ5 |
| Session collaboration pattern compared with the reference: a cheap model on the whole session matched **3 of 6**. A hand-written mapping from cheap turn acts matched 3 of 6, and from reference turn acts 4 of 6. The act set lacked a "plan or think together" act. **The pattern label is unstable even between models**, which raises the RQ7 question of whether it is reliably measurable. | 6 sessions | RQ1, RQ7 |
| **Harness-injected text** appeared as user turns: skill-loading text, task notifications, pasted config files, tool notes. Models labelled it as human behaviour. | Manual inspection | RQ3 |
| **Reasoning tokens dominated cost**: outputs of 2.5–3k tokens against inputs of 1.5–2k, even with reasoning disabled. Shrinking the input matters less than model choice. | Billing per call | RQ5 |
| Context re-explanation derived from turn acts matched the reference on 5 of 6 sessions. | 6 sessions | RQ1 |

## 6. Datasets for the broader study

All candidates must be checked for licence, consent terms and suitability before use.

| Dataset | Type | Gives us | Limitation |
|---|---|---|---|
| Volunteer Claude Code / agent logs (5–10 people, opt-in) | Real agent sessions | Real human-in-the-loop agent work across people | Needs consent and an internal privacy protocol; mostly coding |
| Our platform's chats and traces (if available) | Real, target population | The population Prism actually serves | Access, consent, and whether redaction is in place |
| WildChat (public, from ChatGPT) | Real chats | Scale, non-coding domains, many languages | Chat only, no tools; older models |
| LMSYS-Chat-1M (public) | Real chats | Scale, multiple models | Chat only; arena-style, short sessions |
| Public agent trajectories (e.g. SWE-agent / OpenHands trajectory sets) | Agent traces | Large, tool-heavy traces | Usually **one instruction and no human in the loop**, so not valid for collaboration patterns. Useful only for RQ3 composition and cost. |
| Synthetic sessions with planted ground truth | Generated | Known answers, for example a planted topic switch or planted re-explanation | Not real behaviour. Only for testing whether the method can detect a signal at all. |

**Sampling:**
- Stratify by session length (traces), tool intensity, domain and platform.
- Oversample long and reopened sessions, because that is where context matters most.

**Target size:** about 300 sessions in total, with at least 60 per stratum where possible, and about 1,500 labelled turns.

## 7. Analysis plan

### 7.1 Ablation matrix

For each aspect, vary the **unit** and the **context**, and keep the model fixed for the main runs:

| Context condition | Contents |
|---|---|
| C0 | Metadata only (counts, timing, tool names) |
| C1 | User messages only |
| C2 | C1 + agent activity summary (tool calls, edits, errors) |
| C3 | C2 + head and tail of assistant replies |
| C4 | C3 + short excerpts of failing tool outputs |
| C5 | C4 + full tool outputs (truncated per item) |
| C6 | Full trace including reasoning |
| ±H | With or without harness-injected text (a separate factor) |

**Units:** turn (with 0, 1 or 2 previous turns), trace, session, segment.

**Incremental conditions:**
- the whole session at once
- trace-by-trace update (fold)
- fold with periodic full re-extraction

### 7.2 Reference labels

- **Human gold:**
  - two annotators on a subset: about 100 sessions and 500 turns
  - a written codebook with examples, piloted on 20 sessions before the main labelling
  - the annotator who owns the data labels where consent allows, because they know their own intent
- **Strong-model reference:** the strongest affordable model reading the full trace (C6), as a secondary reference only. It is **never used as ground truth alone.**

### 7.3 Metrics

1. **Agreement per aspect:** accuracy and Cohen's kappa against human labels, always next to human-human kappa.
2. **Context curve:** agreement against context condition, with the knee point where more context stops helping.
3. **Cost:** input, output and reasoning tokens, and dollars per session and per turn.
4. **Stability:** the same input run twice, and across model families.
5. **Drift:** agreement between fold and whole-session labels against the number of folds.
6. **Distribution shift:** how aggregate shares, such as the share of directive sessions, change by unit and context condition. This is what a user would actually see.
7. **Leakage:** the rate of personal or secret data surviving into model inputs and outputs per context condition.

### 7.4 Statistics

- Bootstrap confidence intervals clustered by person and session, since turns within a session are not independent.
- Pre-register the main comparisons (C1–C6 per aspect, units per aspect) to avoid choosing results after the fact.
- Report per stratum, not only pooled.

### 7.5 Controls

- Filter harness-injected text as an explicit factor (±H), not silently.
- Use the same redaction for all conditions.
- Pin model versions and log prompts and parameters for every call.
- Record and report reasoning-token behaviour per model.

## 8. Privacy and ethics

- Opt-in consent for every non-public dataset, with the right to withdraw.
- Redact secrets and personal data before any model call, and measure that redaction (metric 7).
- Use model providers with no data retention, or local models for sensitive subsets.
- Store no raw transcripts beyond the study window. Keep labels and statistics only.
- Annotators see only consented and redacted data.

## 9. Budget and timeline (rough)

| Phase | Work | Model cost (est.) | Human effort |
|---|---|---|---|
| P0 | Codebook, consent, data pipeline, injected-text filter | – | 2–3 days |
| P1 | Codebook pilot on 20 sessions, plus inter-annotator check | < $2 | ~4 hours (2 people) |
| P2 | Main labelling: ~100 sessions, ~500 turns | – | ~10–12 hours (2 people) |
| P3 | Ablation runs on ~300 sessions × conditions × 2–3 models | $20–60, driven mostly by reasoning tokens | 1–2 days |
| P4 | Analysis and write-up | – | 2–3 days |

## 10. Risks and limitations

- **Coding bias.** Agent data is mostly software work, and findings may not carry over to other domains. Mitigation: WildChat and LMSYS strata, and our platform's data.
- **No human-in-the-loop agent data at scale.** Public trajectories cannot speak to collaboration patterns. Mitigation: volunteer logs.
- **Codebook dependence.** Results depend on the label definitions. Mitigation: pilot and revise the codebook before the main labelling, and report agreement per aspect.
- **Self-labelling bias.** Owners labelling their own sessions may over-read intent. Mitigation: a second annotator on a subset.
- **Model churn.** Cheap models change quickly. Mitigation: pin versions and report findings as context curves that can be re-run.

## 11. Expected outputs

1. A **context requirement table**: for each aspect, the recommended unit and minimal context condition, with agreement and cost.
2. A list of aspects that are **not reliably measurable**, by humans or models.
3. Evidence on incremental labelling: drift curves and when re-extraction is needed.
4. A reusable, open evaluation harness and codebook, so others can rerun this on their own data.

## 12. Decisions needed before P0

1. Which datasets are in scope? In particular: is our platform's data available, and can we recruit volunteers?
2. Who are the annotators, and is self-labelling acceptable?
3. Which model providers are acceptable for private data, or must it run locally?
4. Is the aspect list in §3 complete for what Prism needs to show?

## 13. References

- Clio: Privacy-Preserving Insights into Real-World AI Use, Anthropic, 2024: https://arxiv.org/abs/2412.13678
- Which Economic Tasks are Performed with AI? (Anthropic Economic Index), 2025: https://arxiv.org/abs/2503.04761
- Anthropic Economic Index report 5 summary (secondary, unverified): https://businessdatasolutions.github.io/ai-wiki/sources/2026-05-07-anthropic-economic-index-5-learning-curves
- How People Use ChatGPT, NBER Working Paper 34255, 2025: https://econpapers.repec.org/RePEc:nbr:nberwo:34255
- OpenAI Signals data and methodology: https://openai-dotcom-dun.vercel.app/signals/data-download
- Working with AI: Measuring the Occupational Implications of Generative AI, Microsoft, 2025: https://arxiv.org/abs/2507.07935
- LangSmith Insights: https://docs.langchain.com/langsmith/insights
- Transluce Docent: https://docs.transluce.org/
- Kura: https://github.com/jxnl/kura
- Recursively Summarizing Enables Long-Term Dialogue Memory in LLMs, 2023: https://arxiv.org/abs/2308.15022
- MP2D / TS-WikiDialog, 2024: https://arxiv.org/abs/2403.05814
- Def-DTS, ACL Findings 2025: https://arxiv.org/abs/2505.21033
- Dialogue segmentation evaluation critique, 2025: https://arxiv.org/abs/2512.15042
- StudyChat (LLM vs human agreement): https://arxiv.org/abs/2503.07928
- Longitudinal analyses of LLM conversations in the wild (kappa 0.25 on completion): https://arxiv.org/abs/2605.29018
- Benchmarking debiasing methods for LLM-based estimates: https://arxiv.org/abs/2506.09627
- Can Unconfident LLM Annotations Be Used for Confident Conclusions?: https://arxiv.org/abs/2408.15204
- PPI++ non-asymptotic analysis, ICML 2026: https://icml.cc/virtual/2026/poster/60528
- Claude Code monitoring (OpenTelemetry): https://code.claude.com/docs/en/monitoring-usage
- Honeycomb agent telemetry (`gen_ai.conversation.id`): https://docs.honeycomb.io/send-data/agents
- Reflect in Claude.ai (TechCrunch): https://techcrunch.com/2026/07/09/anthropics-new-claude-feature-is-quietly-selling-you-on-ai/
