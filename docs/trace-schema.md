# Trace schema

> **Status: draft for review.** Nothing here is implemented. This document defines the one trace format that every Prism analysis reads. Adapters convert other formats into it. How each harness maps into it is out of scope here.

## Contents

1. [Why one schema](#1-why-one-schema)
2. [Units](#2-units)
3. [Attribute contract](#3-attribute-contract) (normative)
4. [Span record and ingestion](#4-span-record-and-ingestion)
5. [Span types](#5-span-types)
6. [Identity: session, turn, input, user](#6-identity-session-turn-input-user)
7. [Harness edge cases](#7-harness-edge-cases)
8. [Content levels and retention](#8-content-levels-and-retention)
9. [Normalizer rules](#9-normalizer-rules)
10. [Derived views](#10-derived-views-the-analysis-api)
11. [Decisions and open questions](#11-decisions-and-open-questions)
12. [Conformance fixtures](#12-conformance-fixtures)
13. [Appendix: migration from the research lake](#appendix-migration-from-the-research-lake)

## 1. Why one schema

Prism has one input contract: **spans in this schema**. Analyses never read a harness export, a vendor run tree or a chat log directly. An adapter converts each of those into this schema, so adding a source never changes an analysis.

The schema is the **OpenTelemetry GenAI semantic conventions**, plus a small `prism.*` namespace for what those conventions do not cover. Where OpenTelemetry has an attribute, Prism uses it with its exact name and meaning.

- **Base:** [OpenTelemetry GenAI semantic conventions](https://github.com/open-telemetry/semantic-conventions-genai), commit `e6658f1` (6 November 2026). General attributes such as `user.*`, `session.*`, `process.*`, `server.*` and `error.type` come from [OpenTelemetry semantic conventions v1.45.0](https://github.com/open-telemetry/semantic-conventions/tree/v1.45.0).
- **Stability:** all GenAI conventions are still at *Development* status and change between releases. Prism pins one version. Each record carries both `prism.schema.version` (this document) and `prism.semconv.version` (the pinned OpenTelemetry version). A pin change needs a written migration, like the [appendix](#appendix-migration-from-the-research-lake).
- **Extensions:** every Prism-only attribute starts with `prism.`. The [attribute contract](#3-attribute-contract) lists each one with the reason OpenTelemetry does not cover it. If OpenTelemetry later adds an equivalent, Prism migrates to it.

## 2. Units

```
user ── session ── turn ──┬── inference (model request)
         │          │      ├── tool call ──┬── skill load / skill resource read
         │          │      │               ├── command (shell, script)
         │          │      │               └── subagent ── (inferences, tool calls, …)
         │          │      └── inputs, hooks, permission decisions, compaction (span events)
         │          └── next turn (or a fork of an earlier one)
         └── previous / next session (cleared, resumed)
```

| Unit | Definition | Key |
|------|-----------|-----|
| **User** | The principal on whose behalf the harness runs: a person, or a service such as a CI job | `user.hash`, `prism.principal.type` |
| **Session** | One conversation with one harness: turns that share context | `prism.session.id` |
| **Turn** | **One input received while the harness was idle, and everything it causes until the harness is idle again** | `prism.turn.id` |
| **Inference** | One model request, including failed and retried ones | span id |
| **Tool call** | One tool execution, local, remote or provider-side | span id |
| **Subagent** | An agent run started by a tool call of another agent | span id of its boundary span |

**The trace is not a unit.** An OpenTelemetry trace is a transport detail: harnesses use one trace per turn, one per session, or separate traces for subagents joined by span links. Prism groups by `prism.session.id` and `prism.turn.id`, which are on every span, and never by `trace_id`. This replaces the "Trace" level in the [architecture data model](architecture.md#data-model): what that table calls a trace (one agent run caused by a turn) is a **turn** here, and behaviour is counted per turn.

## 3. Attribute contract

This table is normative. It lists every attribute that Prism analyses read. Columns:

- **Kind.** `source`: the source or adapter must supply it. `derived`: the normalizer computes it from other data and the source must not set it. `either`: the source sets it when it can, and otherwise the normalizer derives it.
- **Req.** Prism's requirement, which can be stricter than OpenTelemetry's. **R** required, **C** conditionally required, **Rec** recommended.
- **Lvl.** The [content level](#8-content-levels-and-retention) needed **at ingestion** to produce the value. The stored value is always level 0 (structure), except for the attributes marked 1.

### Every span

| Attribute | Kind | Req | Lvl | Notes |
|-----------|------|-----|-----|-------|
| `gen_ai.operation.name` | source | R | 0 | On every GenAI span |
| `prism.session.id` | derived | R | 0 | [Session](#session) |
| `prism.turn.id` | either | R | 0 | [Turn](#turn) |
| `user.hash` | derived | R | 0 | [User](#user). Raw identifiers are dropped |
| `prism.principal.type` | derived | R | 0 | `person`, `service`, `shared`, `unknown` |
| `prism.harness.name` | source | R | 0 | Resource. The product used (`claude-code`, `codex`, `in-house-bot`), low cardinality |
| `service.version` | source | Rec | 0 | Resource. Harness version |
| `prism.tenant.id` | source | R | 0 | Resource. The installation or organization the adapter reads for. Prevents id collisions |
| `prism.workspace.hash` | derived | Rec | 2 | HMAC of the repository URL or working directory. Separates concurrent sessions and supports per-project views |

### Turn root (and turn-level events)

| Attribute | Kind | Req | Lvl | Notes |
|-----------|------|-----|-----|-------|
| `gen_ai.conversation.id` | source | Rec | 0 | Input to `prism.session.id` |
| `session.id`, `session.previous_id` | source | Rec | 0 | Input to `prism.session.id`; links cleared or resumed sessions |
| `prism.session.id_source` | derived | R | 0 | `conversation_id`, `session_id`, `native`, `inferred` |
| `prism.turn.initiator` | either | R | 0 | Who started the turn: `human`, `automation`, `parent_agent`, `harness` |
| `prism.turn.parent_id` | source | C | 0 | When the turn edits, retries or forks an earlier turn. Turns form a tree, not a list |
| `prism.turn.end_reason` | derived | R | 0 | `completed`, `interrupted`, `error`, `max_steps`, `refused`, `no_reply` |
| `prism.utc_offset_minutes` | either | Rec | 0 | The user's local offset at the turn, for hour-of-day views. From the source or the directory |
| `prism.skills.available` | source | Rec | 0 | Names of the skills offered to the model (the skill catalog). Subject to the [naming rule](#naming-rule-for-custom-components) |
| `prism.sensitivity` | either | R | 0 | `normal`, `sensitive`. Only escalates ([privacy](privacy.md)) |
| `prism.quality` | derived | R | 0 | Flags: `inferred_session`, `inferred_turn`, `incomplete`, `orphans`, `unresolved_user`, `clock_skew`, `unsampled_children` |
| event `prism.input` | either | R | 0 / 1 | One per input part. See [Inputs](#inputs) |
| event `prism.compaction` | source | C | 0 | `trigger` (`auto`, `user`), tokens before and after |
| event `prism.hook` | source | C | 0 | `event`, `outcome` (`pass`, `block`, `modify`), `injected` (whether it added text to the context). Also allowed on tool spans |

### Inference span

| Attribute | Kind | Req | Lvl | Notes |
|-----------|------|-----|-----|-------|
| `gen_ai.provider.name` | source | R | 0 | |
| `gen_ai.request.model`, `gen_ai.response.model` | source | R / Rec | 0 | They differ behind routers and fallbacks |
| `gen_ai.usage.input_tokens`, `gen_ai.usage.output_tokens` | source | Rec | 0 | Per OpenTelemetry, `input_tokens` **includes** cache-read and cache-write tokens. Do not add them again |
| `gen_ai.usage.cache_read.input_tokens`, `gen_ai.usage.cache_write.input_tokens`, `gen_ai.usage.reasoning.output_tokens` | source | Rec | 0 | Cost breakdown |
| `gen_ai.response.finish_reasons` | source | Rec | 0 | `stop`, `length`, `content_filter`, `tool_call`, `compaction`, `error` |
| `gen_ai.response.status` | source | Rec | 0 | `completed`, `incomplete`, `cancelled`, `failed`, … |
| `gen_ai.response.time_to_first_chunk`, `gen_ai.request.stream` | source | Rec | 0 | Perceived latency |
| `gen_ai.conversation.compacted` | source | C | 0 | Set only when true |
| `error.type` | source | C | 0 | When the request failed |
| `prism.step.id` | either | R | 0 | Groups the attempts of one agent-loop step |
| `prism.attempt` | either | R | 0 | 1 for the first try, 2 and up for retries and fallbacks within the step |
| `prism.usage.server_tool_calls` | source | C | 0 | Count of provider-side tool calls, when the provider reports it |

### Tool call span

| Attribute | Kind | Req | Lvl | Notes |
|-----------|------|-----|-----|-------|
| `gen_ai.tool.name` | source | R | 0 | The name the model saw. Subject to the [naming rule](#naming-rule-for-custom-components) |
| `gen_ai.tool.call.id` | source | Rec | 0 | Joins the tool call to the `tool_call` part of the request that caused it |
| `gen_ai.tool.type` | source | Rec | 0 | `function` (client-side), `extension` (agent-side), `datastore` |
| `prism.tool.category` | derived | R | 0 / 2 | **What the call did.** See [Tool categories](#tool-categories) |
| `prism.tool.origin` | derived | R | 0 | Who supplies the tool: `builtin`, `mcp`, `plugin`, `custom`, `provider` |
| `error.type` | source | C | 0 | The tool itself failed. Includes `rejected` and `cancelled` |
| `mcp.method.name`, `mcp.session.id` | source | C | 0 | MCP calls |
| `server.address`, `server.port` | source | C | 0 | Remote MCP servers. Stdio servers have neither |
| `prism.mcp.server.name` | either | C | 0 | MCP calls. OpenTelemetry has no server-name attribute |
| `gen_ai.skill.name`, `gen_ai.skill.resource.name` | either | C | 0 / 2 | When the call loads, reads or runs part of a skill |
| `gen_ai.skill.source.uri` | either | Rec | 2 | Tells apart skills with the same name |
| `prism.skill.activation` | derived | C | 0 / 2 | `tool`, `file_read`, `shell_read`, `script` |
| `prism.skill.scope` | derived | C | 2 | `builtin`, `user`, `project`, `org`, `plugin` |
| `process.executable.name`, `process.exit.code` | source | C | 0 | Command refinement. A non-zero exit is **not** a span error |
| `prism.command.executables` | derived | C | 2 | Every `argv[0]` of a compound command |
| `prism.command.background`, `prism.command.timed_out` | either | C | 0 | |
| `prism.file.path_hash`, `prism.file.ext` | derived | C | 2 | File tools and shell file commands. Counts distinct files and re-reads without storing names |
| `prism.synthetic` | derived | C | 0 | The normalizer created this span ([provider tools](#code-execution)) |
| `gen_ai.transfer.target.name`, `gen_ai.transfer.mode` | source | C | 0 | Agent transfers |
| `gen_ai.agent.name`, `gen_ai.agent.id` | source | C | 0 | On subagent boundaries |
| event `prism.tool.decision` | source | C | 0 | Permission: `decision` (`accept`, `reject`), `source` (`config`, `hook`, `user_once`, `user_always`, `user_reject`, `user_abort`), `wait_ms` |

### Record metadata

| Field | Kind | Req | Notes |
|-------|------|-----|-------|
| `prism.schema.version`, `prism.semconv.version` | derived | R | |
| `prism.source.id` | derived | R | Which adapter instance wrote the record. Part of the record key |
| `prism.ingested_at` | derived | R | |

## 4. Span record and ingestion

Each span is stored as one flat JSON record: the OTLP span model with resource attributes copied down, so that each record stands alone.

```json
{
  "trace_id": "7bfe5dbbedf42504964278938db492c5",
  "span_id": "c3b485c281607aa6",
  "parent_span_id": null,
  "links": [],
  "name": "invoke_agent coder",
  "kind": "INTERNAL",
  "start_time": "2026-11-02T14:05:29.000Z",
  "end_time": "2026-11-02T14:05:48.523Z",
  "status": {"code": "OK", "message": null},
  "resource": {"prism.harness.name": "my-harness", "service.version": "1.4.0", "prism.tenant.id": "acme"},
  "attributes": {"gen_ai.operation.name": "invoke_agent", "prism.session.id": "acme:my-harness:3f1c…", "…": "…"},
  "events": [{"name": "prism.input", "time": "…", "attributes": {"origin": "human", "chars": 212}}],
  "prism": {"schema.version": "0.1", "semconv.version": "e6658f1", "source.id": "otlp-main", "ingested_at": "…"}
}
```

- **Resource attributes describe the process; span attributes describe the operation.** When the same key is on both, the span value wins.
- **Times are UTC.** Local time comes from `prism.utc_offset_minutes`, not from the timestamp.
- **Status** follows OpenTelemetry [recording errors](https://github.com/open-telemetry/semantic-conventions/blob/v1.45.0/docs/general/recording-errors.md): `ERROR` plus `error.type`.

### Ingestion semantics

| Concern | Rule |
|---------|------|
| **Record key** | `(prism.source.id, trace_id, span_id)`. Re-ingesting the same record replaces it. Ingestion is idempotent |
| **Synthesized ids** | Adapters that build spans from logs or exports derive ids deterministically from the source's natural key (for example, the first 8 bytes of SHA-256 of `harness:session:message-id`), so that a re-import produces the same ids |
| **Late and out-of-order spans** | Accepted at any time. The derived views for the affected turn and session are recomputed. Extraction uses a watermark, as in [ADR 0002](adr/0002-session-level-extraction-from-traces.md) |
| **Unfinished spans** | A span with no end time after the session's idle timeout gets the end of its last child (or its start) and the turn gets the `incomplete` flag |
| **Orphans** | A span whose parent never arrives is attached to its turn by `prism.turn.id` when known, and the turn gets the `orphans` flag |
| **Sampling** | Prism needs whole turns. A sampled-out child makes counts low, so the turn gets `unsampled_children` when the source says it sampled |
| **Clock skew** | Within a session, order by the source's own sequence counter when it has one, then by time. Children that start before their parent beyond a tolerance give the `clock_skew` flag |
| **Re-normalization** | Level 2 content is discarded after ingestion ([section 8](#8-content-levels-and-retention)), so attributes derived from it cannot be recomputed later. A new normalizer rule applies to new data only. This is a deliberate cost of the privacy model |

## 5. Span types

| Operation | Role in Prism |
|-----------|---------------|
| `invoke_agent` (INTERNAL) | Agent run. A turn root or a subagent boundary |
| `invoke_agent` (CLIENT, `gen_ai.client.invoke_agent`) | Call to a **remote** agent. Its internals are usually invisible |
| `invoke_workflow`, `invoke_runner` | Framework entry points. Can be the turn root |
| `chat`, `generate_content`, `text_completion` | Inference |
| `execute_tool` | Tool call, with the four OpenTelemetry refinements: load skill, read skill resource, command, transfer |
| `plan` | Explicit planning phase. Kept, not counted as a tool call |
| `retrieval`, `embeddings`, memory operations (`search_memory`, `create_memory`, …) | Kept. Memory operations count as `memory` activity |
| `create_agent`, `fetch_response`, `realtime_inference` | Kept, not used by analyses yet |
| MCP client span (`tools/call {tool}`) | Merged into the matching `execute_tool` span (see [MCP](#mcp-tools)) |

**Parentage is normalized.** OpenTelemetry does not say where tool spans sit in the tree. Prism's rule: inference spans and client-side tool spans are **children of the agent run** they belong to. Provider-side tools, which run inside a model request, are **children of that inference span**. `gen_ai.tool.call.id` links a tool span to the request that asked for it.

**Hooks, inputs, permission decisions and compaction are span events, not spans.** They are not GenAI operations, and making them spans would give them operation names that no other OpenTelemetry consumer knows.

## 6. Identity: session, turn, input, user

### Session

Every span carries **`prism.session.id = {tenant}:{harness}:{id}`**, where `{id}` is the first of:

| Priority | Source | `prism.session.id_source` |
|----------|--------|---------------------------|
| 1 | `gen_ai.conversation.id` **of the turn root** | `conversation_id` |
| 2 | `session.id` | `session_id` |
| 3 | A native id that the adapter supplies | `native` |
| 4 | Inferred: same `user.hash`, harness and `prism.workspace.hash`, with a gap below the inactivity threshold | `inferred` |

- **A separate key** because OpenTelemetry says instrumentations should not make up a conversation id, but Prism needs a key on every span. The tenant and harness prefixes prevent collisions between installations.
- **Subagents inherit the session of their turn root**, even when they carry their own `gen_ai.conversation.id`. That attribute is kept as it is. Otherwise every subagent would become its own session.
- **Linked sessions.** Clearing the context or resuming often creates a new id. `session.previous_id` links them, and the derived **session chain** is what a person thinks of as "the same work". A fork starts a new chain.
- **No guessing across devices.** A session resumed on another device is the same session only if the source keeps its id or records `session.previous_id`. Otherwise they are two sessions.
- **Concurrent sessions** (two terminals in the same project) cannot be separated by priority 4. They are merged and flagged `inferred_session`. Sources that need correct numbers must supply an id.

### Turn

A turn is **one input received while the harness was idle, and everything it causes until the harness is idle again**. Input that arrives while the harness is working (a queued message, an answer to an ask-user question, a permission reply) joins the running turn as a `prism.input` event. It does not start a new turn.

The normalizer finds turn roots in this order:

1. **The source names the turn** (a prompt id or an interaction span). The adapter sets `prism.turn.id`. Sources with one trace per session, or with several agents in sequence inside one turn, **must** do this, because the tree shape alone is ambiguous.
2. **Otherwise, the outermost entry span** (`invoke_agent`, `invoke_workflow` or `invoke_runner`) that is not inside a tool call. Entry spans inside a tool call are subagents.
3. **Otherwise (no entry span, for example a plain chat client),** each inference whose input ends with a new user message starts a turn. This needs level 1 content. Without content, each inference is a turn. Both cases get the `inferred_turn` flag.

Turn order is **not stored**. Views order turns by start time within the session. Edits, retries and rewinds are recorded with `prism.turn.parent_id`, because a turn sequence is really a tree.

### Inputs

Round 1 found that 20 to 51% of "user" turns in agent logs were not typed by a person. One input often mixes several authors: typed text, a pasted log, an attached file, an expanded command and hook output. So **origin is recorded per input part**, as `prism.input` events on the turn root, or on the tool span for ask-user and permission replies:

| Attribute | Lvl | Values |
|-----------|-----|--------|
| `origin` | 0 | `human` (typed or pasted by the person), `command` (a command or skill the person ran, expanded by the harness), `attachment` (a file or image the person attached), `harness` (reminders, hook output, notices, tool results sent in the user role), `parent_agent`, `automation` |
| `pasted` | 0 | For `human` parts, when the source can tell: the text was pasted, not typed. Pasted context matters for re-explanation counts |
| `chars` | 0 | Length |
| `command` | 0 | For `command` parts: the command or skill name (naming rule applies) |
| `text` | **1** | The part's text. Held only until extraction ([section 8](#8-content-levels-and-retention)) |

- **`prism.turn.initiator`** says who started the turn. It is single-valued, because a turn has exactly one trigger: a person, an automation, a parent agent, or the harness (for example a finished background task).
- **The chat view reads `human` and `command` parts only.** Everything else is context, not the person's words.
- Adapters that cannot split the parts send one part with the best origin they can determine and set `origin` to `human` only when they are sure.

### User

The stored key is **`user.hash`** (general OpenTelemetry: "unique user hash to correlate information for a user in anonymized form").

1. The adapter brings whatever identifier the source has: `user.id`, `user.email`, `user.name`, an account id or an employee id, on the resource (single-user CLI) or on the span (multi-user server).
2. The normalizer resolves it through the **identity directory** (configuration that maps each handle, email or account id to one principal) and writes `user.hash = HMAC(key, principal id)` and `prism.principal.type`.
3. It also writes **`prism.identity.raw_key = HMAC(key, namespace:raw id)`**. When the directory learns about an identifier later, stored spans are re-keyed through this value, without ever storing the raw id.
4. **The HMAC key is versioned, and rotation means re-keying** stored hashes, not starting new ones. Otherwise the 12-month view breaks at every rotation.
5. **Raw identifiers are dropped at ingestion:** `user.id`, `user.email`, `user.name`, `user.full_name`, `host.name`, `host.id`. Workspace paths and repository URLs survive only as HMACs.
6. **Not every principal is a person.** CI jobs, bots, API keys and shared accounts get `service` or `shared`. Their sessions are excluded from personal reports and counted separately in organization views.
7. **Unresolved identifiers** get `user.hash = HMAC(key, "unresolved:" + raw id)`, `prism.principal.type = unknown` and the `unresolved_user` flag. They are never merged with a resolved person by guessing.

Org structure (team, role) is **not** stored on spans. It is joined from the directory at aggregation time, so that a move between teams does not rewrite history, and minimum-group rules are applied in one place.

One person can use several harnesses. `user.hash` joins them, and `prism.session.id` never does, because a session belongs to one harness. Detecting switching between harnesses is an analysis on top of this schema.

### Naming rule for custom components

Names of skills, MCP servers, tools and subagent types can reveal private projects. A name is stored as it is only when it is in a **public or org catalog** (built-in, marketplace or published by the organization). Any other name is stored as `custom:{HMAC(key, name)[:8]}`. Counts and "same skill again" stay possible; the name does not leak.

## 7. Harness edge cases

These are the cases where "one tool call" is not one clear thing. For each one, the schema says what the normalized record looks like, however the source emitted it.

### Tool categories

`prism.tool.category` is one vocabulary for **what a call did**, across all tools, the shell included:

`file_read`, `file_write`, `file_search`, `vcs`, `build`, `test`, `package`, `network`, `process`, `code_exec`, `web_search`, `web_fetch`, `skill`, `subagent`, `memory`, `plan`, `ask_user`, `other`

- `Read`, `read_file`, `view` and a shell `cat` are all `file_read`. Analyses that count file activity then include harnesses that read files through the shell.
- For a shell call, the category comes from the **primary executable**: the first one that is not a helper (`cd`, `export`, `echo`, `tee`, `true`). `cd app && npm test | tee log` is `test`. This needs the command text (level 2). At level 0 the category is the tool's own default (`process` for a shell).
- Who supplies the tool (MCP, plugin, provider) is `prism.tool.origin`, not the category.

### Skills

A skill (an [Agent Skills](https://agentskills.io) folder with `SKILL.md`, and optionally `references/`, `assets/` and `scripts/`) can enter the context in several ways. The OpenTelemetry skill refinements apply only when **a dedicated tool** does the work.

| How the skill is activated | Source shape | Normalized record |
|---------------------------|--------------|-------------------|
| **Dedicated load tool** (`Skill`, `load_skill`) | Load-skill refinement | As emitted. `prism.skill.activation = tool` |
| **Dedicated resource tool** (`read_skill_resource`) | Read-skill-resource refinement | As emitted |
| **Generic file read of `SKILL.md`**: the harness lists skill paths, and the model opens one with its normal read tool | `execute_tool` with a file path | Add `gen_ai.skill.name`, `gen_ai.skill.source.uri`, `prism.skill.activation = file_read`. A file under `references/` or `assets/` also gets `gen_ai.skill.resource.name` |
| **Shell read** (`cat`, `sed -n` or `head` on a skill file) | Command refinement | As above, with `prism.skill.activation = shell_read` |
| **Skill script run** (`python skills/pdf/scripts/fill.py`) | Command refinement | Add `gen_ai.skill.name` and `gen_ai.skill.resource.name = scripts/fill.py`, as the command refinement allows. `prism.skill.activation = script` |
| **User-invoked** (`/skill-name`; the harness injects the body into the input) | No tool call | A `prism.input` part with `origin = command` and the skill name. No synthetic tool span |
| **Preloaded** (always in the system prompt or an always-loaded rules file) | Nothing per turn | Not an activation. Appears only in `prism.skills.available` |

Rules:

- **The inferred cases need paths or commands (level 2) at ingestion.** Without them, a skill read through a generic tool looks like any other file read, and the session's skill use is reported as **unknown**, not as zero.
- **Skill roots are configuration.** Paths are matched against known roots (`<workspace>/.*/skills/<name>/`, `~/.*/skills/<name>/`, plugin roots and the catalog), not against any file named `SKILL.md`. Paths are normalized before matching: workspace-relative inside the workspace, and `~/…` for the home directory, so that user-level skills outside the workspace are still found.
- **What counts as a load.** The first read of a skill's `SKILL.md` within one context window is a load. Partial reads (offset or limit) and repeated reads in the same window are not new loads. A read after compaction is a new load, so "reloaded after compaction" stays visible.
- **Same name, different source.** `gen_ai.skill.source.uri` tells them apart; `prism.skill.scope` is the low-cardinality version for reports.
- **Available but not used.** `prism.skills.available` on the turn root makes it possible to report a skill that was offered but not loaded. Round 3 found that skills were loaded every time but followed only some of the time. Available-but-unused is the next question.
- **Nested use.** A skill used inside a subagent belongs to that subagent. The tree shows who used it.

### Commands (shell and scripts)

- Use the OpenTelemetry command refinement: `process.executable.name` (single process only) and `process.exit.code`.
- `prism.command.executables` lists every `argv[0]` of a compound command, which OpenTelemetry cannot express.
- **Three different facts.** Span `ERROR` means the tool failed (timeout, sandbox denial, crash). A non-zero exit code means the command failed. Neither says whether the turn's goal was met: a failing test run can be exactly what the person asked for.
- **Background commands** (`prism.command.background`) can end after their turn. They stay in the turn that started them. If their completion starts a new turn, that turn's initiator is `harness`.
- The full command text is level 2. It is used to derive the attributes above and is then discarded.

### Code execution

1. **Client-side interpreter** (a sandbox, notebook or REPL that the harness runs): an ordinary tool span, `prism.tool.category = code_exec`.
2. **Provider-side tool** (the model provider runs code, web search or similar inside the request): **there is no tool span in the source.** The call appears only as `server_tool_call` and `server_tool_call_response` parts in `gen_ai.output.messages` (level 3 content), or as a usage count.

For case 2, the normalizer creates a **synthetic** tool span: a child of the inference span, **zero duration at the inference's end time**, `prism.tool.origin = provider`, `prism.synthetic = true`. It needs the message parts at ingestion. Without them, only `prism.usage.server_tool_calls` is available, and analyses must treat provider tools as **under-counted**.

### MCP tools

- MCP tool calls are `execute_tool` spans with `mcp.method.name = tools/call`. OpenTelemetry asks MCP instrumentation to enrich an existing tool span **only if it can detect one**. Otherwise a separate MCP client span (`tools/call {tool}`) exists. The normalizer merges such a span into its `execute_tool` parent, or promotes it to the tool span if there is no parent.
- `prism.mcp.server.name` comes from the source, from `server.address` for remote servers, or from the tool-name prefix (`mcp__shop__get_order` → `shop`).
- MCP traffic that is not a tool call (`resources/read`, `prompts/get`) is kept but not counted as a tool call.

### Subagents and transfers

Sources emit subagents in three shapes, and all of them normalize to **a tool span that is the subagent boundary**, with the subagent's inference and tool spans beneath it:

| Source shape | Normalization |
|--------------|---------------|
| Tool span → `invoke_agent` → inferences | As emitted |
| Transfer tool span → inferences directly (OpenTelemetry says not to emit `invoke_agent` when a tool delegates internally) | The transfer span is the boundary |
| Subagent in a separate trace, joined by a span link | `parent_span_id` is rewritten to the tool span. The link is kept |

- **`gen_ai.transfer.mode = pass_control`:** control does not come back. The target agent finishes the turn, and the turn ends when the target ends.
- **Remote agents** (CLIENT `invoke_agent`) are subagents whose insides are not visible.
- **A subagent's input is written by the parent model.** Its input parts have `origin = parent_agent` and are never in the chat view.
- **Parallel subagents** overlap in time. Duration totals use the turn's wall-clock time, not the sum of children.

### Interventions, cancellation and retries

| Case | Record |
|------|--------|
| **Permission asked** | `prism.tool.decision` event on the tool span. A rejected call still has a tool span, with `error.type = rejected` and no execution |
| **Ask-user tool** | Tool span with `prism.tool.category = ask_user`. The answer is a `prism.input` event with `origin = human` |
| **Hook** | `prism.hook` event. A blocking hook explains a tool call that would otherwise look like a model failure |
| **Compaction** | `gen_ai.conversation.compacted` on later inferences, `compaction` as a finish reason or message part when present, and the `prism.compaction` event on the turn root. Context loss explains re-explanation |
| **Interruption** | `prism.turn.end_reason = interrupted`. Inferences in flight get `gen_ai.response.status = cancelled`; tools in flight get `error.type = cancelled` |
| **Cancelled siblings** | When one parallel tool call fails and the harness cancels the others, those get `error.type = cancelled`, not counted as failures of their own |
| **Retries and fallback** | Attempts of one step share `prism.step.id`, ordered by `prism.attempt`. A fallback to another model shows as a different `gen_ai.response.model` within the step |

### Cost

Cost is **not stored**. It is computed from a price table, which needs `gen_ai.provider.name`, `gen_ai.response.model`, the token breakdown and, where the provider has one, the service tier (provider-specific OpenTelemetry attribute). Because `input_tokens` already includes cache tokens, cost is `(input − cache_read − cache_write) × input price + cache_read × read price + cache_write × write price + output × output price`.

## 8. Content levels and retention

OpenTelemetry records no content by default. Prism defines four levels. Each analysis states the lowest level it needs, and the normalizer drops everything above the configured level before anything is stored. This is how the schema keeps [privacy commitment 2](privacy.md) ("raw transcripts and traces are never stored"): **Prism stores structure, not content.**

| Level | Adds at ingestion | What is stored, and for how long | Enables |
|-------|-------------------|----------------------------------|---------|
| **0. Structure** | Names, counts, timing, tokens, errors, exit codes | Stored for the retention period. These are the trace facts | Tool mix, reliability, cost, subagents, skills through dedicated tools |
| **1. Conversation** | Text of `human` and `command` input parts; the final reply of each turn | Held in a transient buffer until the session's extraction (including the fold window), then deleted. Never sent to the narrator | Chat view, labels, behaviour counts |
| **2. Tool detail** | Tool arguments: file paths, command text | **Not stored.** Used during normalization to derive level 0 attributes (category, executables, skill, path hash), then discarded | Inferred skills, command categories, distinct files touched |
| **3. Full content** | All messages, system instructions, tool results | **Never enters the Prism pipeline.** Research setups only. `*_ref` attributes are not followed | Validation studies |

- **Exclusion happens before ingestion.** Incognito, opted-out or policy-restricted sessions produce no spans at all. The adapter drops them.
- **Deletion at the source** tombstones the session: its spans and records are deleted and it leaves future aggregates.
- **Sensitive sessions** keep their structure; `prism.sensitivity` tells the extractor to minimize.

## 9. Normalizer rules

The normalizer turns adapter output into stored spans. It runs these steps in order, and each one is idempotent:

1. **Drop excluded** sessions and **enforce the content level**: keep content up to the configured level for the steps below.
2. **Resolve identity**: `user.hash`, `prism.principal.type`, `prism.identity.raw_key`. Drop raw identifiers.
3. **Assign turns** ([Turn](#turn)) and **sessions** ([Session](#session)) and copy `prism.turn.id` and `prism.session.id` to every span.
4. **Normalize the tree**: parentage, link resolution for subagents, MCP span merge, subagent boundaries.
5. **Classify tools**: `prism.tool.category`, `prism.tool.origin`, command executables, file path hashes.
6. **Detect skills**: the inferred activations, with paths matched against the skill roots.
7. **Synthesize** provider-side tool spans when message parts are present.
8. **Apply the naming rule** to skill, tool, MCP server and subagent names.
9. **Set quality flags** and `prism.turn.end_reason`.
10. **Discard level 2 content**, move level 1 text to the transient buffer, and store the spans.

## 10. Derived views (the analysis API)

Spans are the storage contract. **Analyses do not walk span trees.** They read these views, which are recomputed when spans arrive:

| View | One row per | Main columns |
|------|-------------|--------------|
| `sessions` | session | user, harness, workspace, chain id, first and last time, turns, quality flags |
| `turns` | turn | session, index (by start time), parent turn, initiator, end reason, duration, inferences, tool calls, tokens, quality flags |
| `inputs` | input part | turn, origin, pasted, chars, time, whether it arrived during the turn |
| `inferences` | model request | turn, step, attempt, model, tokens, status, latency |
| `tool_calls` | tool call | turn, agent depth, category, origin, base name (without MCP prefix), MCP server, status, exit code, decision |
| `skill_events` | skill activation | turn, skill, activation, scope, load number within the session, user-invoked or not |
| `agents` | agent run | turn, depth, role (`main`, `subagent`, `remote`), name |

Agent depth and role, turn index, load numbers and base tool names live only in the views. They are derivable, so they are not stored on spans.

## 11. Decisions and open questions

Decided in this draft:

1. **Spans are the storage contract; the views are the analysis API.**
2. **Synthetic spans only for provider-side tools**: flagged and zero-duration. A user-invoked skill is an input part, not a fake tool call.
3. **Hooks, inputs, permission decisions and compaction are span events,** not spans with a custom operation name.
4. **Both sessions and chains are kept.** Reports for people use chains; structural counts use sessions.
5. **Origin is recorded per input part;** the turn has one initiator.

Still open:

1. **Turn definition on real data.** Validate the three-step rule on at least two real harnesses before treating it as settled.
2. **Inactivity threshold** for inferred sessions (also in the [architecture](architecture.md#open-questions)).
3. **The naming rule in personal reports.** A person's own report could show their own custom skill names, resolved locally. Is that safe enough?
4. **Upstream proposals to OpenTelemetry:** MCP server name first (small, general), then input origin. Wait on a turn concept until the definition has survived real data.
5. **Level 1 buffer lifetime** with folding: how long after a session goes idle may its text be kept for a late fold?

## 12. Conformance fixtures

Each edge case gets a small golden trace (input) and its expected normalized spans and view rows (output). The normalizer is correct when all fixtures pass. To build:

1. Plain chat with no agent spans (turns inferred from inference spans)
2. One trace per turn, main agent only
3. One trace per session, with an adapter-supplied turn id
4. `invoke_runner` → `invoke_agent` (the outermost entry span is the root)
5. Mixed input: typed text, a pasted log, an attached file, hook output
6. Queued message and an ask-user answer during a turn (no new turn)
7. Edit and retry of an earlier turn (`prism.turn.parent_id`)
8. Skill through a dedicated tool; through a generic read of `SKILL.md`; through `cat`; a skill script run; a user-invoked skill; a reload after compaction
9. Compound shell command (`cd app && npm test | tee log`) with a non-zero exit
10. MCP call with and without a separate MCP client span; a stdio server
11. Subagent in all three shapes, a `pass_control` transfer and two parallel subagents
12. Provider-side code execution with and without message parts
13. Permission rejected; one parallel tool fails and siblings are cancelled; an interrupted turn
14. Retry and model fallback within one step
15. Background command that ends after its turn and starts a new turn
16. Cleared session with `session.previous_id`; two concurrent sessions without ids
17. Unresolved user later added to the directory (re-key)
18. Re-ingestion of the same export (idempotence); a late span; an unfinished span

## Appendix: migration from the research lake

The round 3 and round 4 lake files already use this shape, with a few non-standard names:

| Current | Becomes |
|---------|---------|
| `gen_ai.input.text` | `prism.input` event, `origin = human`, `text` |
| `gen_ai.output.text` | Final reply text (level 1, transient); full content in `gen_ai.output.messages` |
| `gen_ai.output.tool_calls` | `tool_call` parts in `gen_ai.output.messages` |
| `gen_ai.usage.cached_tokens` | `gen_ai.usage.cache_read.input_tokens` |
| `gen_ai.usage.reasoning_tokens` | `gen_ai.usage.reasoning.output_tokens` |
| `gen_ai.usage.cost` | Dropped (computed from the price table) |
| `session.turn_index`, `prism.turn_index` | Dropped (the `turns` view computes the index); `prism.turn.id` added |
| `platform` | `prism.harness.name` |
| `mcp.server.name` | `prism.mcp.server.name` |
| `prism.skill.name` | `gen_ai.skill.name` |
| `http.status_code` | `http.response.status_code` |
| `user.id` | `user.hash` |
