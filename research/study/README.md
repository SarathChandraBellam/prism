# Context study code

Code for [round 1 of the context study](../../docs/research/context-study-round1.md). This is research code, not part of Prism.

| File | What it does |
|------|--------------|
| `build.py` | Normalises four sources (own Claude Code logs, Fable-5 traces, DataClaw, WildChat) into one session format. Flags harness-injected turns, redacts secrets and emails, and builds context views C1–C6 and C3H. |
| `llm.py` | Cached OpenRouter client. Sends reasoning `effort: none`, asks for no-retention providers, and enforces a budget cap. |
| `label.py` | Session labels per condition and model, turn-level acts per context layer, and turn-by-turn fold runs. |
| `analyze.py` | Builds all tables in the results doc. |

## Data (git-ignored)

`data/` holds downloaded datasets and the normalised sessions, and `cache/` holds model responses. Both contain conversation content and are excluded by `.gitignore`.

To fetch the datasets:
- **DataClaw:** `conversations.jsonl` from `Codingxx/dataclaw-peteromallet` (MIT)
- **Fable-5:** the `.jsonl` files from `AlinCiocan/fable-5-claude-code-traces` (CC-BY-4.0), into `data/fable/`
- **WildChat:** `data/train-00000-of-00086.parquet` from `allenai/WildChat-4.8M` (ODC-BY), saved as `data/wildchat0.parquet`

## Run

```sh
set -a; . ../../.env; set +a        # OPEN_ROUTER_KEY, HF_TOKEN
PILOT_EXCLUDE_SESSIONS=<ids> python3 build.py
BUDGET_USD=2.8 python3 label.py sess turn fold
python3 analyze.py
```

`build.py` needs `uv` to read the WildChat Parquet file.

## Round 2

`round2.py` adds the redefined labels (A), per-prompt labels against SWE-chat (B) and the SWE-chat context curve (C). `analyze2.py` prints the tables in [context-study-round2.md](../../docs/research/context-study-round2.md).

The SWE-chat inputs come from the gated dataset `SALT-NLP/SWE-chat`, so its terms must be accepted on Hugging Face first:
- `data/swe/sessions.parquet` and `data/swe/session_logs.parquet` (about 80 MB)
- 36 selected transcripts in `data/swe/transcripts/`
- per-prompt labels read from row groups of `conversations.parquet`, without downloading the full 6.4 GB file
