# Prism

**See how you and your organization actually work with AI.**

An open-source, vendor-neutral framework for Reflect-style reports, inspired by Reflect in Claude.ai, that works on both assistant chats and agent traces.

Prism turns AI assistant chats and agent traces into periodic, privacy-preserving reflection reports. It breaks your work with the assistant down into topics, task types, time patterns and how much of it is delegated, then writes a short narrative with reflective questions and concrete suggestions for working better.

For an organisation with several AI tools, Prism turns the same traces into a small set of **insight cards**. Each card answers a decision that has an owner: which seats to pay for, which tool to use for which job, what to build next. Each card says how far it can be trusted.

> **Status: design phase.** There is no code yet. This repository currently holds the project's intent, architecture and privacy model. Feedback on the design is the most valuable contribution right now. See [Contributing](#contributing).

## Why

Teams are rolling out AI assistants quickly, but nobody can easily see how they are used:

- **Individuals** cannot see their own patterns: what they delegate, where they keep re-explaining context, which habits pay off.
- **Organizations** cannot see adoption beyond raw seat counts and message volume, and existing tools are tied to a single vendor.
- **Platform builders** have no reusable, privacy-aware way to offer this to their own users.

Prism is meant to be the open, vendor-neutral, self-hostable layer for this.

## How it works

```
 chats and ──▶ 0. Sessionize ──▶ 1. Extract ──▶ 2. Normalize ──▶ 3. Aggregate ──▶ 4. Narrate ──▶ report
 agent traces  group traces,     one record     stable topic     plain SQL         one LLM call
 (adapters)    count facts       per session    categories       over records      over aggregates
               (no LLM)          (small model)
```

0. **Sessionize.** Traces are grouped into sessions (conversations). Structural facts such as tool calls, subagents, tokens, latency and retries are read straight from the trace, with no LLM.
1. **Extract.** When a session goes idle, a small model writes one structured record: topics, domain, task type, collaboration mode (delegate / co-create / think-partner / lookup), outcome, whether context was re-explained, a one-line summary and sensitivity. Long sessions are split into topic segments. The model reads a compact **chat view** (user messages, short replies and one line per tool call), never the full trace, so cost stays low and nothing overflows the context window. When a re-opened session gets new traces, they are **folded** into the existing record instead of re-analysing everything.
2. **Normalize.** Free-text topics are mapped to stable categories so that reports stay comparable over time.
3. **Aggregate.** All numbers are computed deterministically in SQL: topic mix, hour-by-weekday heatmap, session depth, delegation ratio, agent usage, streaks and change since the previous period. A reporting window (1, 3, 6 or 12 months) is just a filter.
4. **Narrate.** One LLM call receives the aggregates and a few example summaries, plus optional user context, and writes the report. **The model interprets numbers; it never computes them.**

See [docs/architecture.md](docs/architecture.md) for details.

## Decisions for the organisation

Prism serves six decisions. They are listed in the [insight catalogue](docs/insights.md) with their owners, the trace attributes they read and the evidence they need.

| Decision | Owner |
|----------|-------|
| Which seats do we pay for? | finance |
| What work goes to AI? | leadership |
| Which tool for which job? | platform owner |
| What do we build next: skills, connectors, context? | enablement |
| Where does sensitive work go? | security |
| How do I work with AI? | the individual |

An insight card states a finding, its evidence, an action and an owner. It also states what kind of evidence it rests on (counted, linked, labelled or checked), the measured error of that evidence, and whether to act, check first or watch ([ADR 0006](docs/adr/0006-insight-card-contract.md)). The [decision study](docs/research/decision-study.md) tested them on simulated data: four in depth, while "sensitive work" is blocked for want of a label and the personal report was studied in earlier rounds.

## Principles

- **Privacy is applied at extraction.** Excluded chats (incognito, opted out, policy-restricted) produce no record. Sensitive chats count towards totals but keep only a generic summary. Raw transcripts never reach the reporting layer. See [docs/privacy.md](docs/privacy.md).
- **Deterministic numbers, generative narrative.** Every figure in a report can be reproduced from the records with SQL.
- **Bring your own everything.** Pluggable chat-source adapters, pluggable LLM providers (including local models) and storage you control.
- **Self-hostable first.** Data never needs to leave your infrastructure.
- **Reflection over surveillance.** Individual reports belong to the individual. Organization views are aggregated and anonymized by design, not by configuration.

## Non-goals

- Monitoring or ranking individual employees.
- Storing or re-serving raw chat transcripts.
- Being a live monitoring, debugging or evaluation tool. Prism does not alert, does not debug a single request and does not run evaluations. It reads cost, errors and the results of evaluations from traces when a decision needs them ([ADR 0004](docs/adr/0004-scope-organisation-decisions.md)).
- Being tied to any single AI vendor.

## Roadmap

| Phase | Scope |
|-------|-------|
| **0. Design** *(now)* | Intent, architecture, privacy model, extraction schema, aggregate definitions |
| **1. Personal reports** | Core pipeline, record schema, a reference chat adapter and an OpenTelemetry GenAI trace adapter, CLI to generate a report |
| **2. Embeddable** | Library and API for platforms to offer Prism reports to their own users |
| **3. Organization insights** | Insight cards for the six decisions, built on tasks and a small sample of checked answers, with minimum-group thresholds, RBAC and audit log |
| **Later** | Topic graph showing how interests connect and evolve over time |

Open design questions are tracked in [docs/architecture.md](docs/architecture.md#open-questions) and as GitHub issues.

## Contributing

Contributions are welcome, especially reviews of the design docs at this stage. Read [CONTRIBUTING.md](CONTRIBUTING.md) first. Significant design decisions are recorded as [ADRs](docs/adr/).

Everyone taking part must follow the [Code of Conduct](CODE_OF_CONDUCT.md). To report a security or privacy issue, follow [SECURITY.md](SECURITY.md) and do not open a public issue.

## License

[Apache License 2.0](LICENSE).
