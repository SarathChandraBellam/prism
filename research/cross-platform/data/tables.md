## Setup

| Item | Value |
|---|---|
| Task instances drawn / in scope | 64 / 52 |
| Scripts in scope / pending | 26 / 6 (M08, M09, M10, M11, M12, M13) |
| Sessions in the lake | 64 |
| Sessions per platform | Atlas 29, Beacon 20, Chatly 15 |
| User turns | 144 |
| Task starts per platform | Atlas 24, Beacon 19, Chatly 9 |
| Seats / monthly spend | 24 / 570 |
| Tasks with a switch / with two switches | 12 / 0 |
| Tasks that ended abandoned | 12 |
| Sessions where the user noticed the first failed turn | 24 of 33 sessions with a failed turn (the roll is made once per session, at the first failed turn) |

## Q1. Fidelity

| Platform | Source | sessions | turns | requests | failed_requests | tool_calls | tool_errors | tokens_in | tokens_out |
|---|---|---|---|---|---|---|---|---|---|
| Atlas | recording | 29 | 85 | 258 | 11 | 187 | 17 | 1,202,908 | 74,331 |
| Atlas | export | 29 | 85 | 258 | 11 | 187 | 17 | 1,202,908 | 74,331 |
| Atlas | lake | 29 | 85 | 258 | 11 | 187 | 17 | 1,202,908 | 74,331 |
| Beacon | recording | 20 | 38 | 133 | 0 | 152 | 9 | 646,631 | 29,274 |
| Beacon | export | 20 | 38 | 133 | 0 | 152 | 9 | 646,631 | 29,274 |
| Beacon | lake | 20 | 38 | 133 | 0 | 152 | 9 | 646,631 | 29,274 |
| Chatly | recording | 15 | 21 | 21 | 0 | 0 | 0 | 6,447 | 7,725 |
| Chatly | export | 15 | 21 | 21 | 0 | 0 | 0 | 6,447 | 7,725 |
| Chatly | lake | 15 | 21 | 21 | 0 | 0 | 0 | 6,447 | 7,725 |

All three columns equal for every platform and field: True

Chatly recording: 85 turns, 85 attempts, 0 failed attempts, 0 turns without a reply, 11 different models

## Q2. Switch detection

Candidates 20, true pairs 12 (adjacent 12), window 30 minutes

| Method | Predicted pairs | TP | Precision | Recall | F1 | Setting |
|---|---|---|---|---|---|---|
| a. Time window only | 20 | 12 | 0.60 | 1.00 | 0.75 |  |
| b2. + word overlap of whole sessions (not in brief) | 14 | 12 | 0.86 | 1.00 | 0.92 | threshold 0.05 |
| b. + word overlap of first prompts | 13 | 12 | 0.92 | 1.00 | 0.96 | threshold 0.1 |
| c. + shared order, ticket or SKU ids | 3 | 3 | 1.00 | 0.25 | 0.40 |  |
| c2. ids or word overlap | 13 | 12 | 0.92 | 1.00 | 0.96 |  |
| e. Best combination | 13 | 12 | 0.92 | 1.00 | 0.96 | tau 0.1, signals jac+ent, k=1, nearest only=False |

| Jaccard threshold | Precision | Recall | F1 |
|---|---|---|---|
| 0.00 | 0.60 | 1.00 | 0.75 |
| 0.05 | 0.92 | 1.00 | 0.96 |
| 0.10 | 0.92 | 1.00 | 0.96 |
| 0.20 | 1.00 | 0.75 | 0.86 |
| 0.30 | 1.00 | 0.58 | 0.74 |
| 0.40 | 1.00 | 0.42 | 0.59 |
| 0.50 | 1.00 | 0.33 | 0.50 |
| 0.60 | 1.00 | 0.08 | 0.15 |

Paraphrase: 12 switch sessions, 12 paraphrased; median Jaccard of first prompts true pairs 0.308, false pairs 0.0; true pairs sharing an id 3 of 12
Counterfactual with the original prompt re-pasted (threshold 0.1): precision 0.923, recall 1.0, F1 0.96
Label lookup by text: script matched in 63 of 64 sessions; sessions with a label 0

## Q3. Proxies

| Platform | Sessions | Turns | Verifiable turns | Correct (checks) | No answer | Switch-away | Abandonment | Tool error | Failed request | Composite |
|---|---|---|---|---|---|---|---|---|---|---|
| Atlas | 29 | 85 | 64 | 91% | 2% | 10% | 28% | 15% | 4% | 0.120 |
| Beacon | 20 | 38 | 32 | 56% | 8% | 30% | 10% | 16% | 0% | 0.127 |
| Chatly | 15 | 21 | 17 | 24% | 0% | 27% | 47% | 0% | 0% | 0.147 |

Session-level flags against the replay: abandonment precision 0.471, recall 0.667 (tp 8, fp 9, fn 4); switch-away precision 0.923, recall 1.0

### Cut: designed_task_type

| Group | Platform | Sessions | Verifiable turns | Correct (checks) | Composite |
|---|---|---|---|---|---|
| analysis | Atlas | 7 | 13 | 92% | 0.124 |
| analysis | Beacon | 6 | 11 | 73% | 0.049 |
| decide | Atlas | 4 | 12 | 83% | 0.129 |
| decide | Chatly | 3 | 3 | 0% | 0.067 |
| lookup | Atlas | 5 | 10 | 100% | 0.140 |
| lookup | Chatly | 3 | 3 | 0% | 0.200 |
| report | Atlas | 8 | 19 | 84% | 0.186 |
| report | Beacon | 5 | 5 | 0% | 0.160 |

| Group | Best by checks | Best by proxy | Match |
|---|---|---|---|
| analysis | Atlas | Beacon | no |
| decide | Atlas | Chatly | no |
| lookup | Atlas | Atlas | yes |
| report | Atlas | Beacon | no |

Cells 8, Spearman composite vs checks 0.073; groups matching 1 of 4; pairs concordant 1 of 4; single proxies {'abandonment': -0.466, 'failed_request': -0.495, 'no_answer': 0.117, 'switch_away': 0.765, 'tool_error': -0.884}

Cut labelled_domain: pending (labels)

## Q4. Seats

| Holder | Seat | Price | Sessions | Share of holder's sessions | Task starts | Last use | Flag |
|---|---|---|---|---|---|---|---|
| priya | Atlas | 30 | 3 | 60% | 2 | 2026-11-11 |  |
| priya | Chatly | 20 | 2 | 40% | 1 | 2026-11-11 |  |
| tomas | Atlas | 30 | 3 | 100% | 3 | 2026-11-04 |  |
| hana | Atlas | 30 | 3 | 100% | 3 | 2026-11-10 |  |
| hana | Beacon | 20 | 0 | 0% | 0 | never | yes |
| hana | Chatly | 20 | 0 | 0% | 0 | never | yes |
| jonas | Beacon | 20 | 5 | 56% | 3 | 2026-11-13 |  |
| jonas | Chatly | 20 | 4 | 44% | 1 | 2026-11-13 |  |
| kofi | Atlas | 30 | 7 | 58% | 4 | 2026-11-11 |  |
| kofi | Beacon | 20 | 5 | 42% | 5 | 2026-11-13 |  |
| lucia | Beacon | 20 | 6 | 100% | 6 | 2026-11-10 |  |
| dmitri | Atlas | 30 | 6 | 75% | 6 | 2026-11-09 |  |
| dmitri | Chatly | 20 | 2 | 25% | 0 | 2026-11-04 |  |
| ines | Atlas | 30 | 1 | 100% | 1 | 2026-11-03 |  |
| ines | Beacon | 20 | 0 | 0% | 0 | never | yes |
| ines | Chatly | 20 | 0 | 0% | 0 | never | yes |
| rosa | Chatly | 20 | 1 | 25% | 1 | 2026-11-05 |  |
| rosa | Atlas | 30 | 3 | 75% | 2 | 2026-11-05 |  |
| omar | Chatly | 20 | 6 | 100% | 6 | 2026-11-13 |  |
| freya | Atlas | 30 | 3 | 100% | 3 | 2026-11-09 |  |
| freya | Beacon | 20 | 0 | 0% | 0 | never | yes |
| freya | Chatly | 20 | 0 | 0% | 0 | never | yes |
| ben | Beacon | 20 | 4 | 100% | 4 | 2026-11-06 |  |
| ben | Atlas | 30 | 0 | 0% | 0 | never | yes |

| Rule | Flagged | Saving per month | Designed idle seats | TP | FP | FN | Precision | Recall |
|---|---|---|---|---|---|---|---|---|
| under 10% of sessions | 7 | 150 | 4 | 3 | 4 | 1 | 0.43 | 0.75 |
| under 10% of task starts | 8 | 170 | 4 | 4 | 4 | 0 | 0.50 | 1.00 |

Designed idle saving 90 per month of 570; single-seat users 3

## Q5. Routing

| Task type | Scripts | Verifiable turns | Atlas correct | Beacon correct | Chatly correct | Atlas $/1k turns | Beacon $/1k turns | Chatly $/1k turns | Best |
|---|---|---|---|---|---|---|---|---|---|
| advise | 3 | 4 | 100% | 50% | 25% | 9.15 | 9.92 | 0.77 | Atlas |
| analysis | 7 | 15 | 87% | 73% | 13% | 7.01 | 5.75 | 0.46 | Atlas |
| decide | 3 | 9 | 89% | 11% | 11% | 3.14 | 7.02 | 0.31 | Atlas |
| draft | 3 | 7 | 100% | 71% | 57% | 3.73 | 4.41 | 0.48 | Atlas |
| lookup | 4 | 9 | 100% | 78% | 11% | 7.29 | 5.15 | 0.36 | Atlas |
| report | 5 | 16 | 69% | 19% | 0% | 5.83 | 8.19 | 0.43 | Atlas |
| triage | 1 | 3 | 100% | 33% | 33% | 5.98 | 3.94 | 1.20 | Atlas |

| Policy | Tasks | Verifiable turns | Correct | Pass rate | Shadow cost (USD) | Cost per task |
|---|---|---|---|---|---|---|
| actual | 52 | 126 | 77 | 61% | 0.760 | 0.0146 |
| routed | 52 | 126 | 110 | 87% | 1.067 | 0.0205 |
| routed_loo | 52 | 126 | 110 | 87% | 1.067 | 0.0205 |
| start_only | 52 | 126 | 80 | 64% | 0.899 | 0.0173 |

| Role | Actual pass | Start-only pass | Routed pass |
|---|---|---|---|
| support | 62% | 69% | 95% |
| operations | 56% | 61% | 74% |
| management | 70% | 60% | 100% |

| Platform | Recordings: correct | Verifiable | Pass rate | Shadow $ per 1k turns | Shadow $ per correct verifiable turn |
|---|---|---|---|---|---|
| Atlas | 55 | 63 | 87% | 6.28 | 0.0097 |
| Beacon | 30 | 63 | 48% | 6.73 | 0.0191 |
| Chatly | 10 | 63 | 16% | 0.51 | 0.0043 |

Chatly verifiable turns in scope: text-only checks 55 (passed 10), with a state check 8 (failed by construction)
