# 0004. Prism serves decisions, for the person and for the organisation

- **Status:** proposed
- **Date:** 2026-11-16

## Context

The README lists "being an LLM observability or tracing tool (cost, latency, evals)" as a non-goal. Prism reads traces to understand how people work, not how models perform.

The research did not stay inside that line. [Round 3](../research/agent-trace-study.md) read the same traces twice, once for observability and once for Prism, and found that "the two readings are worth more together": one says who got the worst service, the other says what that person was doing. [Round 4](../research/cross-platform-study.md) asked which seats are unused and which platform does which job best. Those are questions about spend and quality, and they need tokens, errors and outcomes.

A company with several AI tools does not ask for a dashboard of either kind. It asks a small number of questions that end in an action: which seats to pay for, which tool to use for which job, what to build next. Each has an owner. A person asks one more: how do I work with AI?

## Decision

1. **The product is the decision.** Prism produces two things: a personal reflection report, and insight cards for the organisation. A card states a finding, its evidence, an action and an owner ([ADR 0006](0006-insight-card-contract.md)). Prism does not ship a number that no one can act on.
2. **Six decisions define the scope.** They are listed in the [insight catalogue](../insights.md): seats, the work map, tool fit, what to build next, sensitive work, and personal reflection. A seventh needs an ADR.
3. **Prism reads operational facts when a decision needs them.** Tokens, errors, latency and tool calls are trace facts. Prism may use them for a card, for example cost per finished task.
4. **Prism is still not an observability tool.** Three lines separate the two:

   | | Observability tool | Prism |
   |---|---|---|
   | Unit | the request and the trace | the task, the person, the team |
   | Rhythm | live, with alerts | a period: weeks and months |
   | Reader | the engineer who runs the system | the person, and the owner of a decision |

   Prism does not alert, does not debug a single request, and does not run evaluations. It reads the results of evaluations when a source records them ([ADR 0007](0007-outcome-signal.md)).
5. **Reflection over surveillance stays.** Personal reports belong to the person. Cards about people are per role or team, with a minimum group size. Only a seat flag names a holder, because a seat is a licence, not a behaviour.

## Alternatives considered

- **Keep the non-goal as written.** Clean, but rounds 3 and 4 show that the organisation's questions cannot be answered without cost and outcome. Prism would stop at the personal report.
- **Become an observability tool with a people view.** There are many observability tools already. They are built around the request and the engineer. The gap is the layer above: the task, the person and the decision.

## Consequences

- The README non-goal is reworded: Prism is not a live monitoring or evaluation tool, but it reads cost, errors and outcomes when a decision needs them.
- The catalogue becomes the backlog. Work that serves no row in it is out of scope.
- The session is no longer the top unit. Decisions about spend and quality need the task ([ADR 0005](0005-task-as-unit-of-work.md)).
- Prism needs an outcome signal that traces do not carry today ([ADR 0007](0007-outcome-signal.md)).
- The roadmap's phase 3 (organisation insights) depends on these three ADRs.
