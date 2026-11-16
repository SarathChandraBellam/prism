# 0005. The task is the unit of work across sessions and platforms

- **Status:** proposed
- **Date:** 2026-11-16

## Context

[ADR 0002](0002-session-level-extraction-from-traces.md) analyses meaning per session, because a single trace is often meaningless alone. The session has the same weakness one level up. When a tool fails, a person opens another tool and asks again. That is two sessions and one piece of work.

[Round 4](../research/cross-platform-study.md) built such switches into a simulated company with three platforms. [Round 5](../research/decision-study.md) measured what happens to the numbers when the session stays the unit:

- **Adoption is misread.** The chat-only platform had 21% of the sessions (16 of 77) but 11% of the finished tasks (5 of 45). Sessions counted its failures and its use as a fallback as use.
- **Waste is invisible.** 13% of the token cost went to sessions that the person then re-did on another platform. A session view reports that cost as normal use.
- **Cost per session understates the cost of a result.** A verified-correct task cost 2.0 times the cost of a session. On the platform without skills it cost 3.5 times as much.
- **A seat used only as a fallback looks active.** One seat had two sessions and no task start.

The numbers are from simulated users. They show what the unit does to the arithmetic, not how often real people switch.

## Decision

1. **Add the task to the data model.** A task is one piece of work by one person. It is a chain of one or more segments. The segments may be in different sessions and on different platforms.

   | Level | What it is |
   |-------|-----------|
   | Turn, trace, session, segment | As in [architecture.md](../architecture.md#data-model) |
   | **Task** | A chain of segments by one person that pursue the same piece of work |
   | Period | All tasks for a person in a reporting window |

2. **Tasks are linked by rule.** A session continues an earlier one when the same person starts it on another platform soon after, and the first prompts share words or an id. Round 5 used 30 minutes and a word overlap of 0.10. These numbers are a starting point, not a standard.
3. **A link is evidence of the kind `linked`.** By [ADR 0006](0006-insight-card-contract.md) it carries the precision and recall of its rule, measured on a reference set. In round 5 the rule rebuilt 64 of 64 tasks, but every re-ask in that data came within 12 minutes and no person started two similar tasks in a row.
4. **One person has one identity before analysis.** The transformer resolves each platform's user handle, email or employee id to one `user.id` through a directory. Without a directory there are no tasks across platforms, and Prism falls back to sessions.
5. **Each number has one unit:**

   | Question | Count |
   |----------|-------|
   | Is the tool used? | Task starts. A session that continues a task is not a start |
   | Does the tool work? | Tasks that finish on it, and tasks that leave it |
   | What does a result cost? | All sessions of the task, on every platform |
   | How active is a person? | Sessions and turns, as before |

6. **A task has an end state.** It is `finished`, `re-done elsewhere` or `ended on trouble`. The first two come from the links. The third comes from a flag on the last turn (no answer, a failed tool call, or a phrase such as "I can't access"). That flag was right for 9 of its 19 cases in round 5, so numbers that use it are shown as an upper bound.
7. **No new attribute for now.** The conventions have `session.previous_id`, which can link sessions on one platform, but nothing links work across platforms. [ADR 0003](0003-otel-trace-as-base.md) adds an attribute only when an analysis cannot do without it. The rule works on the easy case, so the question stays open until a harder data set says otherwise.

## Alternatives considered

- **Keep the session as the top unit.** Simple and already designed. It gives the wrong answer to every question about spend and quality in a company with more than one tool.
- **Ask sources for a shared task reference.** A join is better than an inference. No source records one today, and people do not file a ticket before they ask a chatbot. Kept as a later option for work that has a natural id, such as a support ticket or a pull request.
- **Let a model decide which sessions belong together.** More flexible than word overlap. It costs a model call per candidate pair and sends more content to a provider. Worth testing only where the rule fails.

## Consequences

- The pipeline gets a linking step after the sessionizer. It needs no model.
- Aggregates for the organisation are defined on tasks. The personal report can use tasks too: "you re-did four tasks on another tool".
- The linking rule needs content: the first prompt of each session. A deployment that records no content has no tasks, only sessions.
- Three cases are untested and must be studied before this ADR is accepted: a retry on the same platform, a task resumed days later, and two similar tasks in a row.
- [ADR 0002](0002-session-level-extraction-from-traces.md) is unchanged. Meaning is still extracted per session or segment. The task is built on top.
