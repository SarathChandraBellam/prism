# Privacy model

> **Status: draft.** The README, the contribution rules and the security policy refer to this document. This draft states the commitments they already make and adds the rules that the organisation view needs ([ADR 0004](adr/0004-scope-organisation-decisions.md), [ADR 0006](adr/0006-insight-card-contract.md)). Nothing here is implemented. The numbers marked *proposal* are open for review.

## Commitments

1. **Excluded sessions leave no record.** A session that is incognito, opted out or restricted by policy is dropped at the source adapter. Prism keeps no record, no count and no summary of it.
2. **Sensitive sessions count, but say nothing.** A session marked sensitive counts towards totals. Its summary is generic and its topics are not kept. Sensitivity only escalates ([ADR 0002](adr/0002-session-level-extraction-from-traces.md)).
3. **Raw content stays out of the reporting layer.** Aggregates, cards and reports are built from records and trace facts. No prompt, reply or tool result is copied into them.
4. **The personal report belongs to the person.** Nobody else can read it, and the organisation view is not built from it.
5. **The organisation view is about groups.** It is aggregated by design. There is no setting that turns it into a view of one person.
6. **Deletion at the source is followed.** A deleted or newly excluded session tombstones its record and leaves future aggregates.
7. **No ranking of people.** Prism does not score, rank or compare individuals.

## Who sees what

| Data | Holds | Pipeline | The person | Decision owners |
|------|-------|----------|-----------|-----------------|
| Spans with content | Prompts, replies, tool arguments and results | reads, does not copy onward | no (they have the source tool) | no |
| Trace facts | Counts, tokens, errors, timing, tool names | yes | their own, in the report | no |
| Session and task records | Labels, a one-line summary, links between sessions | yes | their own | no |
| Aggregates | Numbers per person and per group | yes | their own | groups only |
| Personal report | Narrative for one person | writes | yes | no |
| Insight cards | Finding, evidence, action, owner | writes | no | yes |

## Content

The OpenTelemetry conventions record no content by default. A source must opt in. Prism reads content in three places only:

- the user's message and the visible reply of each turn, for labels and for linking a re-ask to its first session;
- tool names and one line per tool call, never tool results, for the compact view;
- nothing from system prompts, skill bodies or retrieved documents.

A deployment may record no content at all. It then gets the decisions that rest on counted evidence only. [Round 5](research/decision-study.md) lists which decisions survive.

Content that goes to a model for labelling goes as the compact view, with a token budget ([ADR 0002](adr/0002-session-level-extraction-from-traces.md)). A deployment can use a local model so that no content leaves its infrastructure.

## Rules for the organisation view

1. **Minimum group size.** A number about people is shown only when at least 5 people are behind it (*proposal*). The count is of people, not of sessions or tasks.
2. **Small cells.** When one cell of a table is hidden, the next smallest is hidden too if the hidden value could be worked out from the total.
3. **Named people.** A card names a person in one case only: the holder of a seat on a seat card. A seat is a licence. The card goes to the owner of licences, and its action is to ask the holder, not to cancel.
4. **No quotes.** A card carries numbers and group names. It carries no prompt text, no summary of one session and no example taken from one person.
5. **Outcomes are about tools.** Checked answers and failure rates are reported per platform, task type or capability. They are not reported per person in the organisation view.
6. **Identity.** Joining a person's sessions across platforms needs one identity per person. The directory that provides it stays inside the pipeline. Outputs carry groups.

The simulated company in rounds 4 and 5 has four people per role. That is below the proposed minimum. Its per-role cards show what a card looks like. They would not be shown under this model.

## Open questions

- Is 5 the right minimum, and should it grow for sensitive breakdowns such as domain by team?
- Does a seat card need the holder's consent, or only notice?
- Should the personal report show what the organisation view counted about the person?
- How long are records kept after the reporting window closes?
- Role-based access and the audit log for the organisation view (roadmap phase 3).
