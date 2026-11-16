"""Insight cards in the ADR 0006 contract, by fixed rules over the results of the other scripts. No model.

    python3 cards.py          # reads data/*.json, writes data/cards.json and data/cards.md

A card has a decision, an owner, a finding, evidence with its n, a basis (counted, linked, labelled or checked), the
measured error of that basis, a readiness (act, check first, watch), an action, a caveat and a scope. Readiness comes
from the rules in this file, which follow the bar of each decision in catalogue.json. Cards are ranked by the share of
tasks, turns or spend that they touch.

Numbers with the basis `checked` use the ground truth of the simulation in the place of sampled checks, and the errors
of the `linked` and `labelled` numbers are scored against it. A real deployment needs a reference set for both.
"""
import json, os
import base

NAME, P = base.NAME, base.PLATFORMS
MIN_GROUP = 5                                       # docs/privacy.md, proposal
pc = lambda x: f"{100 * x:.0f}%"
frac = lambda k, n: f"{pc(k / n)} ({k}/{n})" if n else "–"
pts = lambda x: f"{100 * x:+.0f}"
cards, blocked = [], []


def card(weight, decision, owner, title, finding, evidence, basis, error, readiness, why, action, caveat):
    cards.append({"weight": round(weight, 3), "decision": decision, "owner": owner, "title": title, "finding": finding, "evidence": evidence,
                  "basis": basis, "error": error, "readiness": readiness, "readiness_rule": why, "action": action, "caveat": caveat})


def main():
    T, S, SE, DM = (base.load(f + ".json") for f in ("tasks", "sampling", "seats", "demand"))
    cat = {d["id"]: d for d in json.load(open(os.path.join(base.HERE, "catalogue.json")))["decisions"]}
    tasks = T["rebuild"]["rebuilt_tasks"]; sessions = sum(T["shares"]["sessions"].values())
    link = T["rebuild"]["links"]; link_err = f"task links: precision {link['tp']}/{link['tp'] + link['fp']}, recall {link['tp']}/{link['tp'] + link['fn']}"
    scope = f"{T['window']['weeks']:.0f} weeks, {T['window']['people']} people, {tasks} tasks, {sessions} sessions, 3 platforms"

    # ---- D3: which platform, overall
    R = S["matrix"]["rates"]; order = sorted(P, key=lambda p: -R[p]["all"]["rate"]); a, b = order[0], order[1]
    bs = S["matrix"]["bootstrap"].get(f"{a}-{b}") or S["matrix"]["bootstrap"][f"{b}-{a}"]
    lo, hi = sorted(abs(x) for x in bs["script_ci"]) if bs["script_ci"][0] * bs["script_ci"][1] > 0 else (0, 0)
    off_best = tasks - T["shares"]["task_starts"][a]
    card(off_best / tasks, "D3", cat["D3"]["owner"], f"{NAME[a]} gets the most answers right",
         f"{NAME[a]} is right on {pc(R[a]['all']['rate'])} of checked turns, {NAME[b]} on {pc(R[b]['all']['rate'])} and {NAME[order[2]]} on {pc(R[order[2]]['all']['rate'])}.",
         [f"Checked turns correct: " + ", ".join(f"{NAME[p]} {R[p]['all']['k']}/{R[p]['all']['n']}" for p in order),
          f"{NAME[a]} against {NAME[b]}: {pts(bs['diff'])} points, 95% interval {pts(lo)} to {pts(hi)} with the script as the unit",
          f"{off_best} of {tasks} tasks started on another platform than {NAME[a]}"],
         "checked", f"sampling interval, {S['matrix']['rates'][a]['all']['n']} checked turns per platform from {sum(S['matrix']['scripts_per_type'].values())} scripts",
         "act" if lo > 0 else "watch", "D3 bar: the interval of the difference excludes zero with the script as the unit",
         f"Make {NAME[a]} the default for work that needs company data.",
         "Every script was run once on every platform. In a company that is a planned test set, not what the traces give for free.")

    # ---- D3: by task type
    M = S["matrix"]; kept = [t for t in M["tests"] if t["group"] != "all" and t.get("holm")]
    best_by_type = {tt: max(P, key=lambda p: R[p][tt]["rate"]) for tt in M["types"]}
    differs = [tt for tt, p in best_by_type.items() if p != a]
    plan = next(x for x in S["budget"]["plan"] if x["n"] == S["budget"]["first_n_reaching_90"]["mean"])
    card(0, "D3", cat["D3"]["owner"], "Not enough checks to route by task type",
         f"{len(kept)} of {M['within_tests']} platform comparisons inside a task type hold up, and no task type has a clear best platform other than {NAME[a]}.",
         [f"Comparisons significant at 0.05: {M['within_significant']} of {M['within_tests']}; after correction for many tests: {M['within_significant_holm']}",
          f"Task types where another platform has the highest rate: {', '.join(differs) or 'none'}",
          f"{plan['n']} checks per platform and task type pick the right platform 9 times in 10 on average: {plan['type_checks']} checks. "
          f"The window produced {plan['lake_verifiable']} checkable turns and {plan['cells_short']} of {len(S['budget']['lake_cells'])} cells are short of {plan['n']}"],
         "checked", "sampling interval; cells hold 4 to 16 checked turns", "watch", "D3 bar not met inside task types",
         f"Do not route by task type yet. Plan a test set of {plan['n']} checked tasks per platform and task type.",
         "The simulation takes each cell's observed rate as the true rate. Smaller real gaps need more checks.")

    # ---- D3: the trace cannot replace checks
    st = S["silent"]["per_turn"]["all"]; te, ina = S["silent"]["parts"]["all"]["tool_error"], S["silent"]["parts"]["all"]["inability"]
    n10 = S["budget"]["platform"]["10"]
    card(st["silent"]["k"] / st["verifiable"], "D3", cat["D3"]["owner"], "Half of the wrong answers leave no sign in the trace",
         f"{st['silent']['k']} of {st['silent']['n']} turns that failed a check show no error, no empty reply and no \"I can't\" in the trace.",
         [f"Silent failures: {frac(st['silent']['k'], st['silent']['n'])}, 95% interval {pc(st['silent']['lo'])} to {pc(st['silent']['hi'])}",
          f"A failed tool call marks a wrong answer in {te['precision']['k']} of {te['precision']['n']} turns; an inability phrase in {ina['precision']['k']} of {ina['precision']['n']}",
          f"10 checked turns per platform pick the best platform in {pc(n10['best'])} of simulated samples: {len(P) * 10} checks for the period"],
         "checked", f"sampling interval, {st['verifiable']} checked turns", "act", "counted against checks; the interval is far from zero",
         f"Do not rank platforms by error rates. Fund about {len(P) * 10} checked answers per period, and check flagged turns first.",
         "Failure rates from flagged turns only are biased upwards. Use a random sample for the rate.")

    # ---- D4: capability gaps per platform
    for p in P:
        o = DM["switches"]["by_origin"].get(p)
        if not o or not o["missing"]: continue
        kind = lambda k: k.split(": ")[0]
        top = max(sorted(o["missing"]), key=lambda k: (o["missing"][k], kind(k) in ("skill", "MCP server")))
        n = o["missing"][top]; tr = DM["trouble"]["by_platform"][p]; co = DM["chat_only"][p]
        chat_only = p in S.get("no_tool_platforms", [])
        n_tasks = n + (tr["inability"] if chat_only else 0)          # an inability ending on a platform with no tools is the same gap
        ev = [f"{n} of {o['switches']} tasks that left {NAME[p]} used the {top.replace(': ', ' ')} on the next platform",
              f"Tasks started on {NAME[p]} that were re-done elsewhere or ended on trouble: {frac(co['redone_or_trouble'], co['tasks_started'])}"]
        if chat_only:
            ip = S["silent"]["parts"][p]["inability"]["precision"]
            ev.append(f"{tr['inability']} more tasks ended on {NAME[p]} with a reply that says it cannot reach the data; {frac(co['inability_turns'], co['turns'])} of its turns carry such a phrase "
                      f"(the phrase marks a wrong answer in {ip['k']} of {ip['n']} checked turns)")
        ready = "act" if n_tasks >= 5 else "check first" if n_tasks >= 3 else "watch"
        what = f"{kind(top)} `{top.split(': ')[1]}`"
        card(n_tasks / tasks, "D4", cat["D4"]["owner"], f"{NAME[p]} lacks the {kind(top)} {top.split(': ')[1]}",
             (f"{n_tasks} tasks left {NAME[p]} for a platform with the {what} or ended there on a reply that says it cannot reach the data." if chat_only
              else f"{n_tasks} tasks failed on {NAME[p]}, which does not have the {what}."), ev, "linked",
             link_err + ("; inability phrase scored above" if chat_only else ""), ready,
             f"D4 bar: the same gap in 5 tasks or more is `act`, in 3 or 4 `check first` (here {n_tasks})",
             f"Add the {what} to {NAME[p]}, or send that work to a platform that has it.",
             "The next platform may have used the capability only because it was there. A capability the first platform has but did not use in the window counts as missing.")

    # ---- D4: rework
    rw = T["score_rework"]; byp = {p: T["rework"][f"{p} all"] for p in P}; worst = max(P, key=lambda p: byp[p]["cost_share_redone"])
    card(rw["cost"]["estimate_redone"], "D4", cat["D4"]["owner"], "Work that is done twice",
         f"{pc(rw['cost']['estimate_redone'])} of the token cost and {pc(rw['minutes']['estimate_redone'])} of people's time went to sessions that the person then re-did on another platform.",
         [f"Re-done sessions: {T['rework']['total redone']['sessions']} of {sessions}",
          f"Upper bound with sessions that ended on trouble: {pc(rw['cost']['estimate_at_risk'])} of cost, {pc(rw['minutes']['estimate_at_risk'])} of time",
          f"Highest on {NAME[worst]}: {pc(byp[worst]['cost_share_redone'])} of its token cost was re-done elsewhere"],
         "linked", f"{link_err}; the trouble flag is right for {rw['trouble_vs_abandoned']['tp']} of {rw['trouble_vs_abandoned']['tp'] + rw['trouble_vs_abandoned']['fp']} sessions, so the upper bound is loose",
         "check first", "linked evidence with a loose upper bound", f"Start with {NAME[worst]}: find what its re-done tasks needed (see the capability cards).",
         "People time is the length of a session, not effort. Tasks dropped with no sign in the trace are not counted.")

    # ---- D1: seats
    q = [s for s in SE["seats"] if s["R2"]]; ev3 = [s for s in SE["seats"] if s["R3"]]; fb = [s for s in SE["seats"] if s["fallback_only"]]
    multi = [h for h in SE["holders"] if h["seats"] > 1]
    sim = SE["simulation"]["normal"][str(SE["window_weeks"])]["R2"]
    card(sum(s["price"] for s in q) / SE["monthly_spend"], "D1", cat["D1"]["owner"], "Quiet seats, not yet unused seats",
         f"{len(q)} of {len(SE['seats'])} seats had almost no task starts, worth {sum(s['price'] for s in q)} of {SE['monthly_spend']} per month, and {len(ev3)} of them can be called unused on this evidence.",
         ["Quiet seats: " + ", ".join(f"{s['handle']} on {NAME[s['platform']]} ({s['task_starts']} of {s['holder_starts']} starts)" for s in q),
          f"A seat with no start is evidence only after its holder has made {SE['n_star']} task starts. The busiest holder made {max(h['starts'] for h in SE['holders'])}; "
          f"at the observed rates that takes {min(h['weeks_more'] for h in multi):.0f} to {max(h['weeks_more'] for h in multi):.0f} more weeks",
          f"In a simulation of this company, the 10% share rule flags a seat that is in use in {pc(sim['share_runs_wrong'])} of {SE['window_weeks']}-week windows",
          f"Used only as a fallback after a failure elsewhere: " + (", ".join(f"{s['handle']} on {NAME[s['platform']]}" for s in fb) or "none")],
         "linked", link_err, "act" if ev3 else "watch", "D1 bar: the chance of this few starts at a true share of 10% is under 5%",
         "Do not cancel on this evidence. Ask the holders, or wait until the evidence rule fires.",
         "A holder with one seat is never flagged. A seat used rarely but for something that matters looks the same as an unused one.")

    # ---- D1: licence against tokens
    L = T["licence"]["total"]; C = T["cost_per_task"]["total"]
    card(1.0, "D1", cat["D1"]["owner"], "The cost is in the seats, not in the tokens",
         f"Seats cost {L['licence_to_token']:.0f} times the token cost of the work done on them.",
         [f"Licences in the window: {L['licence_window']:.2f}; token cost at list prices: {L['shadow_token_cost_window']:.2f}",
          f"Per task started: {L['licence_per_task_started']:.2f} of licence against {C['cost_per_task']:.3f} of tokens",
          f"Tokens equal the seat price at about {L['breakeven_tasks_per_seat_month']:,.0f} tasks per seat per month; staff did {T['window']['tasks_per_person_week']:.1f} tasks per person per week"],
         "counted", "none for the counts; the token cost is list price, not a bill", "act", "counted evidence",
         "Manage the number of seats before the token spend. Review token cost only for seats with heavy use.",
         "The simulated staff are light users. Heavy agent use changes the ratio.")

    # ---- D2: work map
    LA = DM["label_agreement"]; wm = DM["work_map"]["role_x_domain"]; people_per_role = min(sum(1 for u in base.directory() if u["role"] == r) for r in wm)
    kd = [v["kappa"] for v in LA["domain"]["pairs"].values()]; kt = [v["kappa"] for v in LA["task_type"]["pairs"].values()]
    ok = min(kd + kt) >= 0.6 and people_per_role >= MIN_GROUP
    card(0, "D2", cat["D2"]["owner"], "The work map cannot be compared across platforms yet",
         f"The same task gets the same task type on all three platforms in {frac(LA['task_type']['all_three']['agree'], LA['task_type']['all_three']['n'])} of scripts.",
         [f"Agreement between platforms (kappa): domain {min(kd):.2f} to {max(kd):.2f}, task type {min(kt):.2f} to {max(kt):.2f}",
          "Label equals the designed label: " + ", ".join(f"{NAME[p]} domain {frac(LA['domain']['accuracy'][p]['correct'], LA['domain']['accuracy'][p]['n'])}, "
                                                         f"task type {frac(LA['task_type']['accuracy'][p]['correct'], LA['task_type']['accuracy'][p]['n'])}" for p in P),
          f"The smallest role has {people_per_role} people; the minimum group size is {MIN_GROUP}"],
         "labelled", "agreement as above", "act" if ok else "watch", "D2 bar: kappa 0.6 or more, and groups at or above the minimum size",
         "Show the work map by domain only, and only for platforms whose labels agree. Fix the task type label before it is used across platforms.",
         "The chat platform's transcripts have no tool lines, so the same work reads differently. Labels come from many small free models.")

    # ---- blocked decisions
    ids = DM["identifiers"]
    blocked.append(("D5", cat["D5"]["decision"], "No sensitivity label or policy exists, so no card can be made. "
                    f"A first count: {sum(ids[p]['any'] for p in P)} of {sum(ids[p]['sessions'] for p in P)} sessions name an order, ticket or SKU id in a prompt "
                    f"({', '.join(NAME[p] + ' ' + frac(ids[p]['any'], ids[p]['sessions']) for p in P)}). An id is not sensitivity."))
    blocked.append(("D6", cat["D6"]["decision"], "Not an organisation card. The personal report goes to the person (round 3)."))

    rank = {"act": 0, "check first": 1, "watch": 2}
    cards.sort(key=lambda c: (-c["weight"], rank[c["readiness"]], c["title"]))
    for i, c in enumerate(cards): c["rank"] = i + 1; c["scope"] = scope
    base.save("cards.json", {"cards": cards, "not_available": [{"decision": d, "question": q, "note": n} for d, q, n in blocked]})
    out = ["# Insight cards (generated by cards.py)", "",
           "Each card follows [ADR 0006](../../../docs/adr/0006-insight-card-contract.md). Ranked by the share of tasks, turns or spend it touches. "
           "Numbers with the basis `checked` use the ground truth of the simulation in the place of sampled checks.", "",
           "| # | Card | Decision | Owner | Basis | Readiness |", "|---|---|---|---|---|---|"]
    out += [f"| {c['rank']} | {c['title']} | {c['decision']} | {c['owner']} | {c['basis']} | {c['readiness']} |" for c in cards] + [""]
    for c in cards:
        out += [f"## {c['rank']}. {c['title']}", "", f"**Decision.** {c['decision']}: {cat[c['decision']]['decision']} **Owner.** {c['owner']}", "",
                f"**Finding.** {c['finding']}", "", "**Evidence.**"] + [f"- {e}" for e in c["evidence"]] + \
               ["", f"**Basis.** `{c['basis']}`. **Error.** {c['error']}.", "", f"**Readiness.** `{c['readiness']}` ({c['readiness_rule']}).", "",
                f"**Action.** {c['action']}", "", f"**Caveat.** {c['caveat']}", ""]
    out += ["## No card", ""] + [f"- **{d} {q}** {n}" for d, q, n in blocked] + ["", f"Scope of every card: {scope}.", ""]
    open(os.path.join(base.D, "cards.md"), "w").write("\n".join(out))
    for c in cards: print(c["rank"], c["readiness"].ljust(11), c["decision"], c["title"], "|", c["finding"])


if __name__ == "__main__":
    main()
