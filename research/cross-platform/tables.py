"""Print (and save to data/tables.md) every table used in the write-up, from results.json, fidelity.json, truth.json.

    python3 tables.py
"""
import collections, statistics
from common import *

R = json.load(open(os.path.join(D, "results.json"))); F = json.load(open(os.path.join(D, "fidelity.json"))); T = json.load(open(os.path.join(D, "truth.json")))
scs = scenarios(); N = {"atlas": "Atlas", "beacon": "Beacon", "chatly": "Chatly"}
out = []
def P(s=""): out.append(s); print(s)
def table(head, rows):
    P("| " + " | ".join(head) + " |"); P("|" + "---|" * len(head))
    for r in rows: P("| " + " | ".join(str(x) for x in r) + " |")
    P()
pc = lambda x: f"{100 * x:.0f}%" if x is not None else "–"
tasks, sess = T["tasks"], [s for t in T["tasks"] for s in t["sessions"]]

P("## Setup\n")
sc = T["scope"]
table(["Item", "Value"], [["Task instances drawn / in scope", f"{sc['tasks_drawn']} / {sc['tasks_in_scope']}"], ["Scripts in scope / pending", f"{len(sc['scripts'])} / {len(sc['scripts_pending'])} ({', '.join(sc['scripts_pending'])})"],
    ["Sessions in the lake", sum(len(t["sessions"]) for t in tasks)], ["Sessions per platform", ", ".join(f"{N[p]} {sum(s['platform'] == p for s in sess)}" for p in PLATFORMS)],
    ["User turns", sum(s["turns_played"] for s in sess)], ["Task starts per platform", ", ".join(f"{N[p]} {sum(t['sessions'][0]['platform'] == p for t in tasks)}" for p in PLATFORMS)],
    ["Seats / monthly spend", f"{R['seats']['total_seats']} / {R['seats']['monthly_spend']}"],
    ["Tasks with a switch / with two switches", f"{sum(t['n_switches'] > 0 for t in tasks)} / {sum(t['n_switches'] == 2 for t in tasks)}"],
    ["Tasks that ended abandoned", sum(t['final_fate'] == 'abandoned' for t in tasks)],
    ["Sessions where the user noticed the first failed turn", f"{sum(s['noticed_failure'] for s in sess)} of {sum(any(c and not all(c) for c in s['turn_checks']) for s in sess)} sessions with a failed turn (the roll is made once per session, at the first failed turn)"]])

P("## Q1. Fidelity\n")
keys = ["sessions", "turns", "requests", "failed_requests", "tool_calls", "tool_errors", "tokens_in", "tokens_out"]
table(["Platform", "Source"] + keys, [[N[p], src] + [f"{F[p][src].get(k, 0):,}" for k in keys] for p in PLATFORMS for src in ("recording", "export", "lake")])
ok = all(F[p]["recording"][k] == F[p]["export"][k] == F[p]["lake"][k] for p in PLATFORMS for k in keys)
P(f"All three columns equal for every platform and field: {ok}\n")
ch = [t for r in [json.load(open(os.path.join(D, 'chatly_recording', f))) for f in sorted(os.listdir(os.path.join(D, 'chatly_recording')))] for t in r['turns']]
P(f"Chatly recording: {len(ch)} turns, {sum(len(t['attempts']) for t in ch)} attempts, {sum(bool(a['error']) for t in ch for a in t['attempts'])} failed attempts, {sum(not t['answered'] for t in ch)} turns without a reply, {len({a['model'] for t in ch for a in t['attempts']})} different models\n")

P("## Q2. Switch detection\n")
SD = R["switch_detection"]
P(f"Candidates {SD['n_candidates']}, true pairs {SD['n_true_pairs']} (adjacent {SD['n_adjacent_pairs']}), window {SD['window_minutes']} minutes\n")
names = {"a_window": "a. Time window only", "b_jaccard": "b. + word overlap of first prompts", "b2_jaccard_whole_session": "b2. + word overlap of whole sessions (not in brief)", "c_entities": "c. + shared order, ticket or SKU ids",
         "c_entities_or_jaccard": "c2. ids or word overlap", "d_labels": "d. + same labelled domain and task type", "e_best_combination": "e. Best combination"}
table(["Method", "Predicted pairs", "TP", "Precision", "Recall", "F1", "Setting"], [[names[k], v["tp"] + v["fp"], v["tp"], f"{v['precision']:.2f}", f"{v['recall']:.2f}", f"{v['f1']:.2f}",
      (f"threshold {v['threshold']}" if "threshold" in v else (f"tau {v['tau']}, signals {'+'.join(v['signals'])}, k={v['k']}, nearest only={v['nearest_only']}" if "signals" in v else ""))] for k, v in SD["methods"].items()])
table(["Jaccard threshold", "Precision", "Recall", "F1"], [[k, f"{v['precision']:.2f}", f"{v['recall']:.2f}", f"{v['f1']:.2f}"] for k, v in SD["jaccard_sweep"].items() if k in ("0.00", "0.05", "0.10", "0.20", "0.30", "0.40", "0.50", "0.60")])
pa = SD["paraphrase"]
P(f"Paraphrase: {pa['switch_sessions']} switch sessions, {pa['of_which_paraphrased']} paraphrased; median Jaccard of first prompts true pairs {pa['median_jaccard_first_prompt_true_pairs']}, false pairs {pa['median_jaccard_first_prompt_false_pairs']}; true pairs sharing an id {pa['true_pairs_with_entity']} of {pa['true_pairs_in_candidates']}")
cf = SD["counterfactual_unparaphrased"]
P(f"Counterfactual with the original prompt re-pasted (threshold {cf['threshold']}): precision {cf['precision']}, recall {cf['recall']}, F1 {cf['f1']}")
P(f"Label lookup by text: script matched in {R['label_lookup']['script_match_correct']} of {R['label_lookup']['sessions']} sessions; sessions with a label {R['label_lookup']['sessions_with_label']}\n")

P("## Q3. Proxies\n")
PX = R["proxies"]
table(["Platform", "Sessions", "Turns", "Verifiable turns", "Correct (checks)", "No answer", "Switch-away", "Abandonment", "Tool error", "Failed request", "Composite"],
      [[N[p], c["sessions"], c["turns"], c["verifiable_turns"], pc(c["truth_pass"]), pc(c["no_answer"]), pc(c["switch_away"]), pc(c["abandonment"]), pc(c["tool_error"]), pc(c["failed_request"]), f"{c['composite']:.3f}"] for p, c in PX["by_platform"].items()])
a, s = PX["abandonment_flag_vs_truth"], PX["switch_away_flag_vs_truth"]
P(f"Session-level flags against the replay: abandonment precision {a['precision']}, recall {a['recall']} (tp {a['tp']}, fp {a['fp']}, fn {a['fn']}); switch-away precision {s['precision']}, recall {s['recall']}\n")
for cut in ("designed_task_type", "labelled_domain"):
    x = PX[cut]
    if not x: P(f"Cut {cut}: pending (labels)\n"); continue
    P(f"### Cut: {cut}\n")
    table(["Group", "Platform", "Sessions", "Verifiable turns", "Correct (checks)", "Composite"], [[c["group"], N[c["platform"]], c["sessions"], c["verifiable_turns"], pc(c["truth_pass"]), f"{c['composite']:.3f}"] for c in x["cells"]])
    table(["Group", "Best by checks", "Best by proxy", "Match"], [[g["group"], N[g["best_by_truth"]], N[g["best_by_proxy"]], "yes" if g["match"] else "no"] for g in x["groups"]])
    P(f"Cells {x['n_cells']}, Spearman composite vs checks {x['spearman_composite_vs_truth']}; groups matching {x['groups_matching']} of {x['groups_compared']}; pairs concordant {x['pairs_concordant']} of {x['pairs_compared']}; single proxies {x['spearman_single_proxies']}\n")

P("## Q4. Seats\n")
S = R["seats"]
table(["Holder", "Seat", "Price", "Sessions", "Share of holder's sessions", "Task starts", "Last use", "Flag"], [[r["handle"], N[r["platform"]], r["price"], r["sessions"], pc(r["share"]), r["task_starts"], r["last_use"] or "never", "yes" if r["flag"] else ""] for r in S["rows"]])
table(["Rule", "Flagged", "Saving per month", "Designed idle seats", "TP", "FP", "FN", "Precision", "Recall"],
      [[n, S[k]["flagged"], S[k]["monthly_saving"], S[k]["designed_idle"], S[k]["tp"], S[k]["fp"], S[k]["fn"], f"{S[k]['precision']:.2f}", f"{S[k]['recall']:.2f}"] for n, k in (("under 10% of sessions", "by_sessions"), ("under 10% of task starts", "by_task_starts"))])
P(f"Designed idle saving {S['by_sessions']['designed_saving']} per month of {S['monthly_spend']}; single-seat users {S['single_seat_users']}\n")

P("## Q5. Routing\n")
RT = R["routing"]; cells = {(c["platform"], c["task_type"]): c for c in RT["cells"]}
table(["Task type", "Scripts", "Verifiable turns"] + [f"{N[p]} correct" for p in PLATFORMS] + [f"{N[p]} $/1k turns" for p in PLATFORMS] + ["Best"],
      [[t, cells[("atlas", t)]["scripts"], cells[("atlas", t)]["verifiable_turns"]] + [pc(cells[(p, t)]["pass_rate"]) for p in PLATFORMS] + [f"{cells[(p, t)]['cost_per_1000_turns']:.2f}" for p in PLATFORMS] + [N[RT["best"][t]]] for t in RT["task_types"]])
table(["Policy", "Tasks", "Verifiable turns", "Correct", "Pass rate", "Shadow cost (USD)", "Cost per task"],
      [[n, v["all"]["tasks"], v["all"]["verifiable_turns"], v["all"]["passed"], pc(v["all"]["pass_rate"]), f"{v['all']['shadow_cost']:.3f}", f"{v['all']['cost_per_task']:.4f}"] for n, v in RT["policies"].items()])
table(["Role", "Actual pass", "Start-only pass", "Routed pass"], [[r, pc(RT["policies"]["actual"][r]["pass_rate"]), pc(RT["policies"]["start_only"][r]["pass_rate"]), pc(RT["policies"]["routed"][r]["pass_rate"])] for r in ("support", "operations", "management")])
tot = {p: (sum(c["passed"] for (q, t), c in cells.items() if q == p), sum(c["verifiable_turns"] for (q, t), c in cells.items() if q == p), sum(c["cost"] for (q, t), c in cells.items() if q == p), sum(c["turns"] for (q, t), c in cells.items() if q == p)) for p in PLATFORMS}
table(["Platform", "Recordings: correct", "Verifiable", "Pass rate", "Shadow $ per 1k turns", "Shadow $ per correct verifiable turn"], [[N[p], v[0], v[1], pc(v[0] / v[1]), f"{1000 * v[2] / v[3]:.2f}", f"{v[2] / v[0]:.4f}"] for p, v in tot.items()])
txt = collections.Counter()
for sid in T["scope"]["scripts"]:
    for i, turn in enumerate(scs[sid]["turns"]):
        if turn["checks"]:
            kinds = {c[0] for c in turn["checks"]}; rec = T["recordings"][f"chatly:{sid}"]
            txt["text_only" if kinds <= {"num", "has", "any", "not"} else "state"] += 1
            if kinds <= {"num", "has", "any", "not"}: txt["text_only_passed"] += all(rec["turn_checks"][i])
P(f"Chatly verifiable turns in scope: text-only checks {txt['text_only']} (passed {txt['text_only_passed']}), with a state check {txt['state']} (failed by construction)\n")
open(os.path.join(D, "tables.md"), "w").write("\n".join(out))
