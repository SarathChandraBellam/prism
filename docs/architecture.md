# Architecture

> Status: draft. This describes the intended design. Nothing here is implemented yet.

## Overview

Prism is a five-stage pipeline. Each stage has a narrow contract, so stages can be tested, replaced or run on different schedules independently.

```
 ┌──────────┐   ┌────────────┐   ┌───────────┐   ┌────────────┐   ┌────────────┐   ┌──────────┐
 │ Source   │──▶│ Sessionizer│──▶│ Extractor │──▶│ Normalizer │──▶│ Aggregator │──▶│ Narrator │──▶ Report
 │ adapters │   │ + facts    │   │ (small    │   │ (topic →   │   │ (SQL over  │   │ (one LLM │
 │          │   │ (no LLM)   │   │  model)   │   │  category) │   │  records)  │   │  call)   │
 └──────────┘   └────────────┘   └───────────┘   └────────────┘   └────────────┘   └──────────┘
  chats and      sessions,        session          normalized       aggregates       narrative
  agent traces   trace facts      records          records
```

Prism works on plain assistant chats and on agent traces (runs with tool calls, subagents and retries). Both are reduced to the same session-level records. The design choices are recorded in [ADR 0002](adr/0002-session-level-extraction-from-traces.md).

## Data model

| Level | What it is | Typical source |
|-------|-----------|----------------|
| **Turn** | One user message and the visible reply | chat UI, export |
| **Trace** | One agent run triggered by a turn: model calls, tool calls, subagents, retries | OpenTelemetry span tree (`invoke_agent` root) |
| **Session** | All turns and traces in one conversation or thread | `gen_ai.conversation.id`, or the platform's thread id |
| **Segment** | A part of a session with one coherent topic and its own time range | created by the extractor |
| **Period** | All segments for a person in a reporting window | report filter |

A plain chat is a session whose traces have no tool calls. **Meaning is analysed per session.** A single trace is often not meaningful alone ("now fix the test"), and treating each trace or model call as a separate task inflates task counts and skews delegation figures. **Behaviour is counted per trace**, from structure alone.

## Components

### Source adapters

They read chats or traces from wherever they live, such as a platform database, an export file, an API or an OpenTelemetry collector. They emit a common `Session` shape: an ordered list of traces, each with turns, spans (model and tool calls), timestamps and exclusion flags. Adapters are the main extension point for supporting new platforms. An OpenTelemetry GenAI adapter is planned as the vendor-neutral default for agent traces.

### Sessionizer and trace facts

This stage needs no LLM. It groups traces into sessions and records **trace facts** straight from the spans:

- start and end time, duration, latency
- model calls, tokens in and out
- tool calls by name and status, errors, retries
- subagents spawned, delegation depth
- files or artifacts touched (names and counts only)

Trace facts are appended as traces arrive and are never model-generated. If a source has no session id, the sessionizer groups by user and an inactivity gap.

### Extractor

It turns a session into a **session record** with one or more segments.

**Input: the chat view.** The model never reads the full trace. Agent traces are usually far larger than chats because of tool outputs, file contents, retrieved documents and repeated context. Full traces are costly and often do not fit the context window. The extractor builds a compact chat view:

| Kept | Dropped |
|------|---------|
| user messages in full | tool outputs and file bodies |
| final assistant reply per trace, head and tail truncated | retrieved documents |
| one line per tool call, e.g. `tool=search status=ok out=12KB` | system, skill and memory prompts |
| | reasoning and intermediate model calls |

Each extraction has a hard token budget. A session over budget is processed in chunks with the fold step below, so any length works.

**When it runs.** Extraction is debounced. It runs when a session has been idle for a configurable time (default proposal: 30 minutes), plus a periodic sweep for anything missed. Most sessions are therefore extracted exactly once.

**Late traces: fold, don't redo.** When new traces arrive for a session that already has a record (a re-opened chat), the extractor folds them in:

```
record v(n+1) = extract(record v(n), chat view of traces after the watermark)
```

- The **watermark** is the last trace already folded. It makes folding idempotent and safe to retry.
- Records are versioned. Aggregates read the latest version.
- If the new traces change topic, the current segment closes and a new segment opens.
- To control drift, sessions that fit the budget are occasionally re-extracted in full and compared with the folded record. The same comparison serves as an evaluation of the fold.

**Output: session record.**

| Field | Source | Notes |
|-------|--------|-------|
| `session_id`, `watermark`, `version` | pipeline | |
| `segments[]` | model | each segment carries the fields below |
| `segment.started_at`, `segment.ended_at` | trace facts | never model-generated |
| `segment.topics` | model | free text, normalized later |
| `segment.domain` | model | e.g. engineering, writing, analysis |
| `segment.task_type` | model | e.g. debug, draft, research, plan |
| `segment.collaboration_mode` | model | `delegate` / `co-create` / `think-partner` / `lookup` (mapping to published taxonomies is an open question) |
| `segment.outcome` | model | e.g. resolved, abandoned, ongoing |
| `segment.context_reexplained` | model | did the user repeat context the assistant should have known? |
| `segment.summary` | model | one line; generic for sensitive sessions |
| `sensitivity` | model + policy | session-wide; only ever escalates |

The exact schema and enumerations will be fixed in an ADR before implementation.

### Normalizer

It maps free-text topics to stable categories so that reports can be compared across periods. Candidate approaches are a fixed taxonomy, clustering (as in Clio: embeddings, k-means and an LLM-built hierarchy), or a hybrid (see open questions).

### Aggregator

It holds deterministic SQL definitions over normalized records and trace facts:

- topic and domain mix
- hour × weekday activity heatmap
- session depth (turns, traces and duration distribution)
- delegation ratio by collaboration mode
- agent usage: tool calls, subagents and delegation depth per session
- context re-explanation rate
- streaks and active days
- change versus the previous period of equal length

A reporting window is a filter on segment and trace timestamps, not on session start, so a session that spans a period boundary is split correctly. Reports already delivered are snapshots and are not rewritten when late traces arrive. Aggregates are the only data the narrator sees, apart from a few sampled summaries.

### Narrator

A single LLM call receives the aggregates, a handful of example summaries and optional user context. It returns:

- a short narrative of the period
- two or three reflective questions
- concrete workflow suggestions

It must not introduce numbers that are not present in the aggregates. Output is validated against this rule.

## Cost model

| Step | LLM | Cost driver |
|------|-----|-------------|
| Sessionizer and trace facts | none | free |
| Extraction | small model | chat-view tokens of new traces only, capped per call |
| Normalization | optional | per new topic string, cached |
| Aggregation | none | SQL |
| Narration | one call per report | aggregates and a few summaries |

Clio reports about $0.0005 per conversation for facet extraction, but assumes conversations of about 1,000 tokens. The chat view and the fold step are what keep agent sessions close to that budget. The fixed extraction prompt should be cached, and periodic sweeps can use provider batch APIs.

## Prior art

- **Reflect in Claude.ai** is the product inspiration: a personal summary of a user's activity over 1, 3, 6 or 12 months with prompts to reflect. Prism aims to offer the same idea as an open, vendor-neutral, self-hostable framework that also covers agent traces.
- **Clio** (Anthropic, 2024, [arXiv:2412.13678](https://arxiv.org/abs/2412.13678)) is the reference for privacy-preserving facet extraction, clustering and its privacy layers. It describes no incremental mode, which Prism adds with folding.
- **The Anthropic Economic Index** ([arXiv:2503.04761](https://arxiv.org/abs/2503.04761)) classifies collaboration patterns as automation or augmentation. It is a candidate reference taxonomy for `collaboration_mode`.
- **OpenTelemetry GenAI semantic conventions** provide the vendor-neutral trace shape (`invoke_agent` spans, `gen_ai.conversation.id`).

## Deployment shapes

1. **CLI.** Point it at an export or trace dump and get a personal report.
2. **Library.** Embed it in a platform and feed it chat-idle or trace events.
3. **Service.** Self-hosted, with an org-level aggregated view (phase 3).

## Open questions

Proposed answers are in [ADR 0002](adr/0002-session-level-extraction-from-traces.md) (status: proposed):

- **Extraction trigger:** idle debounce plus a periodic sweep.
- **Topic drift:** one session record with segments.
- **Re-opened chats:** fold into the existing record; add a segment if the topic changes.

Still open:

- **Chat view fidelity:** what share of trace tokens does it keep, and does it give the same facets as the full trace? (spike)
- **Fold drift:** how far does a folded record drift from full re-extraction, and after how many folds?
- **Collaboration taxonomy:** keep Prism's four modes, map them to the Economic Index taxonomy, or adopt that taxonomy?
- **Taxonomy:** fixed, clustered, or hybrid?
- **Sessions without ids:** what inactivity gap defines a session?
- **Org thresholds:** what is the minimum group size for organization views, and how is small-cell suppression handled?
- **Implementation language** and storage backend.

Each will be resolved through an [ADR](adr/).
