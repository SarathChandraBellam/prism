# 0001. Record architecture decisions

- **Status:** accepted
- **Date:** 2026-11-05

## Context

Prism is designed in the open, and contributors need to understand why the project made the choices it did, not just what those choices were.

## Decision

Significant decisions are recorded as Architecture Decision Records (ADRs) in `docs/adr/`, numbered sequentially (`NNNN-short-title.md`). Each ADR states its context, the decision and its consequences. To propose a decision, open a pull request that adds an ADR with status `proposed`. It becomes `accepted` when merged after review. An accepted ADR is never edited to reverse it; a new ADR supersedes it instead.

## Consequences

- Design discussions have a durable home that is easy to review.
- The open questions in [architecture.md](../architecture.md#open-questions) will each be closed by an ADR.
