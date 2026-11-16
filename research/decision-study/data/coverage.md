# Coverage: which decisions the traces can answer

Computed from 1062 spans in `data/lake_otel.jsonl` and `catalogue.json` by `coverage.py`. Shares are the spans of the needed type that carry the attribute with a non-empty value. No ground truth is used.

Verdict rule:

- `ready`: every non-optional need is on at least 99% of its spans and every external input is available.
- `blocked`: a non-optional need is absent (below 1% of its spans, or the platform has no spans of that type), or a required external input is not available.
- `partial`: anything else, i.e. a non-optional need is on 1% to 99% of its spans, or only optional needs fall short.
- An optional need on a platform with no spans of its type is not applicable and does not count.
- A need marked `when: ok` is measured only on spans that did not fail: a failed model call has no tokens and a failed turn has no reply.

## Verdict per decision and platform

| Decision | Unit | Basis | Atlas | Beacon | Chatly | What is missing |
|---|---|---|---|---|---|---|
| D1 Which seats do we pay for? | task | linked | ready | ready | ready | nothing |
| D2 What work goes to AI? | task | labelled | ready | ready | ready | nothing |
| D3 Which tool for which job? | task | checked | blocked | blocked | blocked | external: sampled checks of answers (people or evaluators) not available<br>Atlas: event `gen_ai.evaluation.result`: absent 0% (0/660)<br>Beacon: event `gen_ai.evaluation.result`: absent 0% (0/358)<br>Chatly: event `gen_ai.evaluation.result`: absent 0% (0/44) |
| D4 What do we build next: skills, connectors, context? | task | linked | partial | partial | blocked | Atlas: execute_tool `error.type` (optional): partial 8.2% (19/232)<br>Atlas: execute_tool `gen_ai.skill.name` (optional): partial 16.8% (39/232)<br>Beacon: execute_tool `error.type` (optional): partial 5.4% (9/167)<br>Beacon: execute_tool `gen_ai.skill.name` (optional): absent 0% (0/167)<br>Chatly: execute_tool `gen_ai.tool.name`: no execute_tool spans on this platform |
| D5 Where does sensitive work go? | session | labelled | blocked | blocked | blocked | external: sensitivity policy and label not available |
| D6 How do I work with AI? | session | labelled | ready | ready | ready | nothing |

What the evidence must show before a card may say "act" (the bar):

- D1: The chance of seeing this few task starts on the seat, if the holder really used it for 10% of their tasks, is under 5%
- D2: The label agrees with a reference set (kappa 0.6 or more), and every group shown is at or above the minimum group size
- D3: The interval of the difference in correct answers between two platforms excludes zero, with the task (not the turn) as the unit
- D4: The same missing capability shows in at least 5 tasks that were re-done or ended on trouble
- D5: A sensitivity label with measured agreement exists, and every group shown is at or above the minimum group size
- D6: None: the report goes to the person, who judges it

- 9 of 18 decision-platform cells are ready, 2 partial and 7 blocked.
- Ready: D1 on Atlas, D1 on Beacon, D1 on Chatly, D2 on Atlas, D2 on Beacon, D2 on Chatly, D6 on Atlas, D6 on Beacon, D6 on Chatly.
- 2 decisions (D3, D5) are blocked on every platform by an input that is not in any trace: D3 needs sampled checks of answers (people or evaluators); D5 needs sensitivity policy and label.
- D4 on Chatly: blocked because the platform has no spans of a needed type. This is a missing capability (no tools), not lost data.
- Non-optional needs below 99%: none.
- D4 on Atlas, D4 on Beacon: partial only because an optional need falls short.

## Share of spans that carry each need

For needs measured on spans that did not fail, the share over all spans is in brackets; the verdict uses the first figure.

| Where | Attribute | Measured on | Read by (* optional) | Atlas | Beacon | Chatly |
|---|---|---|---|---|---|---|
| invoke_agent | `user.id` | all spans | D1, D2, D3, D4, D6 | 100% (106/106) | 100% (43/43) | 100% (22/22) |
| invoke_agent | `gen_ai.conversation.id` | all spans | D1, D2, D3, D4, D6 | 100% (106/106) | 100% (43/43) | 100% (22/22) |
| resource | `service.name` | all spans | D1, D2, D3, D4, D5, D6* | 100% (660/660) | 100% (358/358) | 100% (44/44) |
| invoke_agent | `gen_ai.input.messages` | all spans | D1*, D2, D3, D4, D5, D6 | 100% (106/106) | 100% (43/43) | 100% (22/22) |
| invoke_agent | `gen_ai.output.messages` | spans that did not fail | D2, D4, D6 | 100% (104/104) [all spans: 98.1% (104/106)] | 100% (40/40) [all spans: 93.0% (40/43)] | 100% (22/22) |
| execute_tool | `gen_ai.tool.name` | all spans | D2*, D4, D6* | 100% (232/232) | 100% (167/167) | no such spans |
| event | `gen_ai.evaluation.result` | all spans | D3 | 0% (0/660) | 0% (0/358) | 0% (0/44) |
| chat | `gen_ai.usage.input_tokens` | spans that did not fail | D3 | 100% (309/309) [all spans: 98.8% (318/322)] | 100% (148/148) | 100% (22/22) |
| chat | `gen_ai.usage.output_tokens` | spans that did not fail | D3 | 100% (309/309) [all spans: 98.8% (318/322)] | 100% (148/148) | 100% (22/22) |
| chat | `gen_ai.response.model` | spans that did not fail | D3 | 100% (309/309) [all spans: 98.8% (318/322)] | 100% (148/148) | 100% (22/22) |
| execute_tool | `gen_ai.skill.name` | all spans | D4* | 16.8% (39/232) | 0% (0/167) | no such spans |
| execute_tool | `error.type` | all spans | D4* | 8.2% (19/232) | 5.4% (9/167) | no such spans |
| execute_tool | `gen_ai.tool.call.arguments` | all spans | D5* | 100% (232/232) | 100% (167/167) | no such spans |

- 10 of 13 needs are on 100% of their spans wherever the span type exists.
- 5 turns have no reply, and 5 of them are failed turns. 4 of the 4 chat spans without tokens are failed requests. A failed request may still be billed, so cost from tokens can be a little low.
- `error.type` is set on 19 of 19 failed tool spans on Atlas, 9 of 9 failed tool spans on Beacon. It belongs only on failures, so its low share over all tool spans is not a gap; the same holds for `gen_ai.skill.name`, which belongs only on load_skill calls. Both are optional, but they still make D4 partial under the rule.
- `gen_ai.evaluation.result` is on 0 spans: the spans carry no events at all, so no checked outcome reaches the traces.
- Chatly has 0 tool spans, so tool and skill needs do not apply there; they are a capability it lacks.

## What survives when content is off

The same rule, as if the opt-in content attributes (`gen_ai.input.messages`, `gen_ai.output.messages`, `gen_ai.system_instructions`, `gen_ai.tool.call.arguments`, `gen_ai.tool.call.result`, `gen_ai.tool.definitions`) were absent on every platform.

| Decision | Atlas (with content → without) | Beacon (with content → without) | Chatly (with content → without) | What is lost without content |
|---|---|---|---|---|
| D1 Which seats do we pay for? | ready → partial | ready → partial | ready → partial | link a re-ask to its first session, so a fallback is not counted as a task start (optional) |
| D2 What work goes to AI? | ready → blocked | ready → blocked | ready → blocked | what the person asked; the visible reply, for the compact view |
| D3 Which tool for which job? | blocked → blocked | blocked → blocked | blocked → blocked | task type, through the label |
| D4 What do we build next: skills, connectors, context? | partial → blocked | partial → blocked | blocked → blocked | link a re-ask to its first session; no answer, or an inability phrase |
| D5 Where does sensitive work go? | blocked → blocked | blocked → blocked | blocked → blocked | what was typed into the tool; what the agent sent to tools (optional) |
| D6 How do I work with AI? | ready → blocked | ready → blocked | ready → blocked | what the person asked; the visible reply |

- Without content, 0 of 18 cells are ready, 3 partial and 15 blocked (with content: 9, 2, 7).
- Still ready somewhere without content: none. Blocked everywhere only because content is off: D2, D4, D6.
- D1 needs content only to link a re-ask to its first session. Without it, task starts fall back to session starts, which counts a fallback as new use.
- A company that will not record content can still count use per seat, but not say what the work was or why it failed.

## What the schema could not carry

From `data/conformance.json`. Counts are spans changed by the transformer.

| Action | Item | Atlas | Beacon | Chatly |
|---|---|---|---|---|
| renamed | finish reason tool_calls -> tool_call | 205 |  |  |
| renamed | gen_ai.usage.cached_tokens -> gen_ai.usage.cache_read.input_tokens | 168 |  |  |
| renamed | gen_ai.usage.reasoning_tokens -> gen_ai.usage.reasoning.output_tokens | 274 |  |  |
| restructured | gen_ai.input.text -> gen_ai.input.messages | 106 | 43 | 22 |
| restructured | gen_ai.output.text (+ tool_calls) -> gen_ai.output.messages | 413 | 188 | 44 |
| inferred | finish_reason of the output message | 104 | 188 | 44 |
| inferred | gen_ai.skill.name from the load_skill arguments | 39 |  |  |
| inferred | mcp.method.name from the tool-name prefix | 189 | 167 |  |
| dropped | gen_ai.usage.cost | 318 |  |  |
| dropped | http.status_code | 322 |  |  |
| dropped | mcp.server.name | 228 | 167 |  |
| dropped | session.turn_index | 106 | 43 | 22 |
| moved_to_resource | platform -> resource service.name | 660 | 358 | 44 |
| required missing | gen_ai.provider.name on chat spans | 4 of 322 | 148 of 148 | 22 of 22 |

- 4 source attributes were dropped because the conventions have no name for them: `gen_ai.usage.cost` (318 spans), `http.status_code` (322 spans), `mcp.server.name` (395 spans), `session.turn_index` (171 spans).
- 731 values were inferred, not read: finish_reason of the output message (336), gen_ai.skill.name from the load_skill arguments (39), mcp.method.name from the tool-name prefix (356).
- A Required attribute is missing on 4 of 322 Atlas chat spans, 148 of 148 Beacon chat spans, 22 of 22 Chatly chat spans. Where it is missing, the spans do not conform, whatever the analyses need.
- 2476 of the changes fall on Atlas, 944 on Beacon and 154 on Chatly (not counting the platform moved to the resource).

## Which decisions each gap affects

'catalogue' means the decision lists the attribute in its needs. 'judgment' is this script's reading and should be checked.

| Item | Action | Platforms | Decisions | Basis | Note |
|---|---|---|---|---|---|
| finish reason tool_calls -> tool_call | renamed | Atlas | none of the six | catalogue | no decision reads this attribute |
| gen_ai.usage.cached_tokens -> gen_ai.usage.cache_read.input_tokens | renamed | Atlas | none of the six | catalogue | no decision reads this attribute |
| gen_ai.usage.reasoning_tokens -> gen_ai.usage.reasoning.output_tokens | renamed | Atlas | none of the six | catalogue | no decision reads this attribute |
| gen_ai.input.text -> gen_ai.input.messages | restructured | Atlas, Beacon, Chatly | D1, D2, D3, D4, D5, D6 | catalogue | decisions that read this attribute |
| gen_ai.output.text (+ tool_calls) -> gen_ai.output.messages | restructured | Atlas, Beacon, Chatly | D2, D4, D6 | catalogue | decisions that read this attribute |
| finish_reason of the output message | inferred | Atlas, Beacon, Chatly | none of the six | judgment | no decision reads the finish reason; only the text and tool calls are read |
| gen_ai.skill.name from the load_skill arguments | inferred | Atlas | D4 | catalogue | decisions that read this attribute |
| mcp.method.name from the tool-name prefix | inferred | Atlas, Beacon | none of the six | judgment | no decision reads the MCP method |
| gen_ai.usage.cost | dropped | Atlas | D3 | judgment | cost is recomputed from tokens and a price table (base.cost), so it is a shadow cost, not a bill |
| http.status_code | dropped | Atlas | none of the six | judgment | error.type carries the failure class |
| mcp.server.name | dropped | Atlas, Beacon | D4 | judgment | the server is read back from the `server__tool` prefix (base.server_of); D4 groups missing capabilities by it |
| session.turn_index | dropped | Atlas, Beacon, Chatly | D1, D2, D3, D4, D5, D6 | judgment | derivable: order of the root spans of one conversation by start time |
| platform -> resource service.name | moved_to_resource | Atlas, Beacon, Chatly | D1, D2, D3, D4, D5, D6 | catalogue | decisions that read this attribute |
| gen_ai.provider.name on chat spans | required missing | Atlas, Beacon, Chatly | none of the six | judgment | none of the six decisions reads the provider; the model name is enough for price |

- 4 dropped, inferred or missing items touch a decision: `gen_ai.skill.name from the load_skill arguments` → D4; `gen_ai.usage.cost` → D3; `mcp.server.name` → D4; `session.turn_index` → D1, D2, D3, D4, D5, D6.
- Each of those has a workaround from the spans: cost from tokens and a price table, the MCP server from the tool-name prefix, turn order from start times, the skill from the load_skill arguments.
- The workarounds are conventions of this harness. Another vendor may name tools or skills differently, and then D3 cost and D4 lose them.
