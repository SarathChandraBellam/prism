# Cross-platform study: one enterprise, three AI platforms, traces only

Code and data for [round 4 of the context study](../../docs/research/cross-platform-study.md). This is research code, not part of Prism.

Twelve simulated staff in three roles hold seats on three AI platforms whose traces come in three formats. The study asks what can be recovered from the traces alone: platform switching, outcome quality, unused seats, and the gain from routing each task type to its best platform. The platforms are recordings from round 3 plus one new recording. The users are simulated by rule.

All model calls use `openrouter/free`. The analysis needs no model.

**Status: partial.** The daily quota of the free tier ran out during the Chatly recording. 85 of 100 turns are recorded (26 of 32 scripts). The study runs on those 26 scripts (52 of the 64 task instances). The 64 session labels for Beacon and Chatly are not yet made. See "Finish the run" below.

| File | What it does |
|------|--------------|
| `common.py` | Paths, platform names and prices, small helpers. Imports the round 3 code through `sys.path`. |
| `chatly.py` | Records the chat-only platform "Chatly": no tools, no skills, one request per user turn, history kept. Resumable per turn; stops cleanly on a daily quota error. |
| `world.py` | The 12 users, their roles, seats and habits. Writes `data/directory.json` and `data/seats.json`. |
| `replay.py` | Reactive replay: simulated users run the 64 task instances on the platforms they hold seats on, notice failures, switch or give up. Writes the three platform exports and `data/truth.json`. No model calls. |
| `adapters.py` | Three adapters (OTel GenAI spans, LLM-app run trees, chat export) into one span shape. Writes `data/lake.jsonl` and the fidelity counts. |
| `labels.py` | Round 3 session labels for the Beacon and Chatly recordings (one per recording, cached). Atlas labels are reused from round 3. |
| `analysis.py` | Switch detection, outcome proxies against ground truth, seats, routing. Reads the lake, the directory and the seats; reads truth only to score. |
| `insights.py` | Deterministic rules that turn the results into ranked insight cards (`data/insights.md`). |
| `tables.py` | Prints every table used in the write-up (`data/tables.md`). |
| `verify.py` | Sanity checks: counts reconcile, no ground truth or secrets in the exports and the lake. |
| `run_all.sh` | The whole pipeline without model calls. |

## Data (committed, synthetic, 1.9 MB)

| File | Content |
|------|---------|
| `data/export_atlas.jsonl` | Atlas export: OpenTelemetry GenAI spans, users by handle |
| `data/export_beacon.jsonl` | Beacon export: run tree (`chain`, `llm`, `tool` runs), users by email |
| `data/export_chatly.jsonl` | Chatly export: one conversation per line, users by employee id |
| `data/lake.jsonl` | The three exports in one span shape, with a `platform` attribute and the user resolved |
| `data/directory.json`, `data/seats.json` | The identity map and the licences. The analysis may read these. |
| `data/paraphrases.json` | 32 hand-written re-asks, used as the first message of a session that follows a switch |
| `data/truth.json` | Task instances, session chains, which sessions are switches, per-turn check results, the 3 x 26 recordings matrix, designed idle seats. Used only for scoring. |
| `data/results.json`, `data/tables.md`, `data/insights.md`, `data/fidelity.json` | Generated results |

Exports and lake contain no `eval.*` attributes and no designed labels (`verify.py` checks this).

## Run

Requires Python 3.10+ and the round 3 data. No other dependencies.

```sh
python3 chatly.py        # about 10 minutes for 100 requests; resumable
python3 labels.py        # 64 requests; resumable; optional
./run_all.sh             # world, replay, adapters, analysis, insights, verify
python3 tables.py
```

The pipeline after the recordings is seeded (seed 20261113): a rerun gives byte-identical files.

## Finish the run

The free quota resets at 00:00 UTC (2026-11-15 for the run in the write-up). Then:

1. `python3 chatly.py` records the missing 15 turns (M08 to M13).
2. `python3 labels.py` makes up to 64 labels. `analysis.py` uses them only when all three platforms have labels for every script in scope.
3. `./run_all.sh && python3 tables.py`. With all 32 scripts the study has 64 task instances, and every number in the write-up changes.

## Known limitations

- **Users react by rule.** Notice a failed turn with probability 0.8, switch with probability 0.7. The replay creates the switches; the detector is tested on recovering them.
- **The same 32 scripts are replayed across users,** so transcripts repeat. Later turns of a switch session are identical to the first session's.
- **Time is simulated.** Tasks are placed on 2 to 13 November 2026 at role-typical hours. About half of a user's tasks are placed 3 to 25 minutes after another of their tasks, so that time alone does not separate a re-ask from a new task.
- **Labels belong to recordings, not to replayed sessions.** A lake session gets the label of the recording that its text matches best on its own platform.
- **`openrouter/free` picks a different model per request.** Each recording was made once.
- **Small numbers.** 52 tasks, 12 switches, cells of 3 to 8 sessions.
