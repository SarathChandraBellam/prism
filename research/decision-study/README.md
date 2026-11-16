# Decision study: six decisions, and how sure the traces can be

Code and data for [round 5 of the context study](../../docs/research/decision-study.md). This is research code, not part of Prism.

The study starts from six decisions that a company with several AI tools has to make ([insight catalogue](../../docs/insights.md)). It converts the round 4 lake into the [trace schema](../../docs/trace-schema.md), tests whether each decision can be answered from those spans, and measures how wrong each kind of answer can be. It makes no model calls. It reads the data of [round 4](../cross-platform/) and the price table and scripts of [round 3](../agent-study/).

| File | What it does |
|------|--------------|
| `catalogue.json` | The six decisions as data: owner, metric, unit, kind of evidence, bar for action, and what each reads from the spans. |
| `conform.py` | The first transformer. Converts the round 4 lake into spans in the trace schema shape and counts what it renamed, restructured, inferred and dropped. Writes `data/lake_otel.jsonl` (not committed) and `data/conformance.json`. |
| `base.py` | Loader for the converted spans: sessions, turns and their signals, the fixed rule that rebuilds tasks across platforms, shadow cost. Ground truth is loaded by separate functions and used only to score. |
| `coverage.py` | For each decision and platform: the share of spans that carry each attribute the decision needs, a verdict (ready, partial, blocked), and the same with content switched off. |
| `tasks.py` | Sessions against tasks: platform share three ways, re-done work, cost per session, per task and per correct task, licences against tokens. |
| `sampling.py` | Trace signals against per-turn checks (silent failures), what the full matrix supports, and how many checked answers a choice of platform needs. |
| `seats.py` | Per-seat evidence, a share rule against an evidence rule, and a simulation of longer windows. |
| `demand.py` | What the session after a switch shows was missing, tasks that ended on trouble, the work map, and whether labels agree across platforms. |
| `cards.py` | Insight cards in the [ADR 0006](../../docs/adr/0006-insight-card-contract.md) contract, by fixed rules over the results. |
| `run_all.sh` | The whole study. |

## Run

Requires Python 3.10+ and the committed round 3 and round 4 data. No other dependencies.

```sh
./run_all.sh
```

Every script is seeded (seed 20261116 where it draws): a rerun gives byte-identical files in `data/`.

## Results

| File | Content |
|------|---------|
| `data/conformance.json` | What the transformer changed, per platform |
| `data/coverage.md` | Which decisions each platform's traces can answer |
| `data/tasks.md` | Task accounting and cost |
| `data/sampling.md` | The cost of an outcome signal |
| `data/seats.md` | When a seat can be called unused |
| `data/demand.md` | Unmet demand and the work map |
| `data/cards.md` | The nine insight cards |

Each has a `.json` twin with the full numbers.

## Known limitations

- **The company is simulated.** See the limitations of round 4. Users react by rule, and the same 32 scripts repeat across users.
- **The linking rule had an easy case.** Every re-ask came within 12 minutes on another platform. Its thresholds are those reported in round 4 and were not tuned here.
- **Ground truth stands in for checked answers.** Every number with the evidence kind `checked` would need a sample of real checks in a company.
- **Labels belong to recordings, not to sessions.** A session takes the label of the script it resembles most on its platform.
- **The seat simulation draws from the designed habits.** It is a design study and is labelled so.
- **Small numbers.** 64 tasks, 13 switches, 37 failed turns, 24 seats.
