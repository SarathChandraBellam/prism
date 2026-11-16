# 0006. The insight card and its four kinds of evidence

- **Status:** proposed
- **Date:** 2026-11-16

## Context

[ADR 0004](0004-scope-organisation-decisions.md) makes the decision the product. The organisation view therefore needs one output format that an owner can act on, and that says how far to trust it.

[Round 4](../research/cross-platform-study.md) produced seven insight cards by rule. They had the right parts: a finding, evidence, an action and an owner. They also showed the risk. The card "seats nobody uses" looked as firm as the others, but half of its flags were wrong. The card on abandoned tasks rested on a flag that was wrong about half the time. A reader could not tell a counted number from a guessed one.

[Round 5](../research/decision-study.md) measured how wrong each kind of number can be. The errors differ by kind, not by card.

## Decision

1. **The card is the only organisation output.** A card has these fields:

   | Field | Rule |
   |-------|------|
   | `decision` | One row of the [insight catalogue](../insights.md) |
   | `owner` | The role that can take the action |
   | `finding` | One sentence in plain words, with its number |
   | `evidence` | Each number with the count behind it (n). A rate also carries an interval |
   | `basis` | The weakest kind of evidence the card uses (point 2) |
   | `error` | The measured error of that basis (point 3) |
   | `readiness` | `act`, `check first` or `watch` (point 4) |
   | `action` | What the owner should do |
   | `caveat` | What would make the finding wrong |
   | `scope` | The period, the platforms and the groups it covers |

2. **Evidence has four kinds.** Each number on a card is one of them:

   | Basis | What it is | Example |
   |-------|-----------|---------|
   | `counted` | Read from spans with no interpretation | sessions, tokens, tool calls, failed requests |
   | `linked` | A rule joins or flags spans | a re-ask linked to its first session; a session that "ended on trouble" |
   | `labelled` | A model read content and gave a label | domain, task type |
   | `checked` | Someone or something verified an answer | a sampled check of a reply |

3. **Every number that is not counted carries its error.** A `linked` number carries the precision and recall of its rule. A `labelled` number carries the agreement of the label. A `checked` number carries its sampling interval. The error is measured on a reference set and stated on the card. A basis with no measured error cannot be used on a card.
4. **Readiness is set by rule, not by the writer.**

   | Readiness | When | What the owner does |
   |-----------|------|---------------------|
   | `act` | The evidence meets the bar that the catalogue sets for the decision | Takes the action |
   | `check first` | The finding is likely, but its error is large enough that a wrong action would cost something | Confirms with the people concerned, then acts |
   | `watch` | The data cannot support the finding yet | Waits. The card says how much more data it needs |

   The bar is part of the catalogue row. For example, a seat is `act` only when its quietness is unlikely to be chance.
5. **Cards are ranked by what they touch.** The rank is the share of tasks, people or spend behind the finding. Readiness does not change the rank. It changes what the owner does.
6. **Cards about people are about groups.** A card names a group and its size. A group below the minimum size is not shown (the minimum is set by the privacy model). Only a seat card names a holder.
7. **The narrator may reword a card, not change it.** As in the personal report, a model may write the sentence. It may not add a number, raise the readiness or drop the caveat.

## Alternatives considered

- **A dashboard of metrics.** It shows everything and decides nothing. It also shows counted and guessed numbers side by side with no mark.
- **One confidence score per card.** A single score hides why a card is weak. The four kinds say what to fix: a better rule, a better label or more checks.
- **Let the model judge readiness.** It would be neither reproducible nor auditable.

## Consequences

- Each catalogue row needs a bar for `act`. Setting the bar is a design task for each decision.
- Prism needs a small reference set to measure the error of rules and labels. Without one, linked and labelled numbers stay off the cards.
- Some cards will say `watch` for weeks. That is correct: round 5 shows that two weeks of data cannot settle a seat.
- The round 4 card rules are replaced by rules that fill this contract (see the cards in round 5).
