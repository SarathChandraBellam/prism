## Setup

| Item | Value |
|---|---|
| Task instances drawn / in scope | 64 / 64 |
| Scripts in scope / pending | 32 / 0 () |
| Sessions in the lake | 77 |
| Sessions per platform | Atlas 38, Beacon 23, Chatly 16 |
| User turns | 171 |
| Task starts per platform | Atlas 33, Beacon 22, Chatly 9 |
| Seats / monthly spend | 24 / 570 |
| Tasks with a switch / with two switches | 13 / 0 |
| Tasks that ended abandoned | 13 |
| Sessions where the user noticed the first failed turn | 26 of 37 sessions with a failed turn (the roll is made once per session, at the first failed turn) |

## Q1. Fidelity

| Platform | Source | sessions | turns | requests | failed_requests | tool_calls | tool_errors | tokens_in | tokens_out |
|---|---|---|---|---|---|---|---|---|---|
| Atlas | recording | 38 | 106 | 322 | 13 | 232 | 19 | 1,495,276 | 88,985 |
| Atlas | export | 38 | 106 | 322 | 13 | 232 | 19 | 1,495,276 | 88,985 |
| Atlas | lake | 38 | 106 | 322 | 13 | 232 | 19 | 1,495,276 | 88,985 |
| Beacon | recording | 23 | 43 | 148 | 0 | 167 | 9 | 707,085 | 33,216 |
| Beacon | export | 23 | 43 | 148 | 0 | 167 | 9 | 707,085 | 33,216 |
| Beacon | lake | 23 | 43 | 148 | 0 | 167 | 9 | 707,085 | 33,216 |
| Chatly | recording | 16 | 22 | 22 | 0 | 0 | 0 | 6,592 | 7,934 |
| Chatly | export | 16 | 22 | 22 | 0 | 0 | 0 | 6,592 | 7,934 |
| Chatly | lake | 16 | 22 | 22 | 0 | 0 | 0 | 6,592 | 7,934 |

All three columns equal for every platform and field: True

Chatly recording: 100 turns, 100 attempts, 0 failed attempts, 0 turns without a reply, 11 different models

## Q2. Switch detection

Candidates 30, true pairs 13 (adjacent 13), window 30 minutes

| Method | Predicted pairs | TP | Precision | Recall | F1 | Setting |
|---|---|---|---|---|---|---|
| a. Time window only | 30 | 13 | 0.43 | 1.00 | 0.60 |  |
| b2. + word overlap of whole sessions (not in brief) | 11 | 11 | 1.00 | 0.85 | 0.92 | threshold 0.1 |
| b. + word overlap of first prompts | 13 | 13 | 1.00 | 1.00 | 1.00 | threshold 0.1 |
| c. + shared order, ticket or SKU ids | 4 | 4 | 1.00 | 0.31 | 0.47 |  |
| c2. ids or word overlap | 13 | 13 | 1.00 | 1.00 | 1.00 |  |
| d. + same labelled domain and task type | 10 | 8 | 0.80 | 0.61 | 0.70 |  |
| e. Best combination | 13 | 13 | 1.00 | 1.00 | 1.00 | tau 0.1, signals jac+ent, k=1, nearest only=False |

| Jaccard threshold | Precision | Recall | F1 |
|---|---|---|---|
| 0.00 | 0.43 | 1.00 | 0.60 |
| 0.05 | 0.81 | 1.00 | 0.90 |
| 0.10 | 1.00 | 1.00 | 1.00 |
| 0.20 | 1.00 | 0.77 | 0.87 |
| 0.30 | 1.00 | 0.61 | 0.76 |
| 0.40 | 1.00 | 0.39 | 0.56 |
| 0.50 | 1.00 | 0.31 | 0.47 |
| 0.60 | 1.00 | 0.08 | 0.14 |

Paraphrase: 13 switch sessions, 13 paraphrased; median Jaccard of first prompts true pairs 0.308, false pairs 0.0; true pairs sharing an id 4 of 13
Counterfactual with the original prompt re-pasted (threshold 0.1): precision 0.867, recall 1.0, F1 0.929
Label lookup by text: script matched in 76 of 77 sessions; sessions with a label 77

## Q3. Proxies

| Platform | Sessions | Turns | Verifiable turns | Correct (checks) | No answer | Switch-away | Abandonment | Tool error | Failed request | Composite |
|---|---|---|---|---|---|---|---|---|---|---|
| Atlas | 38 | 106 | 82 | 90% | 2% | 8% | 24% | 14% | 4% | 0.103 |
| Beacon | 23 | 43 | 34 | 56% | 7% | 30% | 9% | 14% | 0% | 0.120 |
| Chatly | 16 | 22 | 18 | 22% | 0% | 19% | 50% | 0% | 0% | 0.138 |

Session-level flags against the replay: abandonment precision 0.474, recall 0.692 (tp 9, fp 10, fn 4); switch-away precision 1.0, recall 1.0

### Cut: designed_task_type

| Group | Platform | Sessions | Verifiable turns | Correct (checks) | Composite |
|---|---|---|---|---|---|
| analysis | Atlas | 7 | 13 | 92% | 0.124 |
| analysis | Beacon | 6 | 11 | 73% | 0.049 |
| decide | Atlas | 6 | 16 | 75% | 0.121 |
| decide | Chatly | 3 | 3 | 0% | 0.000 |
| draft | Atlas | 3 | 4 | 100% | 0.000 |
| draft | Beacon | 3 | 5 | 80% | 0.117 |
| lookup | Atlas | 10 | 21 | 100% | 0.069 |
| lookup | Beacon | 3 | 7 | 86% | 0.095 |
| lookup | Chatly | 3 | 3 | 0% | 0.200 |
| report | Atlas | 8 | 19 | 84% | 0.186 |
| report | Beacon | 5 | 5 | 0% | 0.160 |

| Group | Best by checks | Best by proxy | Match |
|---|---|---|---|
| analysis | Atlas | Beacon | no |
| decide | Atlas | Chatly | no |
| draft | Atlas | Atlas | yes |
| lookup | Atlas | Atlas | yes |
| report | Atlas | Beacon | no |

Cells 11, Spearman composite vs checks 0.279; groups matching 2 of 5; pairs concordant 4 of 7; single proxies {'abandonment': -0.012, 'failed_request': -0.216, 'no_answer': 0.245, 'switch_away': 0.338, 'tool_error': -0.389}

### Cut: labelled_domain

| Group | Platform | Sessions | Verifiable turns | Correct (checks) | Composite |
|---|---|---|---|---|---|
| operations | Atlas | 18 | 35 | 89% | 0.166 |
| operations | Beacon | 9 | 14 | 57% | 0.114 |
| operations | Chatly | 4 | 4 | 0% | 0.200 |
| support | Atlas | 17 | 44 | 91% | 0.059 |
| support | Beacon | 9 | 14 | 57% | 0.158 |
| support | Chatly | 9 | 9 | 0% | 0.133 |
| writing | Beacon | 4 | 5 | 60% | 0.025 |

| Group | Best by checks | Best by proxy | Match |
|---|---|---|---|
| operations | Atlas | Beacon | no |
| support | Atlas | Atlas | yes |

Cells 7, Spearman composite vs checks 0.455; groups matching 1 of 2; pairs concordant 4 of 6; single proxies {'abandonment': 0.44, 'failed_request': -0.771, 'no_answer': -0.181, 'switch_away': 0.582, 'tool_error': -0.547}

## Q4. Seats

| Holder | Seat | Price | Sessions | Share of holder's sessions | Task starts | Last use | Flag |
|---|---|---|---|---|---|---|---|
| priya | Atlas | 30 | 4 | 67% | 3 | 2026-11-05 |  |
| priya | Chatly | 20 | 2 | 33% | 1 | 2026-11-05 |  |
| tomas | Atlas | 30 | 9 | 100% | 9 | 2026-11-10 |  |
| hana | Atlas | 30 | 5 | 83% | 5 | 2026-11-10 |  |
| hana | Beacon | 20 | 1 | 17% | 1 | 2026-11-03 |  |
| hana | Chatly | 20 | 0 | 0% | 0 | never | yes |
| jonas | Beacon | 20 | 7 | 58% | 6 | 2026-11-13 |  |
| jonas | Chatly | 20 | 5 | 42% | 1 | 2026-11-12 |  |
| kofi | Atlas | 30 | 7 | 58% | 4 | 2026-11-11 |  |
| kofi | Beacon | 20 | 5 | 42% | 5 | 2026-11-11 |  |
| lucia | Beacon | 20 | 6 | 100% | 6 | 2026-11-09 |  |
| dmitri | Atlas | 30 | 6 | 75% | 6 | 2026-11-09 |  |
| dmitri | Chatly | 20 | 2 | 25% | 0 | 2026-11-04 |  |
| ines | Atlas | 30 | 1 | 100% | 1 | 2026-11-04 |  |
| ines | Beacon | 20 | 0 | 0% | 0 | never | yes |
| ines | Chatly | 20 | 0 | 0% | 0 | never | yes |
| rosa | Chatly | 20 | 1 | 25% | 1 | 2026-11-12 |  |
| rosa | Atlas | 30 | 3 | 75% | 2 | 2026-11-12 |  |
| omar | Chatly | 20 | 6 | 100% | 6 | 2026-11-13 |  |
| freya | Atlas | 30 | 3 | 100% | 3 | 2026-11-09 |  |
| freya | Beacon | 20 | 0 | 0% | 0 | never | yes |
| freya | Chatly | 20 | 0 | 0% | 0 | never | yes |
| ben | Beacon | 20 | 4 | 100% | 4 | 2026-11-06 |  |
| ben | Atlas | 30 | 0 | 0% | 0 | never | yes |

| Rule | Flagged | Saving per month | Designed idle seats | TP | FP | FN | Precision | Recall |
|---|---|---|---|---|---|---|---|---|
| under 10% of sessions | 6 | 130 | 4 | 3 | 3 | 1 | 0.50 | 0.75 |
| under 10% of task starts | 7 | 150 | 4 | 4 | 3 | 0 | 0.57 | 1.00 |

Designed idle saving 90 per month of 570; single-seat users 3

## Q5. Routing

| Task type | Scripts | Verifiable turns | Atlas correct | Beacon correct | Chatly correct | Atlas $/1k turns | Beacon $/1k turns | Chatly $/1k turns | Best |
|---|---|---|---|---|---|---|---|---|---|
| advise | 3 | 4 | 100% | 50% | 25% | 9.15 | 9.92 | 0.77 | Atlas |
| analysis | 7 | 15 | 87% | 73% | 13% | 7.01 | 5.75 | 0.46 | Atlas |
| decide | 4 | 12 | 83% | 17% | 8% | 3.24 | 6.21 | 0.31 | Atlas |
| draft | 4 | 7 | 100% | 71% | 57% | 3.27 | 4.00 | 0.59 | Atlas |
| lookup | 7 | 15 | 100% | 87% | 7% | 6.81 | 5.16 | 0.28 | Atlas |
| report | 5 | 16 | 69% | 19% | 0% | 5.83 | 8.19 | 0.43 | Atlas |
| triage | 2 | 6 | 100% | 17% | 33% | 6.41 | 5.73 | 0.91 | Atlas |

| Policy | Tasks | Verifiable turns | Correct | Pass rate | Shadow cost (USD) | Cost per task |
|---|---|---|---|---|---|---|
| actual | 64 | 150 | 94 | 63% | 0.893 | 0.0140 |
| routed | 64 | 150 | 132 | 88% | 1.216 | 0.0190 |
| routed_loo | 64 | 150 | 132 | 88% | 1.216 | 0.0190 |
| start_only | 64 | 150 | 99 | 66% | 1.052 | 0.0164 |

| Role | Actual pass | Start-only pass | Routed pass |
|---|---|---|---|
| support | 65% | 73% | 94% |
| operations | 56% | 61% | 74% |
| management | 70% | 60% | 100% |

| Platform | Recordings: correct | Verifiable | Pass rate | Shadow $ per 1k turns | Shadow $ per correct verifiable turn |
|---|---|---|---|---|---|
| Atlas | 66 | 75 | 88% | 6.08 | 0.0092 |
| Beacon | 37 | 75 | 49% | 6.47 | 0.0175 |
| Chatly | 11 | 75 | 15% | 0.49 | 0.0045 |

Chatly verifiable turns in scope: text-only checks 64 (passed 11), with a state check 11 (failed by construction)
