# Demand: what work people bring and where it fails

Built from spans only (Atlas, Beacon, Chatly), with the session labels where stated. Ground truth is used only to score. Platforms are simulated: all numbers describe this lake, not a real company.

## Switches by origin and destination

A switch is a consecutive pair of sessions in a rebuilt task (same person, another platform, within 30 minutes, similar first prompt). A capability is missing when the destination session used it (tool, skill or MCP server in an `execute_tool` span) and no session on the origin platform in the whole lake ever did.

| Pair | Switches | Something missing | Nothing missing | Missing capability (switches) |
|---|---|---|---|---|
| Atlas -> Chatly | 3 | 0/3 (0%) small n | 3/3 (100%) small n | none |
| Beacon -> Atlas | 3 | 3/3 (100%) small n | 0/3 (0%) small n | skill: weekly-sales-report (3) |
| Beacon -> Chatly | 4 | 0/4 (0%) small n | 4/4 (100%) small n | none |
| Chatly -> Atlas | 2 | 2/2 (100%) small n | 0/2 (0%) small n | MCP server: shop (2), tool: shop__list_tables (2), tool: shop__run_sql (2), MCP server: filesystem (1), skill: customer-reply (1), skill: weekly-sales-report (1), tool: filesystem__read_file (1), tool: filesystem__search_files (1), tool: shop__search_tickets (1), tool: shop__update_ticket (1) |
| Chatly -> Beacon | 1 | 1/1 (100%) small n | 0/1 (0%) small n | MCP server: shop (1), tool: shop__search_tickets (1), tool: shop__update_ticket (1) |

- 6 of 13 rebuilt switches ended on a platform that used something the origin platform never showed. The most common gap is skill: weekly-sales-report from Beacon (3/7 (43%)).
- A gap is evidence, not proof. The destination may have used the capability only because it was there. Capabilities the origin has but never used in this two-week sample count as missing.
- Score against truth: 13/13 (100%) of the rebuilt switches leave a session whose true fate is 'switched'; 13/13 (100%) are adjacent in a true chain. The lake has 13 true switches, so the rebuild finds 100% of 13 true pairs.

## Connector and skill roadmap: what to add to the origin platform

Each row: one capability missing on the origin platform, and the number of switches from that platform that used it at the destination. Switches can appear in several rows.

| Add to | Capability | Re-dos it would address |
|---|---|---|
| Beacon | skill: weekly-sales-report | 3/7 (43%) |
| Chatly | MCP server: shop | 3/3 (100%) small n |
| Chatly | tool: shop__list_tables | 2/3 (67%) small n |
| Chatly | tool: shop__run_sql | 2/3 (67%) small n |
| Chatly | tool: shop__search_tickets | 2/3 (67%) small n |
| Chatly | tool: shop__update_ticket | 2/3 (67%) small n |
| Chatly | MCP server: filesystem | 1/3 (33%) small n |
| Chatly | skill: customer-reply | 1/3 (33%) small n |
| Chatly | skill: weekly-sales-report | 1/3 (33%) small n |
| Chatly | tool: filesystem__read_file | 1/3 (33%) small n |
| Chatly | tool: filesystem__search_files | 1/3 (33%) small n |

- 11 capability gaps in total, across 3 origin platforms.
- Counts are re-dos in this lake, not saved time. A switch with two gaps needs both added to be saved. Small rows (n < 5) are small n.

## Switches with nothing missing: what the origin session showed

Where the two platforms have the same capabilities, the origin session's last turn is classed by the trace: no answer, tool error, inability phrase, or nothing visible.

| Origin | Last turn of the origin session | Switches (of all from that origin) |
|---|---|---|
| Atlas | inability | 1/3 (33%) small n |
| Atlas | no answer | 1/3 (33%) small n |
| Atlas | nothing visible | 1/3 (33%) small n |
| Beacon | nothing visible | 2/7 (29%) |
| Beacon | tool error | 2/7 (29%) |

- 3/7 (43%) of the switches with nothing missing show no sign of trouble in the trace: the person left and the trace says nothing about why.
- Trouble signals are crude phrase and error checks on one turn. They can miss a wrong answer and flag a harmless tool error.

## Tasks that ended on trouble with no follow-up

A task counts when its last session ends on a turn with no answer, a failed tool call, or an inability phrase. The signals overlap, so the three columns can add up to more than the total. The platform is the one of the last session.

| Last platform | Tasks ending on trouble (of tasks ending there) | No answer | Tool error | Inability |
|---|---|---|---|---|
| Atlas | 9/35 (26%) | 1 | 7 | 2 |
| Beacon | 2/16 (12%) | 1 | 1 | 0 |
| Chatly | 8/13 (62%) | 0 | 0 | 8 |

| Role | Tasks ending on trouble (of the role's tasks) | No answer | Tool error | Inability |
|---|---|---|---|---|
| management | 5/16 (31%) | 0 | 1 | 4 |
| operations | 10/22 (45%) | 2 | 7 | 2 |
| support | 4/26 (15%) | 0 | 0 | 4 |

- 19/64 (30%) of tasks end on trouble. Chatly has the highest share.
- Score against truth: the estimate flags 19 tasks; 13 are truly abandoned; 9 overlap. Precision 0.4737, recall 0.6923.
- A trouble ending is a sign, not a decision to stop. Some people accept a partly wrong answer, and some leave without any trace of trouble.

## What people were asking for when the answer failed

Only no-answer and inability endings. Keywords are matched on the user text of that turn plus the session's first prompt; the first matching row wins.

| Topic | Keywords (regex) | Endings |
|---|---|---|
| ticket / customer reply | `ticket|triage|reply|customer|respond|inbox` | 5/12 (42%) |
| order / refund | `refund|return|order|\b5\d{3}\b` | 3/12 (25%) |
| stock / reorder | `stock|inventory|reorder|\b[A-Z]{3}-[A-Z]{3,5}\b` | 0/12 (0%) |
| sales / report | `sales|revenue|report|figures|net |best sell|top \d|spend` | 2/12 (17%) |
| price / margin | `price|margin|pricing|discount` | 0/12 (0%) |
| shipping / policy | `ship|deliver|policy|automate` | 1/12 (8%) |
| file / document | `file|document|save|note|memo|write|rewrite|description|draft` | 0/12 (0%) |
| other | none of the above | 1/12 (8%) |

- 12 endings with no answer or an inability phrase. The most common topic is ticket / customer reply (5).
- The lexicon is small and was built from the prompts in this lake. A different company needs its own words. Rows with fewer than 5 endings are small n.

## Demand the chat-only platform cannot serve

Per platform: turns whose reply has an inability phrase; tasks started there that were re-done on another platform or ended on trouble; sessions whose prompts name an order, ticket or SKU id or match the data-need words (order / refund, price / margin, sales / report, stock / reorder, ticket / customer reply), meaning the work needs company data.

| Platform | Turns with inability phrase | Tasks started there that were re-done or ended on trouble | Sessions needing company data |
|---|---|---|---|
| Atlas | 3/106 (3%) | 10/33 (30%) | 37/38 (97%) |
| Beacon | 0/43 (0%) | 9/22 (41%) | 23/23 (100%) |
| Chatly | 11/22 (50%) | 7/9 (78%) | 13/16 (81%) |

- On Chatly, 11/22 (50%) of turns end in an inability phrase. On Atlas it is 3/106 (3%).
- 13/16 (81%) of Chatly sessions ask for company data, which Chatly has no tools to reach.
- 7/9 (78%) of tasks started on Chatly were re-done elsewhere or ended on trouble (3 re-done). Task counts are small, so read the shares with care.
- The same scripts were played on every platform in the simulation, so these shares compare platforms on the same kind of work only if people chose the platform at random. That is not tested here.

## Label coverage and match accuracy

Labels file: 42 of 96 recordings labelled at run time. A session gets the label of the script it most resembles on its own platform. This matching step uses the script texts (not available to a real company) and stands in for labelling every session directly. 43 of 64 tasks have a label for their first session; the tables below use only those.

| Platform | Sessions with a label | Recordings in labels file | Session -> script match correct | Domain correct (recordings) | Task type correct (recordings) | Domain correct (sessions) | Task type correct (sessions) |
|---|---|---|---|---|---|---|---|
| Atlas | 38/38 (100%) | 32 | 38/38 (100%) | 28/32 (88%) | 21/32 (66%) | 35/38 (92%) | 26/38 (68%) |
| Beacon | 10/23 (43%) | 10 | 23/23 (100%) | 8/10 (80%) | 7/10 (70%) | 8/10 (80%) | 7/10 (70%) |
| Chatly | 0/16 (0%) | 0 | 15/16 (94%) | 0/0 small n | 0/0 small n | 0/0 small n | 0/0 small n |

- The matching step picks the right script for 76/77 (99%) sessions.
- Label coverage is 48/77 (62%) of sessions. If this is below 100%, rerun when the labels file is complete.
- Recording-level accuracy scores the label against the designed domain and task type. Session-level accuracy also includes match errors.

## Tasks by role and domain

Labelled tasks only (n = 43 of 64). Domain is the label of the task's first session.

| Role | operations | strategy | support | writing | Total |
|---|---|---|---|---|---|
| management | 3 | 2 | 0 | 0 | 5 |
| operations | 19 | 0 | 0 | 2 | 21 |
| support | 0 | 0 | 16 | 1 | 17 |

- The largest cell is operations / operations with 19 tasks.
- Roles have 4 staff each, so one person can shape a whole row. Cells under 5 tasks are small n.

## Tasks by task type and start platform

Labelled tasks only (n = 43).

| Task type | Atlas | Beacon | Chatly | Total |
|---|---|---|---|---|
| advise | 2 | 0 | 0 | 2 |
| analysis | 5 | 2 | 0 | 7 |
| decide | 9 | 1 | 0 | 10 |
| draft | 5 | 2 | 0 | 7 |
| lookup | 4 | 0 | 0 | 4 |
| report | 5 | 5 | 0 | 10 |
| triage | 3 | 0 | 0 | 3 |

- Task type is a label from a small model reading a compact view of the recording, not a measured fact.
- If people choose a platform by task type, this table shows it. If they choose by habit, it will look flat. The sample is too small to tell the two apart.

## Where each kind of work fails

Share of labelled tasks of each type that were re-done on another platform or ended on trouble (spans).

| Task type | Tasks | Re-done elsewhere | Ended on trouble | Either |
|---|---|---|---|---|
| advise | 2 | 0/2 (0%) small n | 0/2 (0%) small n | 0/2 (0%) small n |
| analysis | 7 | 0/7 (0%) | 2/7 (29%) | 2/7 (29%) |
| decide | 10 | 2/10 (20%) | 3/10 (30%) | 4/10 (40%) |
| draft | 7 | 0/7 (0%) | 1/7 (14%) | 1/7 (14%) |
| lookup | 4 | 0/4 (0%) small n | 2/4 (50%) small n | 2/4 (50%) small n |
| report | 10 | 4/10 (40%) | 4/10 (40%) | 5/10 (50%) |
| triage | 3 | 0/3 (0%) small n | 0/3 (0%) small n | 0/3 (0%) small n |

- Highest failure share: lookup, 2/4 (50%) small n.
- Re-done and trouble overlap, so 'Either' is not the sum of the two. Types with fewer than 5 tasks are small n.

## Are labels comparable across platforms?

The same script was recorded on all three platforms. This uses the script identity, which is ground truth: in a real company you would test it by running a set of tasks on purpose on every platform. Only scripts with the needed labels count (n shown).

| Field | Platforms | Agree | Cohen's kappa |
|---|---|---|---|
| domain | atlas-beacon | 8/10 (80%) | 0.0 |
| domain | atlas-chatly | 0/0 small n | n/a |
| domain | beacon-chatly | 0/0 small n | n/a |
| domain | all three agree | 0/0 small n |  |
| task_type | atlas-beacon | 9/10 (90%) | 0.865 |
| task_type | atlas-chatly | 0/0 small n | n/a |
| task_type | beacon-chatly | 0/0 small n | n/a |
| task_type | all three agree | 0/0 small n |  |

| Field | Platform | Label equals designed label |
|---|---|---|
| domain | Atlas | 28/32 (88%) |
| domain | Beacon | 8/10 (80%) |
| domain | Chatly | 0/0 small n |
| task_type | Atlas | 21/32 (66%) |
| task_type | Beacon | 7/10 (70%) |
| task_type | Chatly | 0/0 small n |

- Atlas-Beacon domain: 8/10 (80%) agree.
- All three agree on domain for 0/0 small n scripts and on task type for 0/0 small n.
- Kappa corrects for chance. With a few common labels and few scripts it is unstable; read it with n beside it.

## Identifiers typed into each tool

Share of sessions whose user prompts contain an order, ticket or SKU id (`base.ENT`), an email address, or a full customer name. Names come from `customer_name` fields in tool results (8 distinct names found); a name a person types that no tool ever returned is not found, and Chatly has no tools, so its names come from the other platforms' results. This counts identifiers, not sensitivity. The data has no sensitivity label.

| Platform | Order/ticket/SKU id | Email | Customer name | Any of the three |
|---|---|---|---|---|
| Atlas | 17/38 (45%) | 0/38 (0%) | 0/38 (0%) | 17/38 (45%) |
| Beacon | 5/23 (22%) | 0/23 (0%) | 0/23 (0%) | 5/23 (22%) |
| Chatly | 4/16 (25%) | 0/16 (0%) | 0/16 (0%) | 4/16 (25%) |

- 4/16 (25%) of Chatly sessions contain an order, ticket or SKU id, on the platform with no company data access.
- Across all platforms, 26/77 (34%) of sessions carry at least one identifier.
- An order id alone may be harmless; a customer's name or email is more personal. This table does not rank them.
