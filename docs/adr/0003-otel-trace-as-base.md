# 0003. The OpenTelemetry trace is the base data

- **Status:** accepted
- **Date:** 2026-11-14

## Context

Prism reads data from many AI assistants and agent harnesses. Every analysis must start from one shape of data. OpenTelemetry already defines that shape for generative AI in its [GenAI semantic conventions](https://github.com/open-telemetry/semantic-conventions-genai), and agent harnesses increasingly emit it.

## Decision

**The trace, as defined by the OpenTelemetry GenAI semantic conventions, is the base data for Prism.** Everything Prism builds is built on traces in that form. We take the conventions as they are and do not add our own attributes yet.

A **span** is one operation. It has a `trace_id`, `span_id`, `parent_span_id`, name, start and end time, status and attributes. A **trace** is all the spans with the same `trace_id`, joined by their parent links into a tree. For an agent, a trace looks like this:

```
trace
└─ invoke_agent {agent}            an agent run
   ├─ chat {model}                 a model call
   ├─ execute_tool {tool}          a tool call
   ├─ chat {model}
   ├─ execute_tool {tool}
   └─ chat {model}                 the final answer
```

The span types and attributes we start from, all defined by OpenTelemetry:

| Span | `gen_ai.operation.name` | Main attributes |
|------|------------------------|-----------------|
| Agent run | `invoke_agent` | `gen_ai.agent.name`, `gen_ai.conversation.id` |
| Model call | `chat` (or `generate_content`, `text_completion`) | `gen_ai.provider.name`, `gen_ai.request.model`, `gen_ai.response.model`, `gen_ai.usage.input_tokens`, `gen_ai.usage.output_tokens`, `gen_ai.response.finish_reasons` |
| Tool call | `execute_tool` | `gen_ai.tool.name`, `gen_ai.tool.call.id`, `gen_ai.tool.type`; for skills `gen_ai.skill.name`; for commands `process.executable.name`, `process.exit.code` |
| All | | `error.type` when the operation failed. Content (`gen_ai.input.messages`, `gen_ai.output.messages`, `gen_ai.tool.call.arguments`, `gen_ai.tool.call.result`) when the source records it |

Conversation and user are attributes on the spans (`gen_ai.conversation.id`, `user.id`), not separate structures. Grouping traces by them is something we build on top of traces later.

We pin the conventions at commit `e6658f1` (6 November 2026). They are still at *Development* status, so a newer version is adopted on purpose, not automatically.

## What we defer

- **Edge cases**, where a source does something the conventions do not describe directly: for example, a harness that loads a skill by reading `SKILL.md` with its ordinary file tool, or a model provider that runs code inside the model call. We decide each one when we meet it in real data.
- **Sources in other formats**, or sources that use the conventions differently: we handle them with **transformers** that convert them into this form. Prism itself reads only OpenTelemetry GenAI traces.
- **Prism-specific attributes**: none for now. We add one only when a real analysis needs something the conventions cannot express, and we record that in an ADR.

## Consequences

- One input format. A new source needs a transformer, not changes to Prism.
- Prism follows the OpenTelemetry vocabulary, so harnesses that already emit it work without a transformer.
- What a source does not record cannot be analysed. Gaps become visible as we meet real data, and each one gets its own decision.
- [ADR 0002](0002-session-level-extraction-from-traces.md) (proposed) stays a proposal for how analysis works on top of these traces.
