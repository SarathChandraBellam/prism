# Research proposal: what context does a model need to understand how people work with AI?

Status: draft v0.1 · 2026-11-05 · **Results: [round 1](context-study-round1.md), [round 2](context-study-round2.md)** · Project: Prism · Related: [architecture](../architecture.md), [ADR 0002](../adr/0002-session-level-extraction-from-traces.md) (proposed)

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
| **SWE-chat** (Baumann et al., COLM 2026) | About 18k real, opt-in coding-agent sessions (69% Claude Code) with LLM labels validated against human expert gold labels: prompt intent, pushback, user persona, session success. | **Chooses context per label**: prompt intent from the raw prompt alone; pushback from the full transcript before the prompt; success from the full conversation plus a tool-call summary. That is an existence proof for RQ2, but the choices are not compared systematically. |
| **How Coding Agents Fail Their Users** (2026) | Misalignment episodes in 20,574 sessions (SpecStory and SWE-chat), labelled with GPT-5.4. | **User turns kept in full; agent turns head-tail truncated** at 5,000 characters per turn in short sessions down to 500 in very long ones, which is close to our chat view. Two humans agreed on 83% of 100 records; the LLM judge reached 81% accuracy. |
| **Programming by Chat** (2026) | Behavioural analysis of 11,579 IDE sessions (Cursor, Copilot via SpecStory). | Kept **only user messages**, a C1-style condition. |
| **OpenTelemetry GenAI and Claude Code telemetry** | `invoke_agent` spans and `gen_ai.conversation.id`. Claude Code redacts prompts and tool content by default. | Real-world traces may lack content unless users opt in. `/clear` and cloud sessions change session ids. |

Links are in [§13 References](#13-references).

**Gap:** the reviewed work labels chats per conversation, and recent agent studies (SWE-chat, the misalignment study) each pick a context per label by judgement. None of them measures **how much and which context is needed per aspect, for agent traces, incrementally**. That is the question this proposal targets.

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
| Reasoning tokens appeared to dominate cost: outputs of 2.5–3k tokens against inputs of 1.5–2k. **Corrected in round 1:** this was mostly a configuration error. `reasoning: {enabled: false}` was not honoured; `effort: none` brought reasoning tokens to about 0 for six of seven models. | Billing per call | RQ5 |
| Context re-explanation derived from turn acts matched the reference on 5 of 6 sessions. | 6 sessions | RQ1 |

## 6. Datasets for the broader study

Decision (2026-11-07): use open datasets only. No platform data or volunteer logs in this phase. All licences and terms must be accepted before download.

| Dataset | Type | Gives us | Limitation |
|---|---|---|---|
| **SWE-chat v2** (SALT-NLP, Hugging Face, ODC-BY, gated: accept terms while logged in) | ~18k real coding-agent sessions, ~230k user prompts; Claude Code, Codex, Gemini CLI, Cursor and others | **Primary dataset.** Full raw transcripts with tool calls, tool results (truncated to 10 KB), reasoning blocks, timestamps and session ids. Also LLM labels validated against human gold: prompt intent, pushback, persona, success. PII and secrets scrubbed (Presidio, TruffleHog). | Coding only. Early adopters of one logging tool, from public repositories. 47 GB in total, so sample it. |
| **How Coding Agents Fail Their Users replication package** (GitHub) | Human-validated misalignment episodes | A second external reference for labels that need the whole session | Raw traces not redistributed; episodes only from permissively licensed repositories |
| **DataClaw Claude Code conversations** (Hugging Face) | 549 sessions, 14 projects, one person | A second single-user corpus to compare with the pilot | One person; check licence and scrubbing |
| **WildChat-4.8M** (AllenAI, Hugging Face, ODC-BY, non-toxic version not gated) | Real ChatGPT conversations | The non-coding and multilingual stratum (RQ6) | Chat only, no tools |
| **LMSYS-Chat-1M** | Real chats across many models | A second chat stratum | Chat only; arena-style, short sessions |
| Synthetic sessions with planted ground truth | Generated | Known answers, for example a planted topic switch or planted re-explanation | Not real behaviour. Only for testing whether the method can detect a signal at all. |

Public agent benchmark trajectories (such as SWE-agent or OpenHands runs) are excluded. They have one instruction and no human in the loop, so they cannot inform collaboration patterns.

**Sampling:**
- **SWE-chat:** stratify by agent, session length (traces), tool intensity, and coding mode (human-only, collaborative or vibe coding).
- **WildChat:** stratify by domain and language.
- **Oversample** long and reopened sessions, because that is where context matters most.

**Target size:** about 300 sessions from SWE-chat and 200 from WildChat for the ablations.

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

Two different questions need two kinds of reference:

1. **Information loss** (RQ2–RQ5): does a smaller or cheaper context give the same label as full context? A **model reference** is enough here, because the question is relative: the strongest affordable model on the full trace (C6), cross-checked by a second model family.
2. **Validity** (RQ7): is the label actually right? Model references cannot answer this. All models may share the same blind spot; in the pilot, models disagreed on collaboration pattern in half the sessions, and nothing says which was right. This needs **human-validated labels**. We reuse existing ones before making new ones:
   - **SWE-chat's labels:** prompt intent, pushback, persona and success, which the authors validated against human expert gold labels. Their human gold set is requested from the authors if it is not in the release.
   - **The misalignment study's** human-validated episodes.
   - **A small new human audit only for aspects nobody has validated,** mainly collaboration pattern and context re-explanation: about 30–50 sessions, labelled by one person with a codebook, and a second person on 20 of them if possible.

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
- Use OpenRouter with no-retention routing (`data_collection: deny`). Approved for this study on 2026-11-07. Local models remain an option.
- Store no raw transcripts beyond the study window. Keep labels and statistics only.
- Annotators see only consented and redacted data.

## 9. Budget and timeline (rough)

| Phase | Work | Model cost (est.) | Human effort |
|---|---|---|---|
| P0 | Data pipeline for SWE-chat and WildChat, injected-text filter | – | 2–3 days |
| P1 | Download a SWE-chat sample; check SWE-chat labels and gold availability; codebook for unvalidated aspects | < $2 | ~1 hour |
| P2 | Small human audit: 30–50 sessions for collaboration pattern and re-explanation | – | ~2–3 hours (1 person, +1 on 20 sessions if possible) |
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

## 12. Decisions

| # | Decision | Status |
|---|---|---|
| 1 | Datasets | **Decided 2026-11-07:** open datasets only, with SWE-chat as primary (§6) |
| 2 | Annotators | **Decided 2026-11-07:** reuse existing human-validated labels; small new audit only for unvalidated aspects (§7.2) |
| 3 | Providers | **Decided 2026-11-07:** OpenRouter with no-retention routing |
| 4 | Aspect list (§3) complete for what Prism needs to show? | Open |
| 5 | Accept SWE-chat's gated terms on Hugging Face (needs the project owner's account) | Open |

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
- SWE-chat: Coding Agent Interactions From Real Users in the Wild, COLM 2026: https://arxiv.org/abs/2604.20779 · dataset: https://huggingface.co/datasets/SALT-NLP/SWE-chat
- How Coding Agents Fail Their Users, 2026: https://arxiv.org/abs/2605.29442
- Programming by Chat, 2026: https://arxiv.org/abs/2604.00436
- DataClaw Claude Code conversations (mirror): https://huggingface.co/datasets/Codingxx/dataclaw-peteromallet
- WildChat-4.8M: https://huggingface.co/datasets/allenai/WildChat-4.8M
- Reflect in Claude.ai (TechCrunch): https://techcrunch.com/2026/07/09/anthropics-new-claude-feature-is-quietly-selling-you-on-ai/
