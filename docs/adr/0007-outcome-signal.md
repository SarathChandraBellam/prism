# 0007. The outcome signal is a small sample of checked answers

- **Status:** proposed
- **Date:** 2026-11-16

## Context

The decision "which tool for which job" needs to know whether an answer was right. A trace says what happened: which model ran, which tools it called, what failed. It does not say whether the result was correct.

[Round 4](../research/cross-platform-study.md) tried to stand in for correctness with signals from the trace. A composite of five of them did not rank platforms as the checks did. [Round 5](../research/decision-study.md) measured why, turn by turn, on 134 checked turns:

- **Half of the wrong answers are silent.** 19 of 37 turns that failed a check show no failed tool call, no empty reply and no inability phrase (51%, interval 36% to 67%). On the platform without skills it was 10 of 15.
- **A failed tool call is not a failed answer.** It marked a wrong answer in 4 of 18 turns. Agents retry and recover.
- **An explicit "I can't" is reliable but rare.** It marked a wrong answer in 11 of 13 turns, and found 11 of the 37 failures.
- **No trace signal finds most failing sessions.** The best one found 22 of 37, with 11 false alarms.
- **No outcome reaches the traces today.** The conventions define a `gen_ai.evaluation.result` event. It was on 0 of 1,062 spans.

Round 5 also measured what real checks would cost:

- **A platform-level choice is cheap.** With 10 checked turns per platform, the best platform was picked in 96% of simulated samples. That is 30 checks for a period.
- **A choice per task type is not.** It needs about 10 checks per platform and task type, 210 in all. Two weeks of use produced 134 checkable turns, and 16 of 21 cells had fewer than 10. Cells fill by habit: a platform that few people use for a job gets few turns for it, however long the window.
- **Small cells support little.** With every script run on every platform, 7 of 21 comparisons inside a task type held up.

## Decision

1. **Prism reads outcomes. It does not create them.** An outcome arrives as a `gen_ai.evaluation.result` event on the span it judges, as the conventions define it. A person or an evaluator outside Prism makes it. This keeps [ADR 0004](0004-scope-organisation-decisions.md): Prism runs no evaluations.
2. **The default outcome signal is a random sample.** Each period, a random sample of turns per platform is checked. The starting size is 10 per platform. A card states the sample size and the interval ([ADR 0006](0006-insight-card-contract.md), basis `checked`).
3. **Trace signals are not outcomes.** Prism does not rank platforms by error rates, empty replies or abandonment flags. It uses these signals for two things only:
   - **Where to look first.** A flagged turn failed about twice as often as an average one, so a reviewer finds more per check there. A rate comes from the random sample, never from flagged turns.
   - **What is missing.** An inability phrase says the tool could not reach something. That feeds the decision "what do we build next", not the quality ranking.
4. **A failed tool call is a cost, not a verdict.** It counts towards rework and latency. It is not a sign of a wrong answer.
5. **Routing by task type needs a planned test set.** The same tasks are run on each platform and checked. Normal use cannot fill the cells. Until such a set exists, a card on routing by task type says `watch`.
6. **Comparisons use the task as the unit.** Turns in one task are not independent. An interval is computed over tasks or test scripts.
7. **One sample, three uses.** The checked sample also measures the error of the linking rule ([ADR 0005](0005-task-as-unit-of-work.md)) and the agreement of the labels. Prism needs one reference set per period, not three.
8. **Outcomes are about tools.** A checked answer is reported per platform, task type or capability. It is not reported per person in the organisation view. The sample excludes excluded and sensitive sessions, and the checker's access to content follows the [privacy model](../privacy.md).

## Alternatives considered

- **Use trace proxies as the quality signal.** Free and always available. They miss half of the failures and penalise platforms that have tools, because only those can show tool errors.
- **Ask users to rate answers.** A thumbs-down is an outcome, and Prism should read it when a source records it. Few people rate, and those who do are not a random sample, so it cannot give the rate alone.
- **Let a model judge every answer.** It scales. It is an evaluation product, it sends all content to a model, and its own error must be measured against checked answers anyway. A model may serve as the evaluator for the sample if its agreement with people is known.
- **Use downstream facts** such as a closed ticket or a merged pull request. This is the best signal where the work has such an end. It needs a join that no source provides yet. Kept for later.

## Consequences

- The decision "which tool for which job" is blocked for a deployment that has no checks. The catalogue says so, and Prism shows no card for it.
- Someone must do about 30 checks per period for three platforms. That is the price of the quality signal.
- Sources that already run evaluations can feed Prism without new work, if they emit the standard event.
- Prism needs a small tool to draw the sample and to record a check as an event. It is the only new component this ADR adds.
- The numbers above come from one simulated company with large gaps between platforms. Smaller gaps need larger samples. The sample size must be set from the first real data.
