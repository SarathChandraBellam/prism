# 0002. Session-level extraction from chats and agent traces

- **Status:** proposed
- **Date:** 2026-11-05
- **Blocked on:** the [context study](../research/context-study-proposal.md) (RQ1–RQ5). This ADR is not accepted until the study reports, and it may be superseded.

## Context

Prism must report on how people work with AI assistants, and increasingly that work happens through agents. An agent session is not a short chat. Each user turn starts a trace with many model calls, tool calls, subagents and retries. This raises four problems:

1. **Unit of analysis.** A single trace is often meaningless alone ("now fix the test"). Treating each trace or model call as a task inflates task counts and skews delegation figures.
2. **Cost and size.** Sending whole traces to an LLM is costly and often exceeds the context window. Clio's published cost of about $0.0005 per conversation assumes conversations of about 1,000 tokens. Agent traces are typically much larger, mostly because of tool outputs and file contents.
3. **Late traces.** Sessions are re-opened after they have been analysed. Re-analysing the whole session each time grows quadratically with session length.
4. **Topic drift.** Long sessions move between topics, and a single record hides that.

## Decision

1. **Analyse meaning per session. Count behaviour per trace.** Structural facts (tool calls, tokens, latency, retries, subagents) are read from spans without an LLM. Semantic facets (topic, task type, collaboration mode, outcome) are extracted per session.
2. **The extractor reads a chat view, never the full trace.** It keeps user messages, truncated final replies and one line per tool call. It drops tool outputs, file bodies, retrieved documents, system prompts and intermediate model calls. Each call has a hard token budget.
3. **Debounce extraction.** Extract when a session goes idle, plus a periodic sweep.
4. **Fold late traces.** New traces are merged into the existing record with `extract(previous record, chat view of new traces)`. A watermark makes this idempotent, and records are versioned.
5. **Segments.** A session record holds one or more segments, each with its own topic and time range. A topic change during folding opens a new segment.
6. **Periods use segment and trace timestamps.** Delivered reports are snapshots and are not rewritten.
7. **Sensitivity only escalates.** Exclusion or deletion at the source tombstones the record and removes it from future aggregates.

## Alternatives considered

- **Extract per trace and roll up in SQL.** Cheap, but traces lack context, and drift and outcome are only visible across traces. Kept only for structural facts.
- **Re-extract the whole session on every change.** Simple and drift-free, but cost grows with session length and re-opened sessions are paid for repeatedly. Kept only as a periodic drift check for sessions within budget.
- **Full traces with a long-context model.** Highest fidelity, but expensive, still bounded by the context window, and it sends more sensitive content to the model provider.

## Pilot evidence (2026-11-05)

A pilot on one person's Claude Code logs (33 sessions, 196 traces) gave mixed evidence. It is far too small to decide anything:

- **Supports decision 1:** about 31% of user messages are meaningless alone, and labelling traces separately mislabelled a checked session.
- **Supports decision 2 on cost:** the chat view is about 7% of trace tokens. Its accuracy is not yet validated.
- **Weakens decision 1's session-level labelling:** a cheap model matched the reference on collaboration pattern in only 3 of 6 sessions. Labelling each turn and computing session patterns in SQL is a candidate alternative.
- **Untested:** decisions 3–5 (debounce, fold, segments).

## Consequences

- Extraction cost scales with new user-facing content, not with trace size.
- Less raw content reaches model providers, which supports the [privacy model](../privacy.md).
- Folding can drift. The chat view's fidelity and the fold's drift must be measured on a labelled sample before this ADR is accepted.
- Adapters must supply a session id or let the sessionizer infer sessions from an inactivity gap.
