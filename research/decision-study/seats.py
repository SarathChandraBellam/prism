"""When can a seat be called unused? Per-seat evidence from spans, three flag rules, and a window-length design study.

    python3 seats.py            # writes data/seats.json and data/seats.md

Part 1 is computed from spans only: sessions and rebuilt tasks (base.sessions, base.rebuild_tasks) per seat, and three
rules. R1: under 10% of the holder's sessions. R2: under 10% of the holder's task starts. R3, the evidence rule: flag
only if P(X <= k | n, 0.10) < 0.05, where k is the task starts on the seat and n the holder's task starts on all seats.
The designed habits from ground truth are read in `designed()` and used only to score the rules.

Part 2 is a DESIGN STUDY BY SIMULATION, not a measurement: it draws task starts from the designed habits (truth
start_weight) at each holder's observed task rate, for windows of 2 to 26 weeks, and at 5 times that volume. Part 3
adds the break-even cost ratio for acting on a flag. Standard library only. No model. Seeded, so a rerun gives the same
files.
"""
import collections, functools, math, os, random

import base

SEED, RUNS, SHARE, ALPHA = 20261116, 4000, 0.10, 0.05
WEEKS, BUSY = [2, 4, 8, 13, 26], 5


@functools.lru_cache(maxsize=None)
def binom_cdf(k, n, p=SHARE):
    """P(X <= k) for X ~ Binomial(n, p)."""
    return sum(math.comb(n, i) * p ** i * (1 - p) ** (n - i) for i in range(k + 1))


def r2(k, n): return n > 0 and k / n < SHARE                # no task start at all is no evidence of a share
def r3(k, n): return binom_cdf(k, n) < ALPHA


def n_star():
    """Smallest n at which zero task starts passes R3."""
    n = 0
    while not r3(0, n): n += 1
    return n


def poisson(rng, lam):
    """Poisson draw by inversion (exact; lam here is at most a few hundred)."""
    if lam <= 0: return 0
    k, p = 0, math.exp(-lam); c, u = p, rng.random()
    while u > c and p > 0:
        k += 1; p *= lam / k; c += p
    return k


def prf(tp, fp, fn):
    return {"tp": tp, "fp": fp, "fn": fn, "precision": round(tp / (tp + fp), 3) if tp + fp else None, "recall": round(tp / (tp + fn), 3) if tp + fn else None}


def designed():
    """SCORING AND SIMULATION ONLY: the designed habit per seat, from ground truth."""
    return {(s["handle"], s["platform"]): s for s in base.truth()["seats"]}


# ---------------------------------------------------------------- 1. evidence from spans

def evidence(ses, tasks, seats):
    sess, starts, last = collections.Counter(), collections.Counter(), {}
    for x in ses.values():
        k = (x["user"], x["platform"]); sess[k] += 1
        last[k] = max(last.get(k, x["start"]), x["start"])
    for t in tasks: starts[(t["user"], ses[t["sessions"][0]]["platform"])] += 1
    held = {(s["handle"], s["platform"]) for s in seats}
    assert set(sess) <= held, "a session on a seat the person does not hold"
    days = (max(x["end"] for x in ses.values()).date() - min(x["start"] for x in ses.values()).date()).days + 1
    weeks = math.ceil(days / 7)
    rows = []
    for s in seats:
        u, p = s["handle"], s["platform"]
        ns = sum(v for (h, _), v in sess.items() if h == u); n = sum(v for (h, _), v in starts.items() if h == u)
        k, m = starts[(u, p)], sess[(u, p)]
        f1, f2, f3 = (m / ns if ns else 0) < SHARE, r2(k, n), r3(k, n)
        rows.append({"handle": u, "platform": p, "price": s["monthly_price"], "sessions": m, "holder_sessions": ns, "task_starts": k,
                     "holder_starts": n, "p_le_k": round(binom_cdf(k, n), 4), "fallback_only": m > 0 and k == 0,
                     "last_use": last[(u, p)].date().isoformat() if (u, p) in last else None, "R1": f1, "R2": f2, "R3": f3,
                     "verdict": "unused (evidence)" if f3 else "quiet, not enough evidence" if f2 else "in use"})
    assert len(rows) == len(seats) and sum(r["task_starts"] for r in rows) == len(tasks) and sum(r["sessions"] for r in rows) == len(ses)
    return rows, weeks


def score(rows, des):
    out = {}
    for rule in ("R1", "R2", "R3"):
        idle = lambda r: des[(r["handle"], r["platform"])]["designed_idle"]
        tp = sum(r[rule] and idle(r) for r in rows); fp = sum(r[rule] and not idle(r) for r in rows); fn = sum(idle(r) and not r[rule] for r in rows)
        out[rule] = prf(tp, fp, fn) | {"flagged": tp + fp, "saving": sum(r["price"] for r in rows if r[rule]),
                                      "wrong_price": sum(r["price"] for r in rows if r[rule] and not idle(r))}
    return out


# ---------------------------------------------------------------- 2. window length (design study, uses the designed habits)

def simulate(rate, des, seats, w, mult, rng):
    """RUNS draws of W weeks. A holder's task starts on a seat are Poisson(rate x W x weight), the weights normalised per
    holder; that is the same as a Poisson total split by the weights."""
    price = {(s["handle"], s["platform"]): s["monthly_price"] for s in seats}
    by = collections.defaultdict(list)
    for (u, p) in price: by[u].append(p)
    wsum = {u: sum(des[(u, p)]["start_weight"] for p in ps) for u, ps in by.items()}
    acc = {r: collections.Counter() for r in ("R2", "R3")}; per_seat = {r: collections.Counter() for r in ("R2", "R3")}
    for _ in range(RUNS):
        hit = {"R2": [], "R3": []}
        for u, ps in by.items():
            k = {p: poisson(rng, rate[u] * mult * w * des[(u, p)]["start_weight"] / wsum[u]) for p in ps}; n = sum(k.values())
            for p in ps:
                if r2(k[p], n): hit["R2"].append((u, p))
                if r3(k[p], n): hit["R3"].append((u, p))
        for rule, fl in hit.items():
            a = acc[rule]; wrong = [s for s in fl if not des[s]["designed_idle"]]
            a["flagged"] += len(fl); a["tp"] += len(fl) - len(wrong); a["fp"] += len(wrong)
            a["saving"] += sum(price[s] for s in fl if des[s]["designed_idle"]); a["wrong_price"] += sum(price[s] for s in wrong)
            a["any_wrong"] += bool(wrong)
            for s in fl: per_seat[rule][s] += 1
    n_idle = sum(des[s]["designed_idle"] for s in price)
    res = {}
    for rule, a in acc.items():
        p = a["tp"] / a["flagged"] if a["flagged"] else None
        res[rule] = {"mean_flagged": round(a["flagged"] / RUNS, 2), "precision": None if p is None else round(p, 3),
                     "recall": round(a["tp"] / (RUNS * n_idle), 3), "mean_saving": round(a["saving"] / RUNS, 1),
                     "mean_wrong_price": round(a["wrong_price"] / RUNS, 1), "share_runs_wrong": round(a["any_wrong"] / RUNS, 3),
                     "break_even": None if p is None or p == 1 else round(p / (1 - p), 2),
                     "flag_rate": {f"{u}/{q}": round(per_seat[rule][(u, q)] / RUNS, 3) for (u, q) in sorted(price)}}
    return res


# ---------------------------------------------------------------- markdown

def table(head, rows):
    return "\n".join(["| " + " | ".join(head) + " |", "|" + "---|" * len(head)] + ["| " + " | ".join(map(str, r)) + " |" for r in rows])


def share(k, n):
    if not n: return "– (0/0)"
    lo, hi = base.wilson(k, n)
    return f"{100 * k / n:.0f}% ({k}/{n}, {100 * lo:.0f}–{100 * hi:.0f}%)" + (" small n" if n < 5 else "")


def markdown(res):
    rows, sc, des, sim = res["seats"], res["scores"], res["designed"], res["simulation"]
    yes = lambda b: "yes" if b else ""
    L = ["# When can a seat be called unused?", "",
         f"Window: {res['window_weeks']} weeks of spans. A task start is the first session of a rebuilt task. R1: under 10% of the holder's sessions. "
         "R2: under 10% of the holder's task starts. R3: P(X ≤ k | n, 0.10) < 0.05 for k starts on the seat out of n by the holder. "
         "'Designed idle' (start weight under 5%) comes from ground truth and is used only to score.", ""]
    L += ["## 1a. Per-seat evidence from spans", "",
          table(["Holder", "Platform", "$/month", "Sessions (share)", "Task starts k/n", "P(X ≤ k)", "Last use", "R1", "R2", "R3", "Verdict", "Designed idle"],
                [[r["handle"], base.NAME[r["platform"]], r["price"], share(r["sessions"], r["holder_sessions"]), share(r["task_starts"], r["holder_starts"]),
                  r["p_le_k"], r["last_use"] or "never", yes(r["R1"]), yes(r["R2"]), yes(r["R3"]),
                  r["verdict"] + (", fallback only" if r["fallback_only"] else ""), yes(des[f"{r['handle']}/{r['platform']}"]["designed_idle"])] for r in rows]), ""]
    quiet = [r for r in rows if r["verdict"].startswith("quiet")]; fb = [r for r in rows if r["fallback_only"]]
    L += [f"- {len(quiet)} seats are quiet (R2 flags them) but R3 finds not enough evidence. {sum(r['R3'] for r in rows)} seats are unused on the evidence rule.",
          f"- The largest holder sample is {max(r['holder_starts'] for r in rows)} task starts in {res['window_weeks']} weeks; R3 needs {res['n_star']} with zero on the seat.",
          f"- {len(fb)} {'seat is' if len(fb) == 1 else 'seats are'} fallback only (sessions but no task start): {', '.join(r['handle'] + '/' + base.NAME[r['platform']] for r in fb) or 'none'}. "
          "Such a seat is used after a failure elsewhere; cancelling it removes the fallback.", ""]

    L += ["## 1b. The three rules against the designed idle seats", "",
          table(["Rule", "Flagged", "Correct", "Wrong", "Missed", "Precision", "Recall", "Saving of the flags $/month", "Price of wrong flags $/month"],
                [[k, v["flagged"], v["tp"], v["fp"], v["fn"], share(v["tp"], v["flagged"]), share(v["tp"], v["tp"] + v["fn"]), v["saving"], v["wrong_price"]]
                 for k, v in sc.items()]), ""]
    L += [f"- R1 flags {sc['R1']['flagged']} seats with {sc['R1']['fp']} wrong; R2 flags {sc['R2']['flagged']} with {sc['R2']['fp']} wrong. "
          f"{res['designed_idle']} seats are designed idle, worth {res['designed_saving']} $/month.",
          f"- R3 flags {sc['R3']['flagged']} seats. In {res['window_weeks']} weeks no holder has enough task starts for the evidence rule to fire.",
          "- The scores use 24 seats and one window; one seat moves precision by many points.", ""]

    hs = res["holders"]
    L += ["## 1c. How long until zero starts is evidence", "",
          f"Zero task starts on a seat passes R3 once the holder has made {res['n_star']} task starts (0.9^n < 0.05).", "",
          table(["Holder", "Seats", f"Task starts in {res['window_weeks']} weeks", "Starts per week", "Weeks to reach n*", "More weeks needed"],
                [[h["handle"], h["seats"], h["starts"], h["rate"], h["weeks_total"], h["weeks_more"]] for h in hs]), ""]
    multi = [h for h in hs if h["seats"] > 1]
    L += [f"- For holders with more than one seat, the extra wait runs from {min(h['weeks_more'] for h in multi)} to {max(h['weeks_more'] for h in multi)} weeks at their observed rate.",
          "- The rate comes from one two-week window; for holders with one or two tasks it is very uncertain.",
          "- Holders with one seat cannot have a seat flagged: their only seat holds every start.", ""]

    W = res["weeks"]; nm = lambda v: "–" if v is None else v
    for key, title in (("normal", "observed task rates"), ("busy", f"task rates x {BUSY}")):
        L += [f"## 2{'a' if key == 'normal' else 'b'}. Window length, {title} (design study: simulated from the designed habits)", "",
              f"{RUNS} runs per window. Precision and recall pool all runs. Saving counts correctly flagged seats only.", "",
              table(["Rule", "Weeks", "Mean flagged", "Precision", "Recall", "Mean saving $/month", "Mean price of wrong flags $/month", "Runs with a wrong flag", "Break-even cost ratio"],
                    [[rule, w, sim[key][str(w)][rule]["mean_flagged"], nm(sim[key][str(w)][rule]["precision"]), sim[key][str(w)][rule]["recall"],
                      sim[key][str(w)][rule]["mean_saving"], sim[key][str(w)][rule]["mean_wrong_price"], f"{100 * sim[key][str(w)][rule]['share_runs_wrong']:.0f}%",
                      nm(sim[key][str(w)][rule]["break_even"]) if sim[key][str(w)][rule]["precision"] != 1 else "no wrong flags"]
                     for rule in ("R2", "R3") for w in W]), ""]
        a, z = sim[key][str(W[0])], sim[key][str(W[-1])]
        first = next((w for w in W if sim[key][str(w)]["R3"]["recall"] >= 0.5), None)
        L += [f"- R2 has a wrong flag in {100 * a['R2']['share_runs_wrong']:.0f}% of {W[0]}-week runs and {100 * z['R2']['share_runs_wrong']:.0f}% of {W[-1]}-week runs.",
              (f"- R3 never flags a seat in use in any of the {RUNS} runs at any window. " if not any(sim[key][str(w)]['R3']['share_runs_wrong'] for w in W) else
               f"- R3 has a wrong flag in at most {100 * max(sim[key][str(w)]['R3']['share_runs_wrong'] for w in W):.1f}% of runs at any window. ")
              + f"The price is recall: {a['R3']['recall']} at {W[0]} weeks, {z['R3']['recall']} at {W[-1]} weeks.",
              f"- R3 finds half the idle seats first at {first} weeks." if first else f"- R3 never finds half the idle seats within {W[-1]} weeks.", ""]
    L += [f"- The break-even ratio is p/(1−p) for precision p. Acting on a flag pays when the cost of wrongly cancelling a seat "
          "(lost work, re-buying it) is below that ratio times the monthly saving. At precision 0.5 the cost must be below one month's saving; at 0.9, below nine.", ""]

    idle = [k for k, v in des.items() if v["designed_idle"]]
    L += ["## 2c. How often each designed idle seat is flagged (design study)", "",
          table(["Seat", "Designed start weight"] + [f"R2/R3 at {w} wk" for w in W] + [f"R3 at {w} wk, busy" for w in (W[0], W[-1])],
                [[k, des[k]["start_weight"]] + [f"{100 * sim['normal'][str(w)]['R2']['flag_rate'][k]:.0f}% / {100 * sim['normal'][str(w)]['R3']['flag_rate'][k]:.0f}%" for w in W]
                 + [f"{100 * sim['busy'][str(w)]['R3']['flag_rate'][k]:.0f}%" for w in (W[0], W[-1])] for k in sorted(idle)]), ""]
    edge = [k for k in idle if des[k]["start_weight"] > 0]
    for k in edge:
        obs = next((r for r in res["seats"] if f"{r['handle']}/{r['platform']}" == k), None)
        L += [f"- {k} is designed idle with a start weight of {des[k]['start_weight']}, so it is used sometimes. Both rules compare the share with 10%, "
              f"so with enough starts they flag it and count the flag as correct: R3 flags it in {100 * sim['normal'][str(W[-1])]['R3']['flag_rate'][k]:.0f}% of "
              f"{W[-1]}-week runs. Each start on it delays R3, which needs more evidence for a share of 1 in n than for 0 in n."
              + (f" In the window it had {obs['sessions']} sessions and {obs['task_starts']} task starts: the rules count starts, not fallback use." if obs else "")]
    wrong = max((k for k, v in des.items() if not v["designed_idle"]), key=lambda k: sim["normal"][str(W[0])]["R2"]["flag_rate"][k])
    L += [f"- The seat in use that R2 flags most often is {wrong} (start weight {des[wrong]['start_weight']}): {100 * sim['normal'][str(W[0])]['R2']['flag_rate'][wrong]:.0f}% "
          f"of {W[0]}-week runs and {100 * sim['normal'][str(W[-1])]['R2']['flag_rate'][wrong]:.0f}% of {W[-1]}-week runs."]
    L += ["- A zero-weight seat can only be flagged once its holder has enough starts; holders with few tasks keep their idle seats unflagged.", ""]
    return "\n".join(L)


def main():
    rng = random.Random(SEED)
    ses = base.sessions(); tasks = base.rebuild_tasks(ses); seats = base.seat_list()
    rows, weeks = evidence(ses, tasks, seats)                      # from spans only
    des = designed()                                               # truth: scoring and simulation only
    assert set(des) == {(s["handle"], s["platform"]) for s in seats}, "truth seats and seat list differ"
    ns = n_star()
    starts = collections.Counter(t["user"] for t in tasks); nseat = collections.Counter(s["handle"] for s in seats)
    rate = {u: starts[u] / weeks for u in nseat}
    holders = [{"handle": u, "seats": nseat[u], "starts": starts[u], "rate": round(rate[u], 2),
                "weeks_total": round(ns / rate[u], 1) if rate[u] else None, "weeks_more": round(max(0.0, ns / rate[u] - weeks), 1) if rate[u] else None}
               for u in sorted(nseat, key=lambda u: (-rate[u], u))]
    sim = {key: {str(w): simulate(rate, des, seats, w, mult, rng) for w in WEEKS} for key, mult in (("normal", 1), ("busy", BUSY))}
    res = {"window_weeks": weeks, "n_star": ns, "seats": rows, "scores": score(rows, des), "holders": holders, "weeks": WEEKS, "runs": RUNS,
           "designed": {f"{u}/{p}": {"start_weight": v["start_weight"], "designed_idle": v["designed_idle"]} for (u, p), v in sorted(des.items())},
           "designed_idle": sum(v["designed_idle"] for v in des.values()),
           "designed_saving": sum(s["monthly_price"] for s in seats if des[(s["handle"], s["platform"])]["designed_idle"]),
           "monthly_spend": sum(s["monthly_price"] for s in seats), "simulation": sim,
           "definitions": {"task_start": "the first session of a task rebuilt by base.rebuild_tasks", "R2_zero_holder": "a holder with no task start gives no share; R2 does not flag",
                           "simulation": "design study: per seat Poisson(holder rate x multiplier x weeks x normalised designed start_weight); holder rate = rebuilt tasks in the window / window weeks",
                           "pooled": "precision and recall pool flags over all runs", "break_even": "p/(1-p): the largest ratio of wrong-cancel cost to monthly saving at which acting on a flag pays"}}
    base.save("seats.json", res)
    open(os.path.join(base.D, "seats.md"), "w").write(markdown(res) + "\n")
    print(f"{len(rows)} seats, {res['monthly_spend']} $/month; window {weeks} weeks; n* = {ns}")
    for k, v in res["scores"].items(): print(f"{k}: flagged {v['flagged']}, precision {v['precision']}, recall {v['recall']}, saving {v['saving']}")
    for w in WEEKS: print(f"W={w}: R2 p={sim['normal'][str(w)]['R2']['precision']} r={sim['normal'][str(w)]['R2']['recall']}; R3 p={sim['normal'][str(w)]['R3']['precision']} r={sim['normal'][str(w)]['R3']['recall']}")
    print("wrote data/seats.json, data/seats.md")


if __name__ == "__main__":
    main()
