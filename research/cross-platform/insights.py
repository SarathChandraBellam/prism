"""Insight cards: deterministic rules over data/results.json. No model.

    python3 insights.py          # writes data/insights.md

Each card has a finding in plain words, evidence numbers, a recommended action and an owner role. Findings about people
are given per role (3 groups). Only seat flags name the seat holder (by handle). A card is skipped when the analysis it
needs is pending, and the skipped cards are listed at the end.
"""
from common import *

R = json.load(open(os.path.join(D, "results.json")))
NAME = {"atlas": "Atlas", "beacon": "Beacon", "chatly": "Chatly"}
P = lambda x: f"{100 * x:.0f}%"
cards, pending = [], []


def card(weight, title, finding, evidence, action, owner):
    cards.append({"weight": weight, "title": title, "finding": finding, "evidence": evidence, "action": action, "owner": owner})


# ---- 1. the chat-only platform fails tasks that need company data
O, BP = R["lake_outcomes"]["all"], R["proxies"]["by_platform"]
if O.get("start_chatly"):
    n, sw, ab = O["start_chatly"], O["start_chatly_switched"], O["start_chatly_abandoned"]
    card((sw + ab) / O["tasks"], "Chatly is used for work it cannot do",
         f"{P((sw + ab) / n)} of the tasks that staff started on Chatly were re-done on another platform or ended on trouble.",
         [f"{n} of {O['tasks']} tasks started on Chatly: {sw} re-done elsewhere (detected), {ab} ended on trouble without a follow-up",
          f"From sampled checks: verifiable turns correct on Chatly: {P(BP['chatly']['truth_pass'])} (n={BP['chatly']['verifiable_turns']}), Atlas {P(BP['atlas']['truth_pass'])} (n={BP['atlas']['verifiable_turns']}), Beacon {P(BP['beacon']['truth_pass'])} (n={BP['beacon']['verifiable_turns']})",
          "Chatly has no tools, so every check on database state fails by construction"],
         "Tell Chatly users which requests need company data. Move those to Atlas, or connect Chatly to the same tools.", "platform owner")

# ---- 2. seats
S = R["seats"]["by_sessions"]
low = [r for r in R["seats"]["rows"] if r["flag"]]
if low:
    card(S["monthly_saving"] / R["seats"]["monthly_spend"], "Seats nobody uses",
         f"{S['flagged']} of {R['seats']['total_seats']} seats had no or almost no use in the two weeks, worth {S['monthly_saving']} per month.",
         [f"Flagged (under 10% of the holder's sessions): " + ", ".join(f"{r['handle']} on {NAME[r['platform']]} ({r['sessions']} sessions)" for r in low),
          f"Licence spend is {R['seats']['monthly_spend']} per month; the flagged seats are {P(S['monthly_saving'] / R['seats']['monthly_spend'])} of it",
          f"Against the designed list: precision {S['precision']:.2f}, recall {S['recall']:.2f}. Two weeks is short: a seat can be quiet by chance"],
         "Check each flagged seat with its holder, then cancel or reassign those that stay unused for a month.", "finance")

# ---- 3. routing
RT = R["routing"]; pol = RT["policies"]
gain = pol["routed"]["all"]["pass_rate"] - pol["actual"]["all"]["pass_rate"]
same = len(set(RT["best"].values())) == 1
card(gain, "Send each task type to the platform that gets it right",
     f"Routing every task type to its best platform would lift the share of correct verifiable turns from {P(pol['actual']['all']['pass_rate'])} to {P(pol['routed']['all']['pass_rate'])}"
     + (f", and that platform is {NAME[list(RT['best'].values())[0]]} for all {len(RT['best'])} task types." if same else "."),
     [f"What the simulated staff got: {P(pol['actual']['all']['pass_rate'])} ({pol['actual']['all']['passed']}/{pol['actual']['all']['verifiable_turns']}); if they had stayed on the platform they started with, no switching: {P(pol['start_only']['all']['pass_rate'])}",
      f"Routed: {P(pol['routed']['all']['pass_rate'])}; the same routing chosen without each task's own script gives {P(pol['routed_loo']['all']['pass_rate'])}",
      f"Shadow cost per task: actual {pol['actual']['all']['cost_per_task']:.4f}, routed {pol['routed']['all']['cost_per_task']:.4f} (USD, list prices of the paid twin models)",
      "Best platform by task type: " + ", ".join(f"{k} {NAME[v]}" for k, v in RT["best"].items())],
     "Make the best platform the default for these task types, and keep Chatly for drafting where its answers hold up." if same else "Set the default platform per task type as listed.",
     "team lead")

# ---- 4. role with the highest abandonment
roles = {r: R["lake_outcomes"][r] for r in ("support", "operations", "management")}
worst = max(roles, key=lambda r: (roles[r]["abandoned"] / roles[r]["tasks"], r))
w = roles[worst]
card(w["abandoned"] / O["tasks"], f"The {worst} group abandons the most tasks",
     f"In the {worst} group {P(w['abandoned'] / w['tasks'])} of tasks ended on trouble (an error, no answer or an inability phrase) with no follow-up on another platform.",
     [f"{r}: {v['abandoned']} of {v['tasks']} tasks ended on trouble with no follow-up, {v['switched']} re-done on another platform (detected)" for r, v in roles.items()]
     + [f"Tasks started on Chatly in the {worst} group: {w.get('start_chatly', 0)} of {w['tasks']}",
        f"Scored against the replay, the trouble-without-follow-up flag has precision {R['proxies']['abandonment_flag_vs_truth']['precision']:.2f} and recall {R['proxies']['abandonment_flag_vs_truth']['recall']:.2f}: it over-counts, so treat the rate as an upper bound"],
     f"Review the platform defaults and seats of the {worst} group first.", "team lead")

# ---- 5. skills gap
cells = {(c["platform"], c["task_type"]): c for c in RT["cells"]}
gaps = sorted(((cells[("atlas", t)]["pass_rate"] - cells[("beacon", t)]["pass_rate"], t) for t in RT["task_types"]
               if cells[("atlas", t)]["pass_rate"] is not None and cells[("beacon", t)]["pass_rate"] is not None), reverse=True)
big = [(g, t) for g, t in gaps if g >= .3]
if big:
    card(sum(cells[("atlas", t)]["verifiable_turns"] for g, t in big) / sum(c["verifiable_turns"] for c in RT["cells"] if c["platform"] == "atlas"),
         "Beacon lacks the skills that make Atlas correct",
         f"On {len(big)} task types Beacon, which has the same tools but no skills, gets at least 30 points fewer verifiable turns right than Atlas.",
         [f"{t}: Atlas {P(cells[('atlas', t)]['pass_rate'])}, Beacon {P(cells[('beacon', t)]['pass_rate'])} (n={cells[('atlas', t)]['verifiable_turns']} turns each)" for g, t in big],
         "Port the house-rule skills (refund rules, report definitions, triage order) to Beacon, or move these task types to Atlas.", "skill author")

# ---- 6. proxies
PX = R["proxies"]["designed_task_type"]
if PX:
    sp = PX["spearman_single_proxies"]
    card(PX["groups_compared"] - PX["groups_matching"] and (PX["groups_compared"] - PX["groups_matching"]) / PX["groups_compared"] * .5,
         "Outcome proxies do not rank platforms on their own",
         f"The proxy composite picked the same best platform as the checks in {PX['groups_matching']} of {PX['groups_compared']} task groups.",
         [f"Spearman between composite and share of correct turns across {PX['n_cells']} platform-by-task cells: {PX['spearman_composite_vs_truth']:.2f}",
          "Per proxy (higher means it agrees with the checks): " + ", ".join(f"{k.replace('_', ' ')} {v:.2f}" for k, v in sp.items()),
          "Tool errors run against quality because a platform without tools cannot make them"],
         "Use switch-away as the quality signal and compare platforms only within one capability class. Keep a sample of checked turns.", "platform owner")

# ---- 7. switch detection
SD = R["switch_detection"]; b = SD["methods"]["e_best_combination"]; pa = SD["paraphrase"]
card(O["switched"] / O["tasks"], "Switching is visible in the traces",
     f"{O['switched']} of {O['tasks']} tasks ({P(O['switched'] / O['tasks'])}) were re-done on another platform as far as the detector can tell, and a time window plus word overlap finds {b['tp']} of {b['tp'] + b['fn']} of the true re-asks.",
     [f"Time window alone (30 minutes): precision {SD['methods']['a_window']['precision']:.2f}, recall {SD['methods']['a_window']['recall']:.2f}",
      f"Best combination: precision {b['precision']:.2f}, recall {b['recall']:.2f}, F1 {b['f1']:.2f} (signals {', '.join(b['signals'])}, threshold {b['tau']})",
      f"All {pa['of_which_paraphrased']} re-asks were re-worded; the median word overlap of true pairs is {pa['median_jaccard_first_prompt_true_pairs']:.2f}, so a threshold above 0.3 would lose {P(1 - SD['jaccard_sweep']['0.30']['recall'])} of them",
      f"Re-pasted original prompts would have been found with recall {SD['counterfactual_unparaphrased']['recall']:.2f}"],
     "Log a shared task reference across platforms, or run the detector on every pair of sessions by one user within 30 minutes.", "platform owner")

if "d_labels" not in SD["methods"]: pending.append("Label-based switch detection (method d) and the labelled-domain cut of the proxy analysis: Beacon and Chatly session labels need 64 model requests.")
if not R["proxies"].get("labelled_domain"): pending.append("Proxy comparison by labelled domain.")
if R.get("routing") and False: pass
cards.sort(key=lambda c: -c["weight"])
lines = ["# Insight cards (generated by insights.py)", "",
         "Ranked by the share of tasks, turns or spend each finding touches. Findings about people are per role; only seat flags name a holder.", ""]
for i, c in enumerate(cards, 1):
    lines += [f"## {i}. {c['title']}", "", f"**Finding.** {c['finding']}", "", "**Evidence.**"] + [f"- {e}" for e in c["evidence"]] + \
             ["", f"**Action.** {c['action']}", "", f"**Owner.** {c['owner']}", ""]
if pending: lines += ["## Not yet available", ""] + [f"- {p}" for p in pending] + [""]
open(os.path.join(D, "insights.md"), "w").write("\n".join(lines))
print("\n".join(lines))
