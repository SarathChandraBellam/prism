# Changelog

All notable changes to this project are documented here. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project will use [Semantic Versioning](https://semver.org/) once it makes releases.

## [Unreleased]

### Added

- Project intent, architecture draft, privacy model and contribution guidelines.
- Round 3 of the context study: an agent with MCP servers and skills, a synthetic trace dataset, an observability report and a Prism evaluation on the same traces ([agent trace study](docs/research/agent-trace-study.md)).
- Round 4 of the context study: three simulated AI platforms in three trace formats, adapters into one shape, switch detection, outcome proxies, seat utilisation, routing and insight cards ([cross-platform study](docs/research/cross-platform-study.md)).
- Round 4 completed: all 32 scripts and all 96 session labels; the write-up now reports the complete run.
- Round 5 of the context study: the first transformer into the trace schema, six decisions tested against the traces, task accounting, the cost of an outcome signal, seat evidence, unmet demand and insight cards with a readiness ([decision study](docs/research/decision-study.md)).
- The [insight catalogue](docs/insights.md): the six decisions Prism serves and what each reads from traces.
- A first draft of the [privacy model](docs/privacy.md), which other documents already linked to.
- Proposed ADRs: [0004](docs/adr/0004-scope-organisation-decisions.md) (decisions as the scope), [0005](docs/adr/0005-task-as-unit-of-work.md) (the task as the unit of work), [0006](docs/adr/0006-insight-card-contract.md) (the insight card and four kinds of evidence), [0007](docs/adr/0007-outcome-signal.md) (the outcome signal).

### Changed

- The non-goal on observability is reworded: Prism is not a live monitoring or evaluation tool, but it reads cost, errors and outcomes when a decision needs them.
