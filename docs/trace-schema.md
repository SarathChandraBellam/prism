# Trace schema

> **Status: draft.** Follows [ADR 0003](adr/0003-otel-trace-as-base.md). This document restates the parts of the [OpenTelemetry GenAI semantic conventions](https://github.com/open-telemetry/semantic-conventions-genai) (commit `e6658f1`, 6 November 2026) that Prism reads. It adds nothing of its own. Where this document and OpenTelemetry differ, OpenTelemetry is right and this document must be fixed.

## 1. Trace and span

A **trace** is a tree of **spans** that share one `trace_id`. Each span is one operation. Every span has these fields, from the OpenTelemetry span model:

| Field | Meaning |
|-------|---------|
| `trace_id` | The trace the span belongs to (16 bytes, hex) |
| `span_id` | The span's own id (8 bytes, hex) |
| `parent_span_id` | The parent span. Empty for the root of the trace |
| `name` | Span name, for example `chat gpt-4o` or `execute_tool Read` |
| `kind` | `INTERNAL` (work inside the process) or `CLIENT` (a call to a remote service) |
| `start_time`, `end_time` | Timestamps, nanosecond precision |
| `status` | `UNSET`, `OK` or `ERROR`, with an optional message |
| `attributes` | Key-value pairs. The GenAI conventions define these (sections 3 and 4) |
| `events` | Timestamped records inside the span, for example an exception |
| `links` | References to spans in other traces |
| `resource` | Attributes of the process that emitted the span, for example `service.name` and `service.version` |

On the wire, spans travel as **OTLP** (the OpenTelemetry protocol, in protobuf or JSON). The examples in this document show attributes as a flat map for readability.

## 2. The tree

A typical trace from an agent:

```
invoke_agent {agent}                     agent run (root)
├── chat {model}                         model call: asks for a tool
├── execute_tool {tool}                  tool call
├── chat {model}                         model call: asks for two tools
├── execute_tool {tool}                  tool call
├── execute_tool {tool}                  tool call
└── chat {model}                         model call: final answer
```

A tool that runs another agent has that agent's spans beneath it:

```
invoke_agent {agent}
├── chat {model}
├── execute_tool {tool}                  the parent hands work to a subagent
│   └── invoke_agent {subagent}
│       ├── chat {model}
│       └── execute_tool {tool}
└── chat {model}
```

- `gen_ai.tool.call.id` joins an `execute_tool` span to the tool request in the model call that asked for it.
- A call to an agent that runs on a remote service is an `invoke_agent` span of kind `CLIENT`. What happens inside the remote agent is usually not in the trace.
- An application-defined flow of several agents is wrapped in an `invoke_workflow` span.

## 3. Span types

The span type is set by `gen_ai.operation.name`.

| Span | `gen_ai.operation.name` | Span name | Kind |
|------|------------------------|-----------|------|
| **Agent run** | `invoke_agent` (the model drives the control flow), `invoke_workflow` (the application defines the flow), `invoke_{entrypoint}` such as `invoke_runner` (a framework entry point that is neither) | `{operation} {gen_ai.agent.name}`, or `{operation}` | `INTERNAL` |
| **Remote agent run** | `invoke_agent` | `invoke_agent {gen_ai.agent.name}` | `CLIENT` |
| **Model call** | `chat`, `generate_content` or `text_completion` | `{operation} {gen_ai.request.model}` | `CLIENT` (`INTERNAL` for a model in the same process) |
| **Tool call** | `execute_tool` | `execute_tool {gen_ai.tool.name}` (refinements add more, see 4.3) | `INTERNAL` |
| **Plan** | `plan` | `plan {gen_ai.agent.name}`, or `plan` | `INTERNAL` |
| **Create agent** | `create_agent` | `create_agent {gen_ai.agent.name}` | `CLIENT` |
| **Embeddings** | `embeddings` | `embeddings {gen_ai.request.model}` | `CLIENT` |
| **Retrieval** | `retrieval` | `retrieval` | `INTERNAL` |
| **Memory** | `search_memory`, `create_memory`, `update_memory`, `upsert_memory`, `delete_memory`, `create_memory_store`, `delete_memory_store` | `{operation}` | `CLIENT` (`INTERNAL` for an in-process store) |
| **Fetch response** | `fetch_response` | `fetch_response` | `CLIENT` |
| **Realtime model generation** | `realtime_inference` | `realtime_inference {gen_ai.request.model}` | `CLIENT` |
| **User speech** | `user_speech` | `user_speech` | `INTERNAL` |
| **A2A call** | (none; `a2a.method.name` instead) | `{a2a.method.name}` | `CLIENT` or `SERVER` |

This is every span type in the conventions. All of them are part of the schema.

## 4. Attributes by span type

Requirement levels are OpenTelemetry's: **Required**, **Conditionally required** (when a stated condition holds), **Recommended**, **Opt-in** (off by default; usually content).

### 4.1 Model call

| Attribute | Level | Meaning |
|-----------|-------|---------|
| `gen_ai.operation.name` | Required | `chat`, `generate_content` or `text_completion` |
| `gen_ai.provider.name` | Required | The provider, for example `openai`, `anthropic`, `aws.bedrock` |
| `gen_ai.request.model` | Cond. required (if available) | The model asked for |
| `gen_ai.conversation.id` | Cond. required (if available) | The conversation (session, thread) |
| `error.type` | Cond. required (on error) | Class of the error |
| `gen_ai.request.stream` | Cond. required (only if streaming) | `true` for a streamed request. Unset means not streamed |
| `gen_ai.output.type`, `gen_ai.request.choice.count`, `gen_ai.request.seed`, `gen_ai.request.top_k`, `gen_ai.prompt.name`, `gen_ai.prompt.version` | Cond. required | When used in the request |
| `gen_ai.response.model` | Recommended | The model that answered. Can differ from the request |
| `gen_ai.response.id` | Recommended | The provider's id for the response |
| `gen_ai.response.finish_reasons` | Recommended | Why generation stopped, one per choice |
| `gen_ai.response.time_to_first_chunk` | Recommended (streaming) | Seconds to the first chunk |
| `gen_ai.usage.input_tokens` | Recommended | All input tokens, **including** cached ones |
| `gen_ai.usage.output_tokens` | Recommended | All output tokens |
| `gen_ai.usage.cache_read.input_tokens`, `gen_ai.usage.cache_write.input_tokens` | Recommended (if non-zero) | Input tokens read from or written to the provider's cache |
| `gen_ai.usage.reasoning.output_tokens` | Recommended (if non-zero) | Output tokens spent on reasoning |
| `gen_ai.usage.{text,image,audio}.*` | Recommended (if non-zero) | The same counts split by modality |
| `gen_ai.conversation.compacted` | Recommended | Set to `true` when the context sent is a compacted view of an earlier conversation |
| `gen_ai.request.max_tokens`, `gen_ai.request.temperature`, `gen_ai.request.top_p`, `gen_ai.request.stop_sequences`, `gen_ai.request.frequency_penalty`, `gen_ai.request.presence_penalty`, `gen_ai.request.reasoning.level` | Recommended | Request parameters |
| `gen_ai.request.previous_response.id` | Recommended | The response this request continues |
| `server.address`, `server.port` | Recommended / cond. required | The endpoint called |
| `gen_ai.system_instructions`, `gen_ai.input.messages`, `gen_ai.output.messages`, `gen_ai.tool.definitions` | Opt-in | Content (section 5) |
| `gen_ai.system_instructions_ref`, `gen_ai.input.messages_ref`, `gen_ai.output.messages_ref`, `gen_ai.tool.definitions_ref` | Opt-in | URIs to content kept in external storage |

`gen_ai.response.finish_reasons` values: `stop`, `length`, `content_filter`, `tool_call`, `compaction`, `error`.

### 4.2 Agent run

| Attribute | Level | Meaning |
|-----------|-------|---------|
| `gen_ai.operation.name` | Required | `invoke_agent`, `invoke_workflow` or `invoke_{entrypoint}` |
| `gen_ai.agent.name` | Cond. required (when available) | Human-readable, low-cardinality name of the agent |
| `gen_ai.agent.description` | Cond. required (when available) | |
| `gen_ai.conversation.id` | Cond. required | The conversation, when the framework has one |
| `gen_ai.data_source.id` | Cond. required (if applicable) | A data source the agent uses |
| `error.type` | Cond. required (on error) | |
| `gen_ai.request.model` | Recommended | Only when the agent can use exactly one model |
| `gen_ai.usage.input_tokens`, `gen_ai.usage.output_tokens` | Recommended | Totals for the run |
| `gen_ai.response.finish_reasons`, request parameters | Recommended | As on the model call |
| `gen_ai.input.messages`, `gen_ai.output.messages`, `gen_ai.system_instructions`, `gen_ai.tool.definitions` (and their `_ref` forms) | Opt-in | Content (section 5) |

The remote agent run (kind `CLIENT`) adds `gen_ai.provider.name` (required), `gen_ai.agent.id`, `server.address` and `server.port`.

### 4.3 Tool call

Every tool call has these attributes:

| Attribute | Level | Meaning |
|-----------|-------|---------|
| `gen_ai.operation.name` | Required | `execute_tool` |
| `gen_ai.tool.name` | Required | The tool's name |
| `gen_ai.tool.call.id` | Cond. required | The id the model or provider gave the call, if it gave one |
| `gen_ai.agent.name` | Cond. required (when applicable) | The agent that ran the tool |
| `gen_ai.conversation.id` | Cond. required (if available) | |
| `error.type` | Cond. required (on error) | |
| `gen_ai.tool.type` | Recommended | `function` (run on the client), `extension` (run on the agent side, calls external APIs), `datastore` (data access) |
| `gen_ai.tool.description` | Recommended | |
| `gen_ai.tool.call.arguments` | Opt-in | The arguments, as an object |
| `gen_ai.tool.call.result` | Opt-in | The result, as an object |

OpenTelemetry defines four **refinements**: specialised kinds of tool call that add attributes and extend the span name.

| Refinement | Used when | Extra attributes | Span name |
|-----------|-----------|------------------|-----------|
| **Agent as a tool** | A tool hands work to another agent | `gen_ai.transfer.target.name`, `gen_ai.transfer.mode` (`return_to_caller`, `pass_control`) | `execute_tool {tool}` |
| **Load skill** | A dedicated tool loads an [Agent Skill](https://agentskills.io) into the context | `gen_ai.skill.name` (cond. required), `gen_ai.skill.description`, `gen_ai.skill.source.uri` | `execute_tool {tool} {skill}` |
| **Read skill resource** | A dedicated tool reads a file that belongs to a skill | `gen_ai.skill.name`, `gen_ai.skill.resource.name` (both cond. required), `gen_ai.skill.description`, `gen_ai.skill.source.uri` | `execute_tool {tool} {skill} {resource}` |
| **Command** | A tool runs a command or a script, including a skill's script | `process.executable.name`, `process.exit.code` (cond. required), `process.executable.path`; `gen_ai.skill.name`, `gen_ai.skill.resource.name` when the script belongs to a skill | `execute_tool {tool} {skill} {resource}`, or `execute_tool {tool} {executable}` |

### 4.4 Model Context Protocol (MCP)

A tool call to an MCP server is an `execute_tool` span. The MCP conventions add `mcp.method.name` (`tools/call` for a tool call) and `mcp.session.id`, and `server.address` and `server.port` for remote servers. When the MCP instrumentation cannot add these attributes to an existing tool span, it emits its own `CLIENT` span named `{mcp.method.name} {target}`, for example `tools/call get_order`.

### 4.5 Embeddings

One call that turns inputs into vectors.

| Attribute | Level | Meaning |
|-----------|-------|---------|
| `gen_ai.operation.name` | Required | `embeddings` |
| `gen_ai.provider.name` | Required | |
| `gen_ai.request.model` | Cond. required (if available) | |
| `error.type` | Cond. required (on error) | |
| `gen_ai.response.model` | Recommended | |
| `gen_ai.embeddings.dimension.count` | Recommended | Number of dimensions of each vector |
| `gen_ai.usage.input_tokens` | Recommended | |
| `server.address`, `server.port` | Recommended / cond. required | |

### 4.6 Retrieval

One run of a framework retrieval pipeline (for example a LangChain or LlamaIndex retriever) that returns documents for a query. The steps inside it, such as embeddings or a database query, are their own spans.

| Attribute | Level | Meaning |
|-----------|-------|---------|
| `gen_ai.operation.name` | Required | `retrieval` |
| `error.type` | Cond. required (on error) | |
| `gen_ai.retrieval.top_k` | Recommended | Number of documents asked for |
| `gen_ai.retrieval.query.text` | Opt-in | The query |
| `gen_ai.retrieval.documents` | Opt-in | The documents returned |

### 4.7 Memory

Operations on an agent's long-term memory. The operation name says which:

| `gen_ai.operation.name` | Meaning |
|------------------------|---------|
| `search_memory` | Search or query memories |
| `create_memory` | Create new memory records |
| `update_memory` | Update existing records |
| `upsert_memory` | Create or update, without the caller choosing which |
| `delete_memory` | Delete records |
| `create_memory_store` | Create or initialize a memory store |
| `delete_memory_store` | Delete a memory store |

| Attribute | Level | Meaning |
|-----------|-------|---------|
| `gen_ai.operation.name` | Required | One of the values above |
| `gen_ai.provider.name` | Cond. required | The memory provider |
| `gen_ai.memory.store.id` | Cond. required (if applicable) | The memory store |
| `gen_ai.memory.record.id` | Cond. required | When the operation applies to one record |
| `error.type` | Cond. required (on error) | |
| `gen_ai.memory.record.count` | Recommended | Number of records affected or returned |
| `server.address`, `server.port` | Recommended / cond. required | |
| `gen_ai.memory.query.text` | Opt-in | The search query |
| `gen_ai.memory.records` | Opt-in | The records |

### 4.8 Fetch response

Fetches a response generated earlier, by its id, without running the model again (for example a background response that is polled). It reports no token usage, so tokens are not counted twice.

| Attribute | Level | Meaning |
|-----------|-------|---------|
| `gen_ai.operation.name` | Required | `fetch_response` |
| `gen_ai.provider.name` | Required | |
| `gen_ai.response.id` | Required | The response fetched |
| `error.type` | Cond. required (on error) | |
| `gen_ai.response.status` | Recommended | `queued`, `in_progress`, `completed`, `incomplete`, `cancelled`, `failed` |
| `gen_ai.response.model`, `gen_ai.response.finish_reasons` | Recommended | |
| `server.address`, `server.port` | Recommended / cond. required | |
| `gen_ai.output.messages`, `gen_ai.system_instructions`, `gen_ai.tool.definitions` | Opt-in | Content |

### 4.9 Realtime and speech

For realtime, two-way streaming sessions (voice agents, for example OpenAI Realtime or Gemini Live). One session holds many generations.

**Realtime model generation** (`realtime_inference`): one model generation inside the session.

| Attribute | Level | Meaning |
|-----------|-------|---------|
| `gen_ai.operation.name` | Required | `realtime_inference` |
| `gen_ai.provider.name` | Required | |
| `gen_ai.realtime_session.id` | Cond. required | The realtime session |
| `gen_ai.conversation.id` | Cond. required | |
| `gen_ai.request.model` | Cond. required (if available) | |
| `gen_ai.output.type` | Cond. required | |
| `error.type` | Cond. required (on error) | |
| `gen_ai.response.id`, `gen_ai.response.model`, `gen_ai.response.finish_reasons` | Recommended | |
| `gen_ai.usage.*` | Recommended | Tokens, with the audio, image and text splits |
| `server.address`, `server.port` | Recommended / cond. required | |
| `gen_ai.input.messages`, `gen_ai.output.messages`, `gen_ai.system_instructions`, `gen_ai.tool.definitions` | Opt-in | Content |

**User speech** (`user_speech`): the time the user is speaking into the session.

| Attribute | Level | Meaning |
|-----------|-------|---------|
| `gen_ai.operation.name` | Required | `user_speech` |
| `gen_ai.realtime_session.id` | Cond. required | |
| `error.type` | Cond. required (on error) | |
| `gen_ai.provider.name` | Recommended | |

### 4.10 Agent-to-agent protocol (A2A)

Calls between agents over the [A2A protocol](https://a2a-protocol.org). A `CLIENT` span on the calling side and a `SERVER` span on the receiving side. A2A spans describe the protocol request only; the agent run around them is its own span.

| Attribute | Level | Meaning |
|-----------|-------|---------|
| `a2a.method.name` | Required | The A2A method, for example `SendMessage` |
| `a2a.message.id` | Cond. required | When the request contains a message |
| `a2a.task.id`, `a2a.task.state` | Cond. required | The A2A task and its state |
| `a2a.tenant` | Cond. required | When the request sets a tenant |
| `gen_ai.agent.name`, `gen_ai.agent.description`, `gen_ai.agent.version` | Cond. required | From the remote agent's Agent Card |
| `gen_ai.conversation.id` | Cond. required | |
| `error.type` | Cond. required (on error) | |
| `a2a.protocol.version`, `a2a.message.reference_task_ids` | Recommended | |
| `server.address`, `server.port` | Recommended | |

### 4.11 Attributes outside the GenAI conventions

General OpenTelemetry attributes that a source may also set, on the span or the resource:

| Attribute | Meaning |
|-----------|---------|
| `service.name`, `service.version` | The program that emitted the spans |
| `user.id`, `user.email`, `user.name`, `user.hash` | The user |
| `session.id`, `session.previous_id` | A session, and the session before it |

## 5. Content

The conventions do not record content by default. When a source opts in, content is in these attributes:

| Attribute | Content |
|-----------|---------|
| `gen_ai.system_instructions` | The system prompt, as a list of parts |
| `gen_ai.input.messages` | The messages sent to the model |
| `gen_ai.output.messages` | The messages the model returned |
| `gen_ai.tool.definitions` | The tools offered to the model |
| `gen_ai.tool.call.arguments`, `gen_ai.tool.call.result` | A tool call's input and output |

A **message** has a `role` (`system`, `user`, `assistant`, `tool`), a list of `parts` and, on output messages, a `finish_reason`. **Part** types:

| Part `type` | Holds |
|-------------|-------|
| `text` | Text |
| `reasoning` | The model's reasoning text |
| `tool_call` | A tool request from the model: `id`, `name`, `arguments` |
| `tool_call_response` | A tool result sent back to the model: `id`, `response` |
| `server_tool_call`, `server_tool_call_response` | A tool the model provider ran itself, inside the request |
| `blob`, `file`, `uri` | Media, inline or by reference |
| `transcription` | Transcribed speech |
| `compaction` | A compacted summary of earlier context |

The exact shapes are the JSON schemas in the conventions: [input messages](https://github.com/open-telemetry/semantic-conventions-genai/blob/main/model/gen-ai/gen-ai-input-messages.json) and [output messages](https://github.com/open-telemetry/semantic-conventions-genai/blob/main/model/gen-ai/gen-ai-output-messages.json).

## 6. Events

Besides spans, the conventions define **events**: OpenTelemetry log records emitted alongside the spans and tied to the span that was active when they happened.

| Event | When | Main attributes |
|-------|------|-----------------|
| `gen_ai.client.inference.operation.details` | With a model call. Holds the request's details, including the chat history, so content can be stored apart from traces | As the model call span, plus content |
| `gen_ai.evaluation.result` | An evaluator scored a model output | `gen_ai.evaluation.name` (required), `gen_ai.evaluation.score.value`, `gen_ai.evaluation.score.label`, `gen_ai.evaluation.explanation`, `gen_ai.response.id` |
| `gen_ai.client.realtime_session.started`, `gen_ai.client.realtime_session.ended` | A realtime session opened or closed | `gen_ai.provider.name`, `gen_ai.realtime_session.id`, `gen_ai.request.model`, `error.type` on an abnormal end |
| `gen_ai.client.inference.exception`, `gen_ai.client.embeddings.exception`, `gen_ai.client.fetch_response.exception`, `gen_ai.invoke_agent.exception`, `gen_ai.client.invoke_agent.exception`, `gen_ai.execute_tool.exception` | An operation raised an exception | `exception.type`, `exception.message`, `exception.stacktrace` |

## 7. Example

An agent fixes a failing test: it reads the file, runs the tests, then answers. Content is not recorded.

```json
[
  {"trace_id": "7bfe5dbbedf42504964278938db492c5", "span_id": "a1", "parent_span_id": null,
   "name": "invoke_agent coder", "kind": "INTERNAL", "status": {"code": "OK"},
   "start_time": "2026-11-02T14:05:29.000Z", "end_time": "2026-11-02T14:05:48.500Z",
   "resource": {"service.name": "my-harness", "service.version": "1.4.0"},
   "attributes": {"gen_ai.operation.name": "invoke_agent", "gen_ai.agent.name": "coder",
                  "gen_ai.conversation.id": "conv_3f1c", "user.id": "u-42"}},

  {"trace_id": "7bfe…", "span_id": "b1", "parent_span_id": "a1",
   "name": "chat claude-sonnet-5-5", "kind": "CLIENT", "status": {"code": "OK"},
   "start_time": "2026-11-02T14:05:29.010Z", "end_time": "2026-11-02T14:05:31.200Z",
   "attributes": {"gen_ai.operation.name": "chat", "gen_ai.provider.name": "anthropic",
                  "gen_ai.request.model": "claude-sonnet-5-5", "gen_ai.response.model": "claude-sonnet-5-5",
                  "gen_ai.usage.input_tokens": 3824, "gen_ai.usage.cache_read.input_tokens": 3500,
                  "gen_ai.usage.output_tokens": 41, "gen_ai.response.finish_reasons": ["tool_call"],
                  "gen_ai.conversation.id": "conv_3f1c"}},

  {"trace_id": "7bfe…", "span_id": "c1", "parent_span_id": "a1",
   "name": "execute_tool Read", "kind": "INTERNAL", "status": {"code": "OK"},
   "start_time": "2026-11-02T14:05:31.210Z", "end_time": "2026-11-02T14:05:31.240Z",
   "attributes": {"gen_ai.operation.name": "execute_tool", "gen_ai.tool.name": "Read",
                  "gen_ai.tool.call.id": "toolu_01", "gen_ai.tool.type": "function"}},

  {"trace_id": "7bfe…", "span_id": "b2", "parent_span_id": "a1",
   "name": "chat claude-sonnet-5-5", "kind": "CLIENT", "status": {"code": "OK"},
   "start_time": "2026-11-02T14:05:31.250Z", "end_time": "2026-11-02T14:05:33.900Z",
   "attributes": {"gen_ai.operation.name": "chat", "gen_ai.provider.name": "anthropic",
                  "gen_ai.request.model": "claude-sonnet-5-5", "gen_ai.usage.input_tokens": 5120,
                  "gen_ai.usage.output_tokens": 37, "gen_ai.response.finish_reasons": ["tool_call"]}},

  {"trace_id": "7bfe…", "span_id": "c2", "parent_span_id": "a1",
   "name": "execute_tool Bash pytest", "kind": "INTERNAL", "status": {"code": "OK"},
   "start_time": "2026-11-02T14:05:33.910Z", "end_time": "2026-11-02T14:05:44.100Z",
   "attributes": {"gen_ai.operation.name": "execute_tool", "gen_ai.tool.name": "Bash",
                  "gen_ai.tool.call.id": "toolu_02", "process.executable.name": "pytest",
                  "process.exit.code": 1}},

  {"trace_id": "7bfe…", "span_id": "b3", "parent_span_id": "a1",
   "name": "chat claude-sonnet-5-5", "kind": "CLIENT", "status": {"code": "OK"},
   "start_time": "2026-11-02T14:05:44.110Z", "end_time": "2026-11-02T14:05:48.490Z",
   "attributes": {"gen_ai.operation.name": "chat", "gen_ai.provider.name": "anthropic",
                  "gen_ai.request.model": "claude-sonnet-5-5", "gen_ai.usage.input_tokens": 6010,
                  "gen_ai.usage.output_tokens": 212, "gen_ai.response.finish_reasons": ["stop"]}}
]
```

The test run failed (`process.exit.code` 1), but the tool call itself worked, so its status is `OK`.

## 8. Not in this document

As [ADR 0003](adr/0003-otel-trace-as-base.md) says, these are decided later, one at a time:

- **Edge cases** the conventions do not describe directly.
- **Transformers** that convert other formats into this one. The trace files in `research/` predate this document and use some non-standard attribute names. A transformer will convert them.
- **Prism-specific attributes.** There are none.
