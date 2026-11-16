"""What the outcome signal costs: trace signals against checks, what the full matrix supports, and how many checks a
platform choice needs.

    python3 sampling.py         # writes data/sampling.json and data/sampling.md

Four parts. (1) Silent failures: the trace signal `trouble` (no answer, tool error, inability phrase) crossed with the
check result of every verifiable lake turn, per turn and per session. (2) The full 3 platforms x scripts recordings
matrix: pass rates, Fisher's exact test for every pair of platforms, a Holm correction, and a cluster bootstrap with the
script as the unit. (3) A Monte Carlo sampling budget: how many checked turns per platform, or per platform and task
type, pick the right platform. (4) Session-level trace proxies against checks and against the designed fate.

The signals are computed from spans only (base.sessions, base.rebuild_tasks). Ground truth (base.truth) is read in one
place, `scoring()`, and is used only to score those signals and, in part 3, to set the true rates of a simulation that is
labelled as such. Standard library only. No model. Seeded, so a rerun gives the same files.
"""
import collections, itertools, math, os, random

import base

SEED, DRAWS, BOOT = 20261116, 5000, 5000
NS = [3, 5, 10, 20, 30, 50, 100]
PARTS = ["trouble", "no_answer", "tool_error", "inability"]
P = base.PLATFORMS


# ---------------------------------------------------------------- small statistics (standard library)

def binom_pmf(k, n, p): return math.comb(n, k) * p ** k * (1 - p) ** (n - k)


def fisher(a, b, c, d):
    """Two-sided Fisher's exact test for [[a, b], [c, d]]: the sum of the probabilities of all tables with the same
    margins that are no more likely than the one observed."""
    r1, c1, n = a + b, a + c, a + b + c + d
    pr = lambda x: math.comb(c1, x) * math.comb(n - c1, r1 - x) / math.comb(n, r1)
    p0 = pr(a)
    return min(1.0, sum(pr(x) for x in range(max(0, r1 + c1 - n), min(r1, c1) + 1) if pr(x) <= p0 * (1 + 1e-9)))


def holm(ps, alpha=0.05):
    """Holm step-down: which of the p-values stay significant."""
    keep, m = [False] * len(ps), len(ps)
    for rank, i in enumerate(sorted(range(m), key=lambda i: ps[i])):
        if ps[i] > alpha / (m - rank): break
        keep[i] = True
    return keep


def kappa(tp, fp, fn, tn):
    """Cohen's kappa for two yes/no ratings (signal, truth)."""
    n = tp + fp + fn + tn
    if not n: return None
    po = (tp + tn) / n; pe = ((tp + fp) * (tp + fn) + (fn + tn) * (fp + tn)) / n / n
    return None if pe == 1 else (po - pe) / (1 - pe)


def binom(rng, n, p): return sum(rng.random() < p for _ in range(n))


def share(k, n):
    """A rate as JSON: k, n, rate and its 95% Wilson interval."""
    lo, hi = base.wilson(k, n)
    return {"k": k, "n": n, "rate": round(k / n, 3) if n else None, "lo": round(lo, 3), "hi": round(hi, 3)}


def fmt(s, ci=True):
    """'62% (8/13, 35–85%)', with 'small n' under 5 observations."""
    if not s["n"]: return "– (0/0)"
    t = f"{100 * s['rate']:.0f}% ({s['k']}/{s['n']}" + (f", {100 * s['lo']:.0f}–{100 * s['hi']:.0f}%" if ci else "") + ")"
    return t + (" small n" if s["n"] < 5 else "")


def r3(x): return None if x is None else round(x, 3)


# ---------------------------------------------------------------- ground truth: SCORING ONLY

def scoring(ses):
    """SCORING ONLY. Maps truth onto lake sessions: per lake session the turn checks, the fate and the designed task type.
    Returns the full recordings matrix too. Nothing here feeds a signal."""
    t = base.truth()
    per = {}
    for k in t["tasks"]:
        for s in k["sessions"]:
            x = ses[s["lake_session_id"]]
            assert len(x["turns"]) == len(s["turn_checks"]), "lake turns and truth turn checks differ"
            per[s["lake_session_id"]] = {"checks": s["turn_checks"], "fate": s["fate"], "task_type": k["designed"]["task_type"]}
    assert set(per) == set(ses), "every lake session must be in truth"
    for r in t["recordings"].values():
        assert r["verifiable_turns"] == sum(1 for c in r["turn_checks"] if c) and r["passed_turns"] == sum(1 for c in r["turn_checks"] if c and all(c))
    return per, t["recordings"], t["scope"]["scripts"]


# ---------------------------------------------------------------- 1. silent failures

def confusion(pairs):
    """pairs: (signal, failed). Returns counts plus precision, recall and kappa of the signal as a detector of failure."""
    tp = sum(s and f for s, f in pairs); fp = sum(s and not f for s, f in pairs)
    fn = sum(f and not s for s, f in pairs); tn = len(pairs) - tp - fp - fn
    return {"n": len(pairs), "tp": tp, "fp": fp, "fn": fn, "tn": tn, "precision": share(tp, tp + fp), "recall": share(tp, tp + fn),
            "kappa": r3(kappa(tp, fp, fn, tn))}


def silent(ses, sc):
    turns = []                                                     # (platform, turn, failed) for verifiable turns
    for sid, x in ses.items():
        for t, ch in zip(x["turns"], sc[sid]["checks"]):
            if ch: turns.append((x["platform"], t, not all(ch)))
    groups = {p: [z for z in turns if z[0] == p] for p in P} | {"all": turns}
    per_turn, parts, enrich = {}, {}, {}
    for g, zs in groups.items():
        failed = sum(f for _, _, f in zs); sil = sum(f and not t["trouble"] for _, t, f in zs)
        c = confusion([(t["trouble"], f) for _, t, f in zs])
        per_turn[g] = {"verifiable": len(zs), "failed": failed, "silent": share(sil, failed), "false_alarms": c["fp"],
                       "precision": c["precision"], "recall": c["recall"], "kappa": c["kappa"]}
        parts[g] = {s: confusion([(t[s], f) for _, t, f in zs]) for s in PARTS}
        enrich[g] = {"base_rate": share(failed, len(zs)), "given_trouble": c["precision"], "given_no_trouble": share(c["fn"], c["fn"] + c["tn"]),
                     "lift": r3(c["precision"]["rate"] / (failed / len(zs))) if failed and c["precision"]["n"] else None}
    per_ses = {}
    for g in P + ["all"]:
        rows = [(any(t["trouble"] for t in x["turns"]), any(c and not all(c) for c in sc[sid]["checks"]))
                for sid, x in ses.items() if (g == "all" or x["platform"] == g) and any(sc[sid]["checks"])]
        c = confusion(rows)
        per_ses[g] = {"sessions_with_checks": len(rows), "failed": c["tp"] + c["fn"], "silent": share(c["fn"], c["tp"] + c["fn"]),
                      "false_alarms": c["fp"], "precision": c["precision"], "recall": c["recall"], "kappa": c["kappa"]}
    n_ver = sum(1 for sid in ses for c in sc[sid]["checks"] if c)
    assert per_turn["all"]["verifiable"] == n_ver
    return {"per_turn": per_turn, "parts": parts, "per_session": per_ses, "enrichment": enrich}


# ---------------------------------------------------------------- 2. the full matrix

def matrix(rec, scripts, rng):
    types = sorted({r["designed"]["task_type"] for r in rec.values()})
    tt_of = {r["script"]: r["designed"]["task_type"] for r in rec.values()}
    cell = lambda p, tt=None: [rec[f"{p}:{s}"] for s in scripts if tt is None or tt_of[s] == tt]
    kn = lambda rs: (sum(r["passed_turns"] for r in rs), sum(r["verifiable_turns"] for r in rs))
    rates = {p: {"all": share(*kn(cell(p)))} | {tt: share(*kn(cell(p, tt))) for tt in types} for p in P}
    scripts_per = {tt: sum(tt_of[s] == tt for s in scripts) for tt in types}
    tests = []
    for grp in ["all"] + types:
        for p, q in itertools.combinations(P, 2):
            a, b = rates[p][grp], rates[q][grp]
            tests.append({"group": grp, "pair": f"{p}-{q}", "a": f"{a['k']}/{a['n']}", "b": f"{b['k']}/{b['n']}",
                          "diff": r3(a["rate"] - b["rate"]), "p": fisher(a["k"], a["n"] - a["k"], b["k"], b["n"] - b["k"])})
    within = [x for x in tests if x["group"] != "all"]
    for x, h in zip(within, holm([x["p"] for x in within])): x["holm"] = h
    for x in tests: x["p"] = float(f"{x['p']:.4g}")
    # the overall comparison with the script as the unit (paired: one resample of scripts serves both platforms)
    boot = {}
    turns = {p: [ok for s in scripts for ch in rec[f"{p}:{s}"]["turn_checks"] if ch for ok in [all(ch)]] for p in P}
    pct = lambda xs: (xs[int(0.025 * len(xs))], xs[int(0.975 * len(xs)) - 1])
    for p, q in itertools.combinations(P, 2):
        cl, tu = [], []
        for _ in range(BOOT):
            ss = [rng.choice(scripts) for _ in scripts]
            (kp, np_), (kq, nq) = kn([rec[f"{p}:{s}"] for s in ss]), kn([rec[f"{q}:{s}"] for s in ss])
            cl.append(kp / np_ - kq / nq)
            tp_ = [rng.choice(turns[p]) for _ in turns[p]]; tq = [rng.choice(turns[q]) for _ in turns[q]]
            tu.append(sum(tp_) / len(tp_) - sum(tq) / len(tq))
        (cl_lo, cl_hi), (tu_lo, tu_hi) = pct(sorted(cl)), pct(sorted(tu))
        boot[f"{p}-{q}"] = {"diff": r3(rates[p]["all"]["rate"] - rates[q]["all"]["rate"]), "turn_ci": [r3(tu_lo), r3(tu_hi)],
                            "script_ci": [r3(cl_lo), r3(cl_hi)], "width_ratio": r3((cl_hi - cl_lo) / (tu_hi - tu_lo))}
    sig = sum(x["p"] < 0.05 for x in within)
    return {"types": types, "scripts_per_type": scripts_per, "rates": rates, "tests": tests, "within_tests": len(within),
            "within_significant": sig, "within_significant_holm": sum(x["holm"] for x in within), "bootstrap": boot}


# ---------------------------------------------------------------- 3. sampling budget (Monte Carlo, observed rates taken as true)

def pick(counts, rng):
    top = max(counts.values())
    return [p for p in counts if counts[p] == top], rng.choice(sorted(p for p in counts if counts[p] == top))


def simulate(true, n, rng):
    """true: {platform: rate}. n checked turns per platform. A hit: every platform tied at the sample top is a true best
    (so a sample tie between a true best and a worse platform is a miss). Order: every pair with different true rates is
    strictly ordered the same way in the sample (pairs with equal true rates are not scored). Regret: true best rate minus
    the true rate of the platform picked, ties broken at random."""
    best = max(true.values()); hit = order = reg = 0
    pairs = [(p, q) for p, q in itertools.permutations(true, 2) if true[p] > true[q]]
    for _ in range(DRAWS):
        c = {p: binom(rng, n, true[p]) for p in true}
        tops, choice = pick(c, rng)
        hit += all(true[p] == best for p in tops)
        order += all(c[p] > c[q] for p, q in pairs)
        reg += best - true[choice]
    return {"best": hit / DRAWS, "order": order / DRAWS, "regret": reg / DRAWS}


def budget(rec, scripts, mat, ses, sc, rng):
    types = mat["types"]
    plat = {n: simulate({p: mat["rates"][p]["all"]["rate"] for p in P}, n, rng) for n in NS}
    by_type = {tt: {n: simulate({p: mat["rates"][p][tt]["rate"] for p in P}, n, rng) for n in NS} for tt in types}
    mean = {n: {k: sum(by_type[tt][n][k] for tt in types) / len(types) for k in ("best", "order", "regret")} for n in NS}
    first90 = {tt: next((n for n in NS if by_type[tt][n]["best"] >= 0.9), None) for tt in types}
    first90["mean"] = next((n for n in NS if mean[n]["best"] >= 0.9), None)
    lake = collections.Counter()                                   # verifiable turns the window produced per cell
    for sid, x in ses.items():
        lake[(x["platform"], sc[sid]["task_type"])] += sum(1 for c in sc[sid]["checks"] if c)
    total = sum(lake.values()); cells = len(P) * len(types)
    plan = []
    for n in NS:
        short = sorted(f"{p}/{tt}" for p in P for tt in types if lake[(p, tt)] < n)
        plan.append({"n": n, "platform_checks": n * len(P), "type_checks": n * cells, "lake_verifiable": total,
                     "platform_fraction": r3(n * len(P) / total), "type_fraction": r3(n * cells / total),
                     "cells_short": len(short), "short": short})
    rnd = lambda d: {k: r3(v) for k, v in d.items()}
    return {"note": "Monte Carlo: each cell's pass rate in the full recordings matrix is taken as the true rate.", "draws": DRAWS,
            "platform": {str(n): rnd(v) for n, v in plat.items()},
            "by_type": {tt: {str(n): rnd(v) for n, v in d.items()} for tt, d in by_type.items()},
            "mean_over_types": {str(n): rnd(v) for n, v in mean.items()}, "first_n_reaching_90": first90,
            "lake_cells": {f"{p}/{tt}": lake[(p, tt)] for p in P for tt in types}, "plan": plan}


# ---------------------------------------------------------------- 4. proxies at session level

def proxies(ses, tasks, sc):
    nxt = {s for k in tasks for s in k["sessions"][:-1]}           # followed by another session in its rebuilt task
    sig = {sid: {"ends_in_trouble": x["ends_in_trouble"], "any_trouble_turn": any(t["trouble"] for t in x["turns"]),
                 "switched_away": sid in nxt} for sid, x in ses.items()}
    out = {}
    for name in ("ends_in_trouble", "any_trouble_turn", "switched_away"):
        chk = [(sig[s][name], any(c and not all(c) for c in sc[s]["checks"])) for s in ses if any(sc[s]["checks"])]
        out[name] = {"flagged": sum(v[name] for v in sig.values()), "sessions": len(ses),
                     "vs_failed_check": confusion(chk),
                     "vs_not_completed": confusion([(sig[s][name], sc[s]["fate"] != "completed") for s in ses]),
                     "vs_switched": confusion([(sig[s][name], sc[s]["fate"] == "switched") for s in ses])}
    return out


# ---------------------------------------------------------------- markdown

def table(head, rows):
    return "\n".join(["| " + " | ".join(head) + " |", "|" + "---|" * len(head)] + ["| " + " | ".join(map(str, r)) + " |" for r in rows])


def ci(lo, hi): return f"{100 * lo:+.0f} to {100 * hi:+.0f} pts"


def markdown(res):
    s, m, b, x = res["silent"], res["matrix"], res["budget"], res["proxies"]
    G = P + ["all"]; nm = lambda g: base.NAME.get(g, "All")
    L = ["# What the outcome signal costs", "",
         "Data: the decision-study lake (spans only) for the signals; ground truth only to score them (parts 1 and 4) and to "
         "set the true rates of a simulation (part 3). Rates show k/n and a 95% Wilson interval. 'small n' marks fewer than 5 observations.", ""]

    pt = s["per_turn"]; al = pt["all"]
    L += ["## 1a. Silent failures per turn (trace signal `trouble` against the checks)", "",
          table(["Platform", "Verifiable turns", "Failed", "Silent failures (share of failed)", "False alarms", "Precision of trouble", "Recall of trouble", "Kappa"],
                [[nm(g), pt[g]["verifiable"], pt[g]["failed"], fmt(pt[g]["silent"]), pt[g]["false_alarms"], fmt(pt[g]["precision"]),
                  fmt(pt[g]["recall"]), pt[g]["kappa"]] for g in G]), ""]
    worst = max(P, key=lambda g: pt[g]["silent"]["rate"] or 0)
    L += [f"- {al['silent']['k']} of {al['failed']} failed turns ({fmt(al['silent'])}) show no trouble in the trace. " + ("The trace misses most failures." if al["silent"]["rate"] > 0.6 else "The trace misses about half of the failures." if al["silent"]["rate"] >= 0.4 else "The trace misses a sizeable share of failures."),
          f"- Silent failures are highest on {nm(worst)}: {fmt(pt[worst]['silent'])}. On that platform a failed turn usually looks normal in the trace. The cells are small.",
          f"- {al['false_alarms']} turns with trouble passed their checks. Precision of trouble is {fmt(al['precision'])}; recall is {fmt(al['recall'])}.",
          f"- Agreement beyond chance is low: kappa {al['kappa']} over {al['verifiable']} turns. Per-platform cells are small.", ""]

    pa = s["parts"]; notool = res["no_tool_platforms"]
    L += ["## 1b. Each part of the trouble signal", "",
          table(["Signal", "Platform", "Flagged turns", "Precision", "Recall"],
                [[sig, nm(g), pa[g][sig]["tp"] + pa[g][sig]["fp"], fmt(pa[g][sig]["precision"]), fmt(pa[g][sig]["recall"])] for sig in PARTS for g in G]), ""]
    best_part = max(PARTS[1:], key=lambda q: pa["all"][q]["recall"]["rate"] or 0)
    L += [f"- The strongest part is `{best_part}`: recall {fmt(pa['all'][best_part]['recall'])} overall.",
          f"- `tool_error` flags {pa['all']['tool_error']['tp'] + pa['all']['tool_error']['fp']} turns, with precision {fmt(pa['all']['tool_error']['precision'])}. Agents often recover from a failed tool call.",
          (f"- {', '.join(nm(q) for q in notool)} made no tool calls in the window, so `tool_error` cannot fire there. That is a property of the platform, not of its quality."
           if notool else "- Every platform made tool calls."), ""]

    ps = s["per_session"]; pa_ = ps["all"]
    L += ["## 1c. Silent failures per session (any failed check against any trouble turn)", "",
          table(["Platform", "Sessions with checks", "With a failed check", "Silent (share of failed)", "False alarms", "Precision", "Recall", "Kappa"],
                [[nm(g), ps[g]["sessions_with_checks"], ps[g]["failed"], fmt(ps[g]["silent"]), ps[g]["false_alarms"], fmt(ps[g]["precision"]),
                  fmt(ps[g]["recall"]), ps[g]["kappa"]] for g in G]), ""]
    L += [f"- At session level {pa_['silent']['k']} of {pa_['failed']} sessions with a failed check ({fmt(pa_['silent'])}) show no trouble at all.",
          f"- Precision is {fmt(pa_['precision'])}: a session with trouble usually does hold a failed check, but many failing sessions look clean.",
          "- Sessions with no verifiable turn are left out; they cannot be scored.", ""]

    e = s["enrichment"]
    L += ["## 1d. Where a reviewer should look first: failure rate given the signal", "",
          table(["Platform", "P(failed) base rate", "P(failed | trouble)", "P(failed | no trouble)", "Lift"],
                [[nm(g), fmt(e[g]["base_rate"]), fmt(e[g]["given_trouble"]), fmt(e[g]["given_no_trouble"]), f"{e[g]['lift']:.2f}" if e[g]["lift"] else "–"] for g in G]), ""]
    ea = e["all"]
    L += [f"- A turn with trouble fails {fmt(ea['given_trouble'])} of the time, against a base rate of {fmt(ea['base_rate'])} (lift {ea['lift']:.2f}).",
          "- So review flagged turns first: each check there finds more failures.",
          f"- Do not report the flagged-turn failure rate as the platform's rate. Unflagged turns still fail {fmt(ea['given_no_trouble'])} of the time; "
          "a rate from flagged turns only is biased upwards and ranks platforms by how loudly they fail.", ""]

    r = m["rates"]; T = m["types"]
    L += ["## 2a. Pass rate in the full recordings matrix (every script on every platform)", "",
          table(["Task type", "Scripts"] + [base.NAME[p] for p in P],
                [["all", sum(m["scripts_per_type"].values())] + [fmt(r[p]["all"]) for p in P]] +
                [[tt, m["scripts_per_type"][tt]] + [fmt(r[p][tt]) for p in P] for tt in T]), ""]
    order = sorted(P, key=lambda p: -r[p]["all"]["rate"])
    ov = sum(r[p]["all"]["lo"] <= r[q]["all"]["hi"] and r[q]["all"]["lo"] <= r[p]["all"]["hi"] for p, q in itertools.combinations(P, 2))
    L += [f"- Overall the order is {', '.join(f'{base.NAME[p]} {fmt(r[p]['all'], False)}' for p in order)}. {ov} of 3 pairs of overall intervals overlap.",
          f"- Within a task type the cells hold {min(r[p][tt]['n'] for p in P for tt in T)} to {max(r[p][tt]['n'] for p in P for tt in T)} verifiable turns, so most intervals are wide.",
          "- Each cell comes from one recording per script; repeated runs of the same script could differ.", ""]

    L += ["## 2b. Fisher's exact test for every pair of platforms", "",
          table(["Group", "Pair", "Correct A", "Correct B", "Difference", "p (two-sided)", "Holm at 0.05"],
                [[t["group"], t["pair"], t["a"], t["b"], f"{100 * t['diff']:+.0f} pts", t["p"], ("kept" if t["holm"] else "no") if "holm" in t else "–"] for t in m["tests"]]), ""]
    L += [f"- Of {m['within_tests']} comparisons within a task type, {m['within_significant']} are significant at 0.05 and {m['within_significant_holm']} remain after Holm.",
          f"- Overall, {sum(t['p'] < 0.05 for t in m['tests'] if t['group'] == 'all')} of 3 platform pairs differ at 0.05.",
          "- A non-significant pair is not evidence that two platforms are equal; the cells are too small to tell.", ""]

    bs = m["bootstrap"]
    L += ["## 2c. Overall difference with the script as the unit (cluster bootstrap)", "",
          table(["Pair", "Difference", "95% CI, turns resampled", "95% CI, scripts resampled", "Width ratio"],
                [[k, f"{100 * v['diff']:+.0f} pts", ci(*v["turn_ci"]), ci(*v["script_ci"]), v["width_ratio"]] for k, v in bs.items()]), ""]
    wr = [v["width_ratio"] for v in bs.values()]
    L += [f"- Resampling whole scripts changes the interval width by a factor of {min(wr)} to {max(wr)} ({BOOT} resamples each).",
          "- The script bootstrap is paired: the same scripts are drawn for both platforms, which removes script difficulty from the difference. "
          "Clustering widens the interval; pairing narrows it. The ratio shows the net effect.",
          f"- {sum(1 for v in bs.values() if v['script_ci'][0] > 0 or v['script_ci'][1] < 0)} of 3 pairs keep an interval that excludes zero.", ""]

    pl = b["platform"]
    L += ["## 3a. Checks per platform needed to pick the best platform (simulation)", "",
          "Monte Carlo, " + f"{DRAWS} draws per n. The overall pass rates in 2a are taken as the true rates.", "",
          table(["Checked turns per platform", "P(best is right)", "P(whole order right)", "Mean regret (pts)"],
                [[n, f"{100 * pl[str(n)]['best']:.1f}%", f"{100 * pl[str(n)]['order']:.1f}%", f"{100 * pl[str(n)]['regret']:.1f}"] for n in NS]), ""]
    f90 = next((n for n in NS if pl[str(n)]["best"] >= 0.9), None)
    o90 = next((n for n in NS if pl[str(n)]["order"] >= 0.9), None)
    L += [f"- With true gaps this large, {f90} checked turns per platform pick the best platform at least 90% of the time.",
          f"- The full order needs more: {o90 if o90 else 'more than ' + str(NS[-1])} per platform for 90%.",
          "- Real gaps may be smaller than in this simulated company; smaller gaps need many more checks.", ""]

    bt = b["by_type"]; mo = b["mean_over_types"]
    L += ["## 3b. Checks per platform and task type (simulation)", "",
          table(["Task type"] + [f"n={n}" for n in NS] + ["First n at 90%"],
                [[tt] + [f"{100 * bt[tt][str(n)]['best']:.0f}%" for n in NS] + [b["first_n_reaching_90"][tt] or f">{NS[-1]}"] for tt in T] +
                [["mean over types"] + [f"{100 * mo[str(n)]['best']:.0f}%" for n in NS] + [b["first_n_reaching_90"]["mean"] or f">{NS[-1]}"]]), ""]
    hard = [tt for tt in T if not b["first_n_reaching_90"][tt]]
    slow = max(T, key=lambda tt: b["first_n_reaching_90"][tt] or 10 ** 9)
    top2 = sorted(P, key=lambda p: -r[p][slow]["rate"])[:2]
    L += ["- Cells show P(the best platform for that type is right). Regret and full order are in sampling.json.",
          f"- The mean over types reaches 90% at n={b['first_n_reaching_90']['mean'] or '>' + str(NS[-1])} per cell.",
          f"- The hardest type is {slow} (n={b['first_n_reaching_90'][slow] or '>' + str(NS[-1])}): its two best platforms are close ({fmt(r[top2[0]][slow], False)} against {fmt(r[top2[1]][slow], False)}).",
          (f"- {', '.join(hard)} never reach 90% here: two platforms have equal or nearly equal true rates, so the pick is close to a coin toss and costs little."
           if hard else "- Every type reaches 90% within the list."),
          "- True cell rates come from 2 to 7 scripts each, so the simulated gaps are themselves uncertain.", ""]

    pn = b["plan"]
    L += ["## 3c. The budget against what two weeks produced", "",
          table(["n", "Checks, platform level", "Checks, per task type", "Verifiable lake turns", "Fraction (platform)", "Fraction (task type)", "Cells short of n"],
                [[q["n"], q["platform_checks"], q["type_checks"], q["lake_verifiable"], f"{100 * q['platform_fraction']:.0f}%", f"{100 * q['type_fraction']:.0f}%",
                  f"{q['cells_short']} of {len(P) * len(T)}"] for q in pn]), ""]
    lc = b["lake_cells"]
    L += [f"- The window produced {pn[0]['lake_verifiable']} verifiable turns in {len(P) * len(T)} platform-by-type cells ({min(lc.values())} to {max(lc.values())} per cell).",
          f"- At n={NS[1]} per cell, {pn[1]['cells_short']} cells did not even produce {NS[1]} verifiable turns. A fraction above 100% means the window cannot supply the sample.",
          "- The platform-level choice is affordable; a per-task-type choice needs a longer window or a planned test set.",
          "- Lake cells follow the people's habits: a platform few people use for a type fills its cell slowly however long the window.", ""]
    L += ["Verifiable lake turns per cell:", "",
          table(["Task type"] + [base.NAME[p] for p in P], [[tt] + [lc[f"{p}/{tt}"] for p in P] for tt in T]), ""]

    L += ["## 4. Trace proxies at session level against checks and fate", "",
          table(["Proxy", "Flagged sessions", "Precision vs failed check", "Recall vs failed check", "Precision vs not completed", "Recall vs not completed",
                 "Precision vs switched", "Recall vs switched"],
                [[k, f"{v['flagged']}/{v['sessions']}", fmt(v["vs_failed_check"]["precision"]), fmt(v["vs_failed_check"]["recall"]),
                  fmt(v["vs_not_completed"]["precision"]), fmt(v["vs_not_completed"]["recall"]), fmt(v["vs_switched"]["precision"]),
                  fmt(v["vs_switched"]["recall"])] for k, v in x.items()]), ""]
    sw = x["switched_away"]["vs_switched"]
    bestr = max(x, key=lambda k: x[k]["vs_failed_check"]["recall"]["rate"] or 0)
    L += [f"- `switched_away` matches the designed switch fate: precision {fmt(sw['precision'])}, recall {fmt(sw['recall'])}. "
          "The replay makes users switch only after a noticed failure, so this link is built in.",
          f"- Against a failed check, the best recall is {fmt(x[bestr]['vs_failed_check']['recall'])}, by `{bestr}`. No proxy finds most failing sessions without false alarms.",
          f"- 'Failed check' uses the {x['ends_in_trouble']['vs_failed_check']['n']} sessions with a verifiable turn; fate uses all {x['ends_in_trouble']['sessions']}.",
          "- 'Not completed' is fate abandoned or switched; a completed session can still hold a failed check.", ""]
    return "\n".join(L)


def main():
    rng = random.Random(SEED)
    ses = base.sessions(); tasks = base.rebuild_tasks(ses)
    sc, rec, scripts = scoring(ses)
    res = {"silent": silent(ses, sc)}
    res["matrix"] = matrix(rec, scripts, rng)
    res["budget"] = budget(rec, scripts, res["matrix"], ses, sc, rng)
    res["proxies"] = proxies(ses, tasks, sc)
    res["no_tool_platforms"] = [p for p in P if not any(t["tools"] for x in ses.values() if x["platform"] == p for t in x["turns"])]
    res["definitions"] = {
        "verifiable_turn": "a lake turn whose truth turn_checks list is non-empty; correct when all checks are true",
        "silent_failure": "a verifiable turn that failed a check and has no trouble signal (no answer, tool error or inability phrase)",
        "session_failed": "a session with at least one failed check (only sessions with a verifiable turn are scored)",
        "switched_away": "the session is followed by another session in its rebuilt task (base.rebuild_tasks)",
        "best_hit": "every platform tied at the top of the sample is a true best; a tie with a worse platform is a miss",
        "order_hit": "every pair with different true rates is strictly ordered the same way in the sample",
        "regret": "true best rate minus the true rate of the platform picked, sample ties broken at random",
        "bootstrap": "percentile 2.5/97.5 of 5000 resamples; the script bootstrap draws scripts with replacement, the same draw for both platforms"}
    base.save("sampling.json", res)
    open(os.path.join(base.D, "sampling.md"), "w").write(markdown(res) + "\n")
    pt, mt, bd = res["silent"]["per_turn"]["all"], res["matrix"], res["budget"]
    print(f"verifiable lake turns {pt['verifiable']}, failed {pt['failed']}, silent {pt['silent']['k']} ({fmt(pt['silent'])})")
    print(f"within-type pairs significant {mt['within_significant']}/{mt['within_tests']}, after Holm {mt['within_significant_holm']}")
    print("first n at 90% per type:", bd["first_n_reaching_90"])
    print("wrote data/sampling.json, data/sampling.md")


if __name__ == "__main__":
    main()
