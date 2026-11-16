"""Tasks: what changes when the unit is the task, not the session.

    python3 tasks.py            # writes data/tasks.json and data/tasks.md

Rebuilds task chains from the spans with the fixed rule in base.rebuild_tasks, then compares the session view with the
task view: platform share, rework (sessions whose work was re-done or ended in trouble), cost per task and per correct
task, and licence cost against token cost. Every estimate is computed from the spans, the seat list and the directory.
Ground truth (base.truth, base.truth_tasks) is read only in the score_* functions and in the 'correct' column of the
cost table, which in practice needs sampled checks of answers. Standard library only. No model.
"""
import collections, datetime as dt, os
import base

P = base.PLATFORMS
CLASSES = ["redone", "ended_in_trouble", "clean"]
DAYS_PER_MONTH = 21                      # working days in a month, to prorate the monthly seat price to the window


def r(x, n=4): return round(x, n)
def share(k, n): return f"{100 * k / n:.0f}% ({k}/{n})" + (" small n" if n < 5 else "") if n else "–"
def usd(x): return f"{x:.4f}" if x < 10 else f"{x:.2f}"
def money(x, n): return (f"{x:,.2f}" + (" small n" if n < 5 else "")) if x else "–"
def table(head, rows): return "\n".join(["| " + " | ".join(head) + " |", "|" + "---|" * len(head)] + ["| " + " | ".join(map(str, x)) + " |" for x in rows])


def prf(tp, fp, fn):
    p, rc = (tp / (tp + fp) if tp + fp else None), (tp / (tp + fn) if tp + fn else None)
    return {"tp": tp, "fp": fp, "fn": fn, "precision": r(p, 3) if p is not None else None, "recall": r(rc, 3) if rc is not None else None}


def working_days(ses):
    """Weekdays from the first to the last day with a session, both included."""
    d0, d1 = min(x["start"].date() for x in ses.values()), max(x["end"].date() for x in ses.values())
    return sum((d0 + dt.timedelta(days=i)).weekday() < 5 for i in range((d1 - d0).days + 1))


# ---------------------------------------------------------------- spans only

def measures(x):
    chats = [k for t in x["turns"] for k in t["chats"]]
    return {"sessions": 1, "turns": len(x["turns"]), "requests": len(chats),
            "tokens": sum((base.A(k).get("gen_ai.usage.input_tokens") or 0) + (base.A(k).get("gen_ai.usage.output_tokens") or 0) for k in chats),
            "cost": x["cost"], "minutes": (x["end"] - x["start"]).total_seconds() / 60}


def classify(ses, tasks):
    """redone: a later session of the same rebuilt task follows it. ended_in_trouble: last session of its task and its last
    turn shows trouble. clean: the rest."""
    c = {}
    for k in tasks:
        for i, sid in enumerate(k["sessions"]):
            c[sid] = "redone" if i < len(k["sessions"]) - 1 else "ended_in_trouble" if ses[sid]["ends_in_trouble"] else "clean"
    return c


def shares(ses, tasks):
    n_ses = collections.Counter(x["platform"] for x in ses.values())
    starts = collections.Counter(ses[k["sessions"][0]]["platform"] for k in tasks)
    fin = collections.Counter(ses[k["sessions"][-1]]["platform"] if not ses[k["sessions"][-1]]["ends_in_trouble"] else "unfinished" for k in tasks)
    return {"sessions": dict(n_ses), "task_starts": dict(starts), "tasks_finished": dict(fin)}


def rework(ses, cls):
    agg = collections.defaultdict(collections.Counter)
    for sid, x in ses.items():
        m = measures(x)
        for key in ((x["platform"], cls[sid]), (x["platform"], "all"), ("total", cls[sid]), ("total", "all")): agg[key].update(m)
    out = {f"{p} {c}": {k: r(v, 6) for k, v in agg[(p, c)].items()} for p, c in agg}
    for p in P + ["total"]:
        a, al = agg[(p, "redone")], agg[(p, "all")]
        b = agg[(p, "ended_in_trouble")]
        out[f"{p} all"].update({f"{m}_share_redone": r(a[m] / al[m]) if al[m] else None for m in ("cost", "minutes")})
        out[f"{p} all"].update({f"{m}_share_at_risk": r((a[m] + b[m]) / al[m]) if al[m] else None for m in ("cost", "minutes")})
    return out


# ---------------------------------------------------------------- scoring against truth (SCORING ONLY)

def score_rebuild(tasks):
    _, true = base.truth_tasks()
    got = {tuple(k["sessions"]) for k in tasks}; want = {tuple(c) for c in true}
    links = lambda chains: {(c[i], c[i + 1]) for c in chains for i in range(len(c) - 1)}
    lg, lw = links(got), links(want)
    return {"rebuilt_tasks": len(got), "true_tasks": len(want), "exact_chains": len(got & want),
            "links": prf(len(lg & lw), len(lg - lw), len(lw - lg))}


def truth_sessions(): return {s["lake_session_id"]: s for k in base.truth()["tasks"] for s in k["sessions"]}


def score_rework(ses, cls):
    ts = truth_sessions()
    waste = {"switched", "abandoned"}
    tot = {m: sum(measures(x)[m] for x in ses.values()) for m in ("cost", "minutes")}
    out = {}
    for m in ("cost", "minutes"):
        out[m] = {"estimate_redone": r(sum(measures(ses[i])[m] for i in ses if cls[i] == "redone") / tot[m]),
                  "estimate_at_risk": r(sum(measures(ses[i])[m] for i in ses if cls[i] != "clean") / tot[m]),
                  "true_switched": r(sum(measures(ses[i])[m] for i in ses if ts[i]["fate"] == "switched") / tot[m]),
                  "true_waste": r(sum(measures(ses[i])[m] for i in ses if ts[i]["fate"] in waste) / tot[m])}
    def pr(est, true):
        return prf(sum(cls[i] in est and ts[i]["fate"] in true for i in ses), sum(cls[i] in est and ts[i]["fate"] not in true for i in ses),
                   sum(cls[i] not in est and ts[i]["fate"] in true for i in ses))
    out["redone_vs_switched"] = pr({"redone"}, {"switched"})
    out["trouble_vs_abandoned"] = pr({"ended_in_trouble"}, {"abandoned"})
    out["at_risk_vs_waste"] = pr({"redone", "ended_in_trouble"}, waste)
    out["true_fates"] = dict(collections.Counter(ts[i]["fate"] for i in ses))
    return out


def score_correct(sid, ts):
    """SCORING ONLY. True when the session is verified correct, False when verified wrong, None when it has no checked turn."""
    s = ts[sid]; ver = [c for c in s["turn_checks"] if c]
    if not ver: return None
    return all(all(c) for c in ver) and not s["truncated"] and s["fate"] == "completed"


def score_finished(ses, tasks):
    """SCORING ONLY. Tasks whose true final session completed, by the platform of the rebuilt task's final session."""
    ts = truth_sessions()
    return dict(collections.Counter(ses[k["sessions"][-1]]["platform"] if ts[k["sessions"][-1]]["fate"] == "completed" else "unfinished" for k in tasks))


# ---------------------------------------------------------------- cost per task and licence

def cost_per_task(ses, tasks):
    ts = truth_sessions()
    rows = {}
    for p in P + ["total"]:
        ks = [k for k in tasks if p == "total" or ses[k["sessions"][0]]["platform"] == p]
        cost = lambda k: sum(ses[s]["cost"] for s in k["sessions"])
        n_ses = sum(len(k["sessions"]) for k in ks); total = sum(cost(k) for k in ks)
        ok = [score_correct(k["sessions"][-1], ts) for k in ks]
        checked = [k for k, o in zip(ks, ok) if o is not None]; n_ok = sum(o is True for o in ok)
        rows[p] = {"tasks": len(ks), "sessions": n_ses, "cost": r(total, 6),
                   "cost_per_session": r(total / n_ses, 6) if n_ses else None, "cost_per_task": r(total / len(ks), 6) if ks else None,
                   "cost_per_task_first_session_only": r(sum(ses[k["sessions"][0]]["cost"] for k in ks) / len(ks), 6) if ks else None,
                   "tasks_checked": len(checked), "tasks_unchecked": len(ks) - len(checked), "tasks_correct": n_ok,
                   "cost_per_correct_task": r(sum(cost(k) for k in checked) / n_ok, 6) if n_ok else None}
        rows[p]["ratio_correct_to_session"] = r(rows[p]["cost_per_correct_task"] / rows[p]["cost_per_session"], 2) \
            if rows[p]["cost_per_correct_task"] and rows[p]["cost_per_session"] else None
    return rows


def licence(ses, cpt, days):
    seats = base.seat_list(); out = {}
    for p in P + ["total"]:
        ss = [s for s in seats if p == "total" or s["platform"] == p]
        monthly = sum(s["monthly_price"] for s in ss); lic = monthly * days / DAYS_PER_MONTH
        tok = sum(x["cost"] for x in ses.values() if p == "total" or x["platform"] == p)
        c = cpt[p]; per_task = c["cost_per_task"]
        out[p] = {"seats": len(ss), "monthly": monthly, "licence_window": r(lic, 2), "shadow_token_cost_window": r(tok, 4),
                  "licence_to_token": r(lic / tok, 1) if tok else None,
                  "licence_per_task_started": r(lic / c["tasks"], 3) if c["tasks"] else None,
                  "licence_per_correct_task": r(lic / c["tasks_correct"], 3) if c["tasks_correct"] else None,
                  "breakeven_tasks_per_seat_month": r(monthly / len(ss) / per_task, 0) if per_task and ss else None}
    return out


# ---------------------------------------------------------------- markdown

def pp(a, b): return f"{100 * (a - b):+.0f} pp"


def markdown(o, ses, tasks):
    L = ["# Tasks: what changes when the unit is the task", "",
         f"Computed by `tasks.py` from {len(ses)} sessions and {sum(len(x['turns']) for x in ses.values())} user turns in `data/lake_otel.jsonl`. "
         f"Tasks are rebuilt with the fixed rule in `base.rebuild_tasks`: {len(tasks)} tasks. Columns marked (truth) use the ground truth and "
         "are there to score the estimate; a real deployment would need sampled checks for them.", ""]

    s = o["rebuild"]; lk = s["links"]
    L += ["## Rebuild quality (scored against truth)", "",
          table(["Measure", "Value"], [["Rebuilt tasks", s["rebuilt_tasks"]], ["True tasks", s["true_tasks"]],
                                       ["Rebuilt chains equal to a true chain", share(s["exact_chains"], s["true_tasks"])],
                                       ["'B continues A' links: precision", share(lk["tp"], lk["tp"] + lk["fp"])],
                                       ["'B continues A' links: recall", share(lk["tp"], lk["tp"] + lk["fn"])]]), "",
          f"- {s['exact_chains']} of {s['true_tasks']} true chains are rebuilt exactly.",
          f"- The rule finds {lk['tp']} of {lk['tp'] + lk['fn']} true links and adds {lk['fp']} false ones.",
          "- Every re-ask here was re-worded and came 2 to 12 minutes later by design, so the rule has an easy case. Real switches may be slower or vaguer.", ""]

    sh = o["shares"]; tf = o["score_finished"]
    N = {k: sum(v.values()) for k, v in sh.items()}; nfin = N["tasks_finished"] - sh["tasks_finished"].get("unfinished", 0)
    rows = [[base.NAME[p], share(sh["sessions"].get(p, 0), N["sessions"]), share(sh["task_starts"].get(p, 0), N["task_starts"]),
             share(sh["tasks_finished"].get(p, 0), nfin), pp(sh["sessions"].get(p, 0) / N["sessions"], sh["tasks_finished"].get(p, 0) / nfin) if nfin else "–",
             tf.get(p, 0)] for p in P]
    rows += [["Not finished (ends in trouble)", "", "", f"{sh['tasks_finished'].get('unfinished', 0)} of {N['tasks_finished']} tasks", "", tf.get("unfinished", 0)]]
    L += ["## Platform share, three ways", "",
          "Session share: sessions on the platform. Task starts: the first session of a rebuilt task. Finished: the last session of the task "
          "is on the platform and its last turn shows no trouble; the share is of finished tasks.", "",
          table(["Platform", "Sessions", "Task starts", "Tasks finished", "Session share − finished share", "Truly completed there (truth)"], rows), ""]
    gap = max(P, key=lambda p: abs(sh["sessions"].get(p, 0) / N["sessions"] - sh["tasks_finished"].get(p, 0) / nfin)) if nfin else P[0]
    L += [f"- {base.NAME[gap]} moves most between the views: {share(sh['sessions'].get(gap, 0), N['sessions'])} of sessions against "
          f"{share(sh['tasks_finished'].get(gap, 0), nfin)} of finished tasks.",
          f"- {sh['tasks_finished'].get('unfinished', 0)} of {N['tasks_finished']} tasks end in trouble by the spans; the truth says "
          f"{tf.get('unfinished', 0)} did not complete. The trouble flag counts some good endings as trouble (see the scoring table).",
          "- The session share counts a fallback session as new use. The task view counts the work once, where it started and where it ended.", ""]

    rw = o["rework"]
    rows = []
    for p in P + ["total"]:
        for c in CLASSES + ["all"]:
            m = rw.get(f"{p} {c}")
            if not m: continue
            rows.append([base.NAME.get(p, "Total"), c.replace("_", " "), f"{m['sessions']:g}" + (" small n" if m["sessions"] < 5 else ""), m["turns"], m["requests"], f"{m['tokens']:,}", usd(m["cost"]), f"{m['minutes']:.0f}"])
    L += ["## Rework by session class", "",
          "redone: a later session of the same rebuilt task follows it. ended in trouble: the last session of its task, and its last turn has "
          "no answer, a tool error or an inability phrase. clean: the rest. Cost is shadow cost in USD; time is session end minus start.", "",
          table(["Platform", "Class", "Sessions", "User turns", "Model requests", "Tokens in+out", "Shadow cost", "People minutes"], rows), ""]
    t = rw["total all"]
    L += [f"- {rw.get('total redone', {}).get('sessions', 0)} of {t['sessions']} sessions were re-done elsewhere and "
          f"{rw.get('total ended_in_trouble', {}).get('sessions', 0)} ended their task in trouble.",
          "- People minutes include the time a person reads and types between turns, so they are the span of a session, not effort. "
          "A one-turn session counts only the wait for its reply, so time is low for Chatly.",
          f"- Re-done sessions are short: {rw.get('total redone', {}).get('turns', 0):g} user turns in {rw.get('total redone', {}).get('sessions', 0):g} sessions. "
          "People stop at the first failed turn, so a re-done session is short and costs less than a clean one.", ""]

    rows = [[base.NAME.get(p, "Total"), rw[f"{p} all"]["sessions"], f"{100 * rw[f'{p} all']['cost_share_redone']:.0f}%", f"{100 * rw[f'{p} all']['cost_share_at_risk']:.0f}%",
             f"{100 * rw[f'{p} all']['minutes_share_redone']:.0f}%", f"{100 * rw[f'{p} all']['minutes_share_at_risk']:.0f}%"]
            + (["small n"] if rw[f"{p} all"]["sessions"] < 5 else [""]) for p in P + ["total"]]
    L += ["## Share spent on work that was re-done", "",
          "Re-done is a lower bound of waste. At risk (re-done + ended in trouble) is an upper bound, because the trouble flag over-counts.", "",
          table(["Platform", "Sessions (n)", "Cost re-done", "Cost at risk", "Time re-done", "Time at risk", "Note"], rows), ""]
    L += [f"- Across all {t['sessions']} sessions, {100 * t['cost_share_redone']:.0f}% of shadow cost and {100 * t['minutes_share_redone']:.0f}% of people time went to work that was re-done.",
          f"- Up to {100 * t['cost_share_at_risk']:.0f}% of cost and {100 * t['minutes_share_at_risk']:.0f}% of time is at risk.",
          f"- {base.NAME[max(P, key=lambda p: rw[f'{p} all']['cost_share_at_risk'])]} has the largest share of cost at risk.", ""]

    sc = o["score_rework"]
    rows = [[k, f"{100 * sc['cost'][k]:.0f}%", f"{100 * sc['minutes'][k]:.0f}%"] for k in ("estimate_redone", "true_switched", "estimate_at_risk", "true_waste")]
    L += ["## Rework estimate against truth", "", f"True fates of the {len(ses)} sessions: " + ", ".join(f"{k} {v}" for k, v in sorted(sc["true_fates"].items())) + ".", "",
          table(["Share of", "Shadow cost", "People time"], [[x[0].replace("_", " ") + (" (truth)" if x[0].startswith("true") else " (spans)"), x[1], x[2]] for x in rows]), "",
          table(["Spans class", "Truth fate", "Precision", "Recall"],
                [[a, b, share(sc[k]["tp"], sc[k]["tp"] + sc[k]["fp"]), share(sc[k]["tp"], sc[k]["tp"] + sc[k]["fn"])]
                 for k, a, b in (("redone_vs_switched", "redone", "switched"), ("trouble_vs_abandoned", "ended in trouble", "abandoned"),
                                 ("at_risk_vs_waste", "redone or ended in trouble", "switched or abandoned"))]), ""]
    a, b = sc["redone_vs_switched"], sc["trouble_vs_abandoned"]
    L += [f"- The re-done share of cost is {100 * sc['cost']['estimate_redone']:.0f}% from spans against {100 * sc['cost']['true_switched']:.0f}% truly switched.",
          f"- The true waste (switched or abandoned) is {100 * sc['cost']['true_waste']:.0f}% of cost and {100 * sc['minutes']['true_waste']:.0f}% of time; "
          f"the spans bracket it at {100 * sc['cost']['estimate_redone']:.0f}% to {100 * sc['cost']['estimate_at_risk']:.0f}% of cost.",
          f"- 'Ended in trouble' finds {b['tp']} of {b['tp'] + b['fn']} abandoned sessions, and {b['fp']} of its {b['tp'] + b['fp']} flags are false.",
          f"- 'Re-done' finds {a['tp']} of {a['tp'] + a['fn']} switched sessions with {a['fp']} false.", ""]

    cp = o["cost_per_task"]
    rows = [[base.NAME.get(p, "Total"), c["sessions"], c["tasks"], usd(c["cost_per_session"]), usd(c["cost_per_task_first_session_only"]), usd(c["cost_per_task"]),
             f"{c['tasks_correct']} of {c['tasks_checked']}" + (" small n" if c["tasks_checked"] < 5 else ""), c["tasks_unchecked"],
             (usd(c["cost_per_correct_task"]) + (" small n" if c["tasks_correct"] < 5 else "")) if c["cost_per_correct_task"] else "none correct",
             f"{c['ratio_correct_to_session']:.1f}x" if c["ratio_correct_to_session"] else "–"] for p, c in cp.items()]
    L += ["## Cost per task, with and without rework", "",
          "Grouped by the platform where the task started. Cost from spans (shadow USD). A task is verified correct (truth) when its final session has "
          "at least one checked turn, every checked turn in it is correct, it is not cut short and its fate is completed. Tasks whose final session "
          "has no checked turn are left out of the last two columns. In practice this column needs sampled checks of answers.", "",
          table(["Started on", "Sessions", "Tasks", "Cost per session", "Cost per task, first session only", "Cost per task, all sessions",
                 "Correct of checked (truth)", "Unchecked", "Cost per correct task", "Correct-task cost / session cost"], rows), ""]
    T = cp["total"]
    L += [f"- Over all {T['tasks']} tasks, a task costs {usd(T['cost_per_task'])} against {usd(T['cost_per_session'])} per session.",
          f"- Per verified-correct task the cost is {usd(T['cost_per_correct_task'] or 0)}, {T['ratio_correct_to_session'] or 0:.1f} times the cost per session "
          f"({T['tasks_correct']} correct of {T['tasks_checked']} checked; {T['tasks_unchecked']} tasks have no checked turn).",
          "- The per-platform cells rest on few correct tasks; read the ratio as a direction, not a measure.", ""]

    lc = o["licence"]; d = o["window"]
    rows = [[base.NAME.get(p, "Total"), c["seats"], c["monthly"], usd(c["licence_window"]), usd(c["shadow_token_cost_window"]),
             f"{c['licence_to_token']:,.0f}x" if c["licence_to_token"] else "–",
             money(c["licence_per_task_started"], o["cost_per_task"][p]["tasks"]), money(c["licence_per_correct_task"], o["cost_per_task"][p]["tasks_correct"]),
             f"{c['breakeven_tasks_per_seat_month']:,.0f}" if c["breakeven_tasks_per_seat_month"] else "–"] for p, c in lc.items()]
    L += ["## Licence against tokens", "",
          f"Licence in the window = monthly price × seats × {d['working_days']}/{DAYS_PER_MONTH} (working days in the data / working days in a month). "
          "Per task and per correct task use the platform where the task started. Break-even: the tasks per seat per month at which shadow token cost "
          "per task (all sessions) times tasks equals the mean seat price.", "",
          table(["Platform", "Seats", "Price per month", "Licence in window", "Shadow token cost in window", "Licence / tokens",
                 "Licence per task started", "Licence per correct task", "Break-even tasks per seat per month"], rows), ""]
    L += [f"- In the window the seats cost {usd(lc['total']['licence_window'])} and the tokens {usd(lc['total']['shadow_token_cost_window'])} at list price: "
          f"the licence is {lc['total']['licence_to_token']:,.0f} times the token cost. A seat decision should look at the licence first.",
          f"- A seat would cost the same as tokens at about {lc['total']['breakeven_tasks_per_seat_month']:,.0f} tasks per seat per month. "
          f"The simulated staff did {d['tasks_per_person_week']:.1f} tasks per person per week ({len(tasks)} tasks, {d['people']} people, {d['weeks']:g} weeks).",
          "- Shadow cost is the list price of paid twins of the free models that answered, not a bill. Heavy real users would close the gap.", ""]
    return "\n".join(L)


def main():
    ses = base.sessions(); tasks = base.rebuild_tasks(ses); cls = classify(ses, tasks)
    spans = base.jl(os.path.join(base.D, "lake_otel.jsonl"))
    days, people = working_days(ses), len(base.directory())
    o = {"window": {"working_days": days, "days_per_month": DAYS_PER_MONTH, "people": people, "weeks": days / 5,
                    "tasks_per_person_week": r(len(tasks) / people / (days / 5), 2)},
         "rebuild": score_rebuild(tasks), "shares": shares(ses, tasks), "score_finished": score_finished(ses, tasks),
         "rework": rework(ses, cls), "score_rework": score_rework(ses, cls), "cost_per_task": cost_per_task(ses, tasks)}
    o["licence"] = licence(ses, o["cost_per_task"], days)
    # reconciliation
    roots = {base.A(s)["gen_ai.conversation.id"] for s in spans if s["parent_span_id"] is None}
    all_cost = sum(base.cost(s) for s in spans if base.op(s) == "chat")
    assert sorted(i for k in tasks for i in k["sessions"]) == sorted(ses) == sorted(roots), "every session is in exactly one task"
    assert sum(o["shares"]["sessions"].values()) == len(ses) and sum(o["shares"]["tasks_finished"].values()) == len(tasks)
    tot = o["rework"]["total all"]
    assert tot["requests"] == sum(base.op(s) == "chat" for s in spans) and tot["turns"] == len([s for s in spans if s["parent_span_id"] is None])
    assert abs(tot["cost"] - all_cost) < 1e-6 and abs(o["licence"]["total"]["shadow_token_cost_window"] - all_cost) < 1e-4
    assert abs(sum(o["rework"][f"total {c}"]["cost"] for c in CLASSES if f"total {c}" in o["rework"]) - all_cost) < 1e-6
    assert o["cost_per_task"]["total"]["sessions"] == len(ses) and abs(o["cost_per_task"]["total"]["cost"] - all_cost) < 1e-5
    assert o["licence"]["total"]["monthly"] == sum(s["monthly_price"] for s in base.seat_list())
    base.save("tasks.json", o)
    open(os.path.join(base.D, "tasks.md"), "w").write(markdown(o, ses, tasks))
    t, s = o["rework"]["total all"], o["score_rework"]["cost"]
    print(f"{len(ses)} sessions, {len(tasks)} tasks; exact chains {o['rebuild']['exact_chains']}/{o['rebuild']['true_tasks']}")
    print(f"cost re-done {t['cost_share_redone']:.0%}, at risk {t['cost_share_at_risk']:.0%}; truth: switched {s['true_switched']:.0%}, waste {s['true_waste']:.0%}")
    print(f"licence/tokens {o['licence']['total']['licence_to_token']}x. Wrote data/tasks.json and data/tasks.md")


if __name__ == "__main__":
    main()
