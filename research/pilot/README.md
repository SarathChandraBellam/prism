# Pilot: context needed to label agent sessions

Throwaway research code behind the pilot findings in the [context study proposal](../../docs/research/context-study-proposal.md#5-pilot-findings-one-user-claude-code-logs). It is not part of Prism and is not maintained as a library.

It parses local Claude Code session logs into sessions and traces, then asks models on OpenRouter to label them in different ways. It compares the labels with a stronger reference model and records cost.

## Privacy

The parsed sessions and model responses contain the content of your own conversations. They are written next to the scripts (`sessions.jsonl`, `cache/`, `g_results.json`, `g_output.txt`) and are **git-ignored**. Never commit them.

Before any model call, `parse.py` redacts common secret formats (API keys, tokens, JWTs, private keys) and email addresses. Redaction is pattern-based and not guaranteed, so review your data before sending it to a provider. Requests ask OpenRouter for providers that do not collect data (`data_collection: deny`).

## Files

| File | What it does |
|------|--------------|
| `parse.py` | Reads `~/.claude/projects/*/*.jsonl` and builds sessions with three views: `full`, `chat` and `chat_err` (chat plus failing-tool excerpts). It also builds per-trace views and structural facts. |
| `run.py` | Calls OpenRouter for the approaches `full`, `chat`, `chat_err`, `per_trace` and `fold`. Every call is cached, so reruns are free. |
| `analyze.py` | Scores each approach against the reference model, measures agreement between models and fold drift, and shows the collaboration-pattern distribution. |
| `approach_g.py` | Labels each user turn with an interaction act at four context layers, derives session patterns with a hand-written mapping and compares them with session-level labels. |

## Running

Requires Python 3.10+ and an OpenRouter key.

```sh
export OPEN_ROUTER_KEY=...                 # or: set -a; . ../../.env; set +a
export PILOT_EXCLUDE_SESSIONS=<id>,<id>    # optional: sessions to skip
python3 -I parse.py                        # free, no model calls

python3 -I run.py '{"models":["z-ai/glm-5.3"],"approaches":["full"]}'
python3 -I run.py '{"models":["z-ai/glm-5.3-flash"],"approaches":["chat","chat_err","per_trace"],"fold":true}'
python3 -I analyze.py

export PILOT_G_SESSIONS=<id-prefix>,...    # optional; default is the first 6 sessions with 4-10 traces
PYTHONPATH=. python3 approach_g.py
```

`BUDGET_USD` (default 1.5) stops the fold stage once that much has been spent. Watch reasoning tokens: in the pilot, they cost more than the input.

## Known limitations

- **Human versus harness text:** harness-injected text (skill instructions, task notifications, tool notes) is not yet filtered out of user turns.
- **The reference is a model:** it is a stronger model, not human labels.
- **The act mapping is hand-written:** `approach_g.py` maps turn acts to session patterns with untested rules.
- **macOS SSL:** the SSL context points at `/etc/ssl/cert.pem`, which works on macOS. Adjust it elsewhere.
