# Privacy model

> Status: draft. These are design commitments that the implementation must satisfy.

Prism processes some of the most sensitive data an organization has: what people ask their AI assistant. Privacy is therefore part of the architecture, not a setting.

## Commitments

1. **Exclusion happens at the source.** Chats that are incognito, opted out or restricted by policy produce no record at all. They are not stored and then hidden later.
2. **Records, not transcripts.** After extraction, the pipeline holds only structured records. Raw transcripts and traces are never stored by Prism and never sent to the narrator. The extractor sees only a compact chat view: tool outputs, file contents and retrieved documents are dropped before any model call.
3. **Sensitive chats are minimized.** A chat flagged as sensitive still counts towards totals, but its summary is replaced with a generic one and its topics are coarsened. Sensitivity only escalates: when later traces are folded into a session, it can become more sensitive, never less.
4. **Personal reports belong to the person.** An individual's report is visible only to that individual by default.
5. **Organization views are aggregate-only.** Team and org views never show individual records or individual-level breakdowns, and groups below a minimum size are suppressed.
6. **You choose where data goes.** Every model call can go to a provider you choose, including a local model. Prism adds no telemetry.
7. **Retention is bounded.** Records have a configurable retention period. Deleting or excluding a chat at the source must tombstone its record and remove it from future aggregates.

## Threats considered

| Threat | Mitigation |
|--------|-----------|
| Sensitive content leaking into reports | Sensitivity flag at extraction; generic summaries; narrator sees aggregates only |
| Re-identifying individuals in org views | Minimum group size; small-cell suppression; no per-person drill-down |
| Use as an employee-monitoring tool | Aggregate-only org views by design; this is documented as a non-goal |
| Prompt injection from chat content into the narrator | Narrator receives structured aggregates, not transcripts |
| Prompt injection or secrets in tool outputs reaching the extractor | Chat view drops tool outputs, file bodies and retrieved documents |
| Data sent to third-party model providers | Pluggable providers, including local models; no default external endpoint |

## Reporting issues

If you find a way to break any of these commitments, report it privately as described in [SECURITY.md](../SECURITY.md).
