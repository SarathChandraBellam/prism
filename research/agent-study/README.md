# Agent study: traces from a real agent with MCP servers and skills

Code and data for [round 3 of the context study](../../docs/research/agent-trace-study.md). This is research code, not part of Prism.

A small tool-calling agent ("operations assistant" of a fictional three-person coffee-gear shop) is run through 32 scripted sessions (100 user turns, 3 people). Every turn is logged as a trace. The same traces are then analysed twice: once as **observability** data (reliability, MCP and skill usage, value for money) and once with the **Prism** pipeline (how the people worked).

All model calls use `openrouter/free`. Everything else is local and needs no authentication.

| File | What it does |
|------|--------------|
| `shop_mcp.py` | Builds the deterministic demo database and serves it as an MCP server over stdio (5 tools). |
| `mcp_client.py` | Minimal MCP stdio client. Starts three servers: `shop` (custom), and the reference `filesystem` (14 tools) and `memory` (9 tools) servers from npm. |
| `skills/*/SKILL.md` | Six skills with a name and description. The agent sees the list and loads a body on demand with `load_skill`. |
| `workspace/docs/` | Policy documents the agent can read through the filesystem server. |
| `scenarios.py` | The sessions. Each carries its *designed* labels (domain, task type, expected skill and servers, the act of every turn) and checks that verify answers against the database. |
| `agent.py` | The agent loop and the tracer. Writes OpenTelemetry-GenAI-style spans (`invoke_agent` → `chat`, `execute_tool`) as JSONL. |
| `obs.py` | Observability report. No LLM. |
| `prism.py` | Prism pipeline: trace facts, compact chat view, session labels, per-prompt labels, SQL aggregates, narrated report, and the evaluation against the designed labels. |
| `rescore.py` | Re-applies the checks in `scenarios.py` to stored traces after a check is changed. |

## Data (committed, synthetic)

| File | Content |
|------|---------|
| `data/scenarios.json` | The scripted sessions with designed labels and checks |
| `data/traces.jsonl` | One span per line, main run |
| `data/traces-noskill.jsonl` | Ablation: the same sessions with the skills removed |
| `data/prism_labels.json` | Model labels per session (two draws) and per prompt |
| `data/prices.json` | Paid list prices used for shadow costing |
| `data/observability.md`, `data/prism_report.md` | Generated reports |

Span attributes follow the OpenTelemetry GenAI conventions where one exists (`gen_ai.operation.name`, `gen_ai.conversation.id`, `gen_ai.usage.input_tokens`, `gen_ai.tool.name`, …). Study-specific attributes are prefixed `prism.` (simulated time, turn index, tool-schema size) and `eval.` (check results).

## Run

Requires Python 3.10+, Node 18+ and an OpenRouter key.

```sh
npm install                              # the two reference MCP servers
export OPEN_ROUTER_KEY=...
python3 scenarios.py                     # writes data/scenarios.json
python3 agent.py                         # about 15 minutes; resumable per session
ARM=noskill python3 agent.py             # ablation
python3 obs.py
python3 prism.py label && python3 prism.py report
```

Free models allow about 20 requests a minute and, on an account that has bought credits, 1,000 requests a day. The whole study is about 830 requests.

## Known limitations

- **The user is scripted.** Turns do not react to what the agent said, so a designed "correction" is sent even when the agent was right.
- **Time is simulated.** Sessions are placed on 2 to 13 November 2026 for time-of-day patterns; the database is a snapshot of 13 November.
- **`openrouter/free` picks a different model per request.** Results describe the router, not one model, and are not reproducible call by call.
- **Shadow cost** prices tokens at the paid twin of the model that served the call, or at the median twin price where there is none.
