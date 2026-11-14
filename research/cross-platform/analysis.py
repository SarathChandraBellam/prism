"""Cross-platform analyses on the lake. Reads lake.jsonl, directory.json and seats.json; reads truth.json only to score.

    python3 analysis.py          # writes data/results.json

1 switch detection · 2 outcome proxies against ground truth · 3 seats · 4 routing counterfactual
"""
import collections, datetime as dt, itertools, json, re, statistics
from common import *
import prism

WINDOW_S = 30 * 60
STOP = set("a an the of to for and or is are was were be do does can could we you i it me my our this that on in at with please what how which who".split())
TOK = lambda s: {w for w in re.findall(r"[a-z0-9\-]+", s.lower()) if w not in STOP}
ENT = re.compile(r"\b[59]\d{3}\b|\b[A-Z]{3}-[A-Z]{3,5}\b")
REFUSAL = ("don't have access", "do not have access", "can't access", "cannot access", "no access", "unable to", "i can't", "i cannot",
           "i'm not able", "i am not able", "don't have real-time", "do not have real-time", "don't have the ability", "not able to look")
T = lambda s: dt.datetime.fromisoformat(s)
PIDX = {p: i for i, p in enumerate(PLATFORMS)}
pct = lambda a, b: f"{100 * a / b:.0f}%" if b else "–"


# ---------------------------------------------------------------- lake

def load_lake():
    spans = jl(os.path.join(D, "lake.jsonl"))
    kids = collections.defaultdict(list)
    for s in spans:
        if s["parent_span_id"]: kids[s["trace_id"]].append(s)
    ses = {}
    for s in spans:
        if s["parent_span_id"] is not None: continue
        a = A(s)
        x = ses.setdefault(a["gen_ai.conversation.id"], {"id": a["gen_ai.conversation.id"], "platform": a["platform"], "user": a["user.id"], "turns": []})
        x["turns"].append({"idx": a["session.turn_index"], "root": s, "kids": sorted(kids[s["trace_id"]], key=lambda k: k["start_time"]),
                           "input": a["gen_ai.input.text"], "output": a["gen_ai.output.text"] or ""})
    for x in ses.values():
        x["turns"].sort(key=lambda t: t["idx"])
        x["start"], x["end"] = T(x["turns"][0]["root"]["start_time"]), T(x["turns"][-1]["root"]["end_time"])
        x["first"] = x["turns"][0]["input"]
        x["text"] = " ".join(t["input"] for t in x["turns"])
        x["entities"] = set(ENT.findall(x["text"]))
    return ses


def prf(tp, fp, fn):
    p = tp / (tp + fp) if tp + fp else 0.0
    r = tp / (tp + fn) if tp + fn else 0.0
    return {"tp": tp, "fp": fp, "fn": fn, "precision": round(p, 3), "recall": round(r, 3), "f1": round(2 * p * r / (p + r), 3) if p + r else 0.0}


def jac(a, b): return len(a & b) / len(a | b) if a | b else 0.0


# ---------------------------------------------------------------- labels by text match

def attach_labels(ses, truth):
    """The labels belong to recordings. A lake session gets the label of the recording of the script whose user texts it
    most resembles, on its own platform. Accuracy of the match is scored against truth."""
    labs = json.load(open(os.path.join(D, "labels.json"))) if os.path.exists(os.path.join(D, "labels.json")) else {}
    scs = {k: v for k, v in scenarios().items() if k in truth["scope"]["scripts"]}
    want = {s["lake_session_id"]: t["script"] for t in truth["tasks"] for s in t["sessions"]}
    complete = all(f"{p}:{sid}" in labs for p in PLATFORMS for sid in scs)
    hit = tot = 0
    for x in ses.values():
        ts = [TOK(t["input"]) for t in x["turns"]]
        best = max(sorted(scs), key=lambda sid: statistics.mean(jac(a, TOK(b["text"])) for a, b in zip(ts, scs[sid]["turns"])))
        x["script_guess"] = best
        x["label"] = labs.get(f"{x['platform']}:{best}") if complete else None
        hit += best == want[x["id"]]; tot += 1
    return hit, tot, sum(1 for x in ses.values() if x["label"])


# ---------------------------------------------------------------- 1. switch detection

def candidates(ses):
    by = collections.defaultdict(list)
    for x in ses.values(): by[x["user"]].append(x)
    out = []
    for u, xs in by.items():
        xs.sort(key=lambda x: x["start"])
        for a, b in itertools.permutations(xs, 2):
            gap = (b["start"] - a["end"]).total_seconds()
            if a["platform"] != b["platform"] and 0 <= gap <= WINDOW_S: out.append((a, b, gap))
    return out


def detect(ses, truth):
    chain = {}
    for t in truth["tasks"]:
        for i, s in enumerate(t["sessions"]): chain[s["lake_session_id"]] = (t["task_id"], i)
    pos = {(a["lake_session_id"], b["lake_session_id"]) for t in truth["tasks"] for a, b in itertools.combinations(t["sessions"], 2) if a["platform"] != b["platform"]}
    adjacent = {(t["sessions"][i]["lake_session_id"], t["sessions"][i + 1]["lake_session_id"]) for t in truth["tasks"] for i in range(len(t["sessions"]) - 1)}
    cands = candidates(ses)
    feats = []
    for a, b, gap in cands:
        la, lb = a["label"], b["label"]
        feats.append({"a": a["id"], "b": b["id"], "gap": gap, "jac": jac(TOK(a["first"]), TOK(b["first"])), "jac_all": jac(TOK(a["text"]), TOK(b["text"])),
                      "ent": len(a["entities"] & b["entities"]), "label": bool(la and lb and la["domain"] == lb["domain"] and la["task_type"] == lb["task_type"]),
                      "has_labels": bool(la and lb), "truth": (a["id"], b["id"]) in pos, "adjacent": (a["id"], b["id"]) in adjacent})
    n_pos = len(pos)

    def score(pred):
        sel = [f for f in feats if pred(f)]
        tp = sum(f["truth"] for f in sel)
        return prf(tp, len(sel) - tp, n_pos - tp), sel
    res = {"n_candidates": len(feats), "n_true_pairs": n_pos, "n_adjacent_pairs": len(adjacent), "window_minutes": 30, "methods": {}}
    res["methods"]["a_window"] = score(lambda f: True)[0]
    sweep = {}
    for tau in [x / 20 for x in range(0, 13)]:
        sweep[tau] = score(lambda f, tau=tau: f["jac"] >= tau)[0]
    res["jaccard_sweep"] = {f"{k:.2f}": v for k, v in sweep.items()}
    bt = max(sweep, key=lambda k: (sweep[k]["f1"], k))
    res["methods"]["b_jaccard"] = {**sweep[bt], "threshold": bt}
    res["methods"]["b2_jaccard_whole_session"] = {**max((score(lambda f, t=t: f["jac_all"] >= t)[0] | {"threshold": t} for t in [x / 20 for x in range(1, 13)]), key=lambda r: (r["f1"], r["threshold"]))}
    res["methods"]["c_entities"] = score(lambda f: f["ent"] >= 1)[0]
    res["methods"]["c_entities_or_jaccard"] = score(lambda f: f["ent"] >= 1 or f["jac"] >= bt)[0]
    have = any(f["has_labels"] for f in feats)
    if have: res["methods"]["d_labels"] = score(lambda f: f["label"])[0]
    # e: best combination of signals (k of n), with an option to keep only the nearest predecessor per successor
    best = None
    for tau in [.1, .15, .2, .3]:
        for sig in ([("jac", "ent", "label"), ("jac", "ent")] if have else [("jac", "ent")]):
            for k in range(1, len(sig) + 1):
                for nearest in (False, True):
                    def pred(f, tau=tau, sig=sig, k=k):
                        v = {"jac": f["jac"] >= tau, "ent": f["ent"] >= 1, "label": f["label"]}
                        return sum(v[s] for s in sig) >= k
                    sel = [f for f in feats if pred(f)]
                    if nearest:
                        keep = {}
                        for f in sel:
                            if f["b"] not in keep or f["gap"] < keep[f["b"]]["gap"]: keep[f["b"]] = f
                        sel = list(keep.values())
                    tp = sum(f["truth"] for f in sel)
                    r = prf(tp, len(sel) - tp, n_pos - tp) | {"tau": tau, "signals": list(sig), "k": k, "nearest_only": nearest}
                    if best is None or (r["f1"], -len(sig), -k) > (best["f1"], -len(best["signals"]), -best["k"]): best = r
                    if best is r: best_sel = sel
    res["methods"]["e_best_combination"] = best
    # paraphrase effect: every switch session carries a paraphrased first prompt (by construction)
    adj = [f for f in feats if f["adjacent"]]
    res["paraphrase"] = {"switch_sessions": sum(1 for t in truth["tasks"] for s in t["sessions"] if s["is_switch"]),
                         "of_which_paraphrased": sum(1 for t in truth["tasks"] for s in t["sessions"] if s["is_switch"] and s["paraphrased"]),
                         "median_jaccard_first_prompt_true_pairs": round(statistics.median([f["jac"] for f in feats if f["truth"]]), 3),
                         "median_jaccard_first_prompt_false_pairs": round(statistics.median([f["jac"] for f in feats if not f["truth"]]), 3) if any(not f["truth"] for f in feats) else None,
                         "true_pairs_with_entity": sum(f["ent"] >= 1 for f in feats if f["truth"]), "true_pairs_in_candidates": sum(f["truth"] for f in feats),
                         "adjacent_pairs_with_jaccard_ge_best": sum(f["jac"] >= bt for f in adj), "adjacent_pairs_in_candidates": len(adj)}
    # sensitivity: what if the user had pasted the original prompt again (counterfactual, uses the script text, not the lake)
    scs = scenarios(); orig = {s["lake_session_id"]: scs[t["script"]]["turns"][0]["text"] for t in truth["tasks"] for s in t["sessions"]}
    alt = [(f, jac(TOK(orig[f["a"]]), TOK(orig[f["b"]]))) for f in feats]
    tp = sum(f["truth"] for f, j in alt if j >= bt); sel = sum(j >= bt for f, j in alt)
    res["counterfactual_unparaphrased"] = prf(tp, sel - tp, n_pos - tp) | {"threshold": bt}
    # which signals the missed true pairs lack
    miss = [f for f in feats if f["truth"] and f not in best_sel]
    res["best_misses"] = {"n": len(miss) + (n_pos - sum(f["truth"] for f in feats)), "outside_window": n_pos - sum(f["truth"] for f in feats)}
    # detected successors for the proxies
    detected = {(f["a"], f["b"]) for f in best_sel}
    return res, detected, feats


# ---------------------------------------------------------------- 2. proxies against truth

def session_signals(x, detected_from):
    nt = len(x["turns"])
    no_ans = sum(not t["output"].strip() for t in x["turns"])
    tool_err = sum(any(A(k)["gen_ai.operation.name"] == "execute_tool" and k["status"] == "error" for k in t["kids"]) for t in x["turns"])
    chats = [k for t in x["turns"] for k in t["kids"] if A(k)["gen_ai.operation.name"] == "chat"]
    last = x["turns"][-1]
    trouble = (not last["output"].strip()) or any(A(k)["gen_ai.operation.name"] == "execute_tool" and k["status"] == "error" for k in last["kids"]) \
        or any(r in last["output"].lower() for r in REFUSAL)
    switched = x["id"] in detected_from
    return {"turns": nt, "no_answer": no_ans, "tool_error_turns": tool_err, "requests": len(chats), "failed_requests": sum(k["status"] == "error" for k in chats),
            "switched_away": switched, "abandoned": bool(trouble and not switched)}


def spearman(x, y):
    return prism.spearman(x, y) if len(x) > 2 else float("nan")


def proxies(ses, truth, detected):
    from_ = {a for a, b in detected}
    sess_truth = {s["lake_session_id"]: s for t in truth["tasks"] for s in t["sessions"]}
    tdes = {s["lake_session_id"]: t["designed"] for t in truth["tasks"] for s in t["sessions"]}
    sig = {i: session_signals(x, from_) for i, x in ses.items()}

    def cell(ids):
        n = len(ids); S = [sig[i] for i in ids]
        turns = sum(s["turns"] for s in S); req = sum(s["requests"] for s in S)
        ver = pas = 0
        for i in ids:
            for ch in sess_truth[i]["turn_checks"]:
                if ch: ver += 1; pas += all(ch)
        comp = {"no_answer": sum(s["no_answer"] for s in S) / turns, "switch_away": sum(s["switched_away"] for s in S) / n,
                "abandonment": sum(s["abandoned"] for s in S) / n, "tool_error": sum(s["tool_error_turns"] for s in S) / turns,
                "failed_request": (sum(s["failed_requests"] for s in S) / req) if req else 0.0}
        return {"sessions": n, "turns": turns, "verifiable_turns": ver, "truth_pass": round(pas / ver, 3) if ver else None,
                **{k: round(v, 3) for k, v in comp.items()}, "composite": round(statistics.mean(comp.values()), 3)}

    tp = sum(sig[i]["abandoned"] and sess_truth[i]["fate"] == "abandoned" for i in ses)
    fp = sum(sig[i]["abandoned"] and sess_truth[i]["fate"] != "abandoned" for i in ses)
    fn = sum(not sig[i]["abandoned"] and sess_truth[i]["fate"] == "abandoned" for i in ses)
    sw_tp = sum(sig[i]["switched_away"] and sess_truth[i]["fate"] == "switched" for i in ses)
    out = {"abandonment_flag_vs_truth": prf(tp, fp, fn), "switch_away_flag_vs_truth": prf(sw_tp, sum(sig[i]["switched_away"] for i in ses) - sw_tp, sum(sess_truth[i]["fate"] == "switched" for i in ses) - sw_tp),
           "definitions": {
        "no_answer": "share of turns whose reply is empty", "switch_away": "share of sessions followed by a detected session of the same user on another platform",
        "abandonment": "share of sessions that end on a turn with trouble (no answer, a tool error or an inability phrase in the reply) and have no detected follow-up",
        "tool_error": "share of turns with at least one failed tool call", "failed_request": "share of model requests that failed (not visible on Chatly)",
        "composite": "unweighted mean of the five; lower is better"}}
    by_p = {p: [i for i, x in ses.items() if x["platform"] == p] for p in PLATFORMS}
    out["by_platform"] = {p: cell(ids) for p, ids in by_p.items()}
    cuts = {"labelled_domain": lambda i: (ses[i]["label"] or {}).get("domain"), "designed_task_type": lambda i: tdes[i]["task_type"]}
    for cname, key in cuts.items():
        cells = {}
        for p in PLATFORMS:
            g = collections.defaultdict(list)
            for i in by_p[p]:
                if key(i): g[key(i)].append(i)
            for k, ids in g.items():
                if len(ids) >= 3 and sum(1 for i in ids for ch in sess_truth[i]["turn_checks"] if ch) >= 3: cells[(k, p)] = cell(ids)
        if not cells: out[cname] = None; continue
        rows = [{"group": k, "platform": p, **c} for (k, p), c in sorted(cells.items())]
        xs = [-c["composite"] for c in cells.values()]; ys = [c["truth_pass"] for c in cells.values()]
        groups = collections.defaultdict(dict)
        for (k, p), c in cells.items(): groups[k][p] = c
        conf, match, ties, pairs, conc = [], 0, 0, 0, 0
        for k, d in sorted(groups.items()):
            if len(d) < 2: continue
            bt = max(d, key=lambda p: (d[p]["truth_pass"], -PIDX[p])); bp = min(d, key=lambda p: (d[p]["composite"], PIDX[p]))
            tie = sorted(d[p]["composite"] for p in d)[0] == sorted(d[p]["composite"] for p in d)[1]
            conf.append({"group": k, "platforms": len(d), "best_by_truth": bt, "best_by_proxy": bp, "match": bt == bp, "proxy_tie": tie})
            match += bt == bp; ties += tie
            for p, q in itertools.combinations(d, 2):
                if d[p]["truth_pass"] != d[q]["truth_pass"] and d[p]["composite"] != d[q]["composite"]:
                    pairs += 1; conc += (d[p]["truth_pass"] > d[q]["truth_pass"]) == (d[p]["composite"] < d[q]["composite"])
        singles = {name: spearman([-c[name] for c in cells.values()], ys) for name in ("no_answer", "switch_away", "abandonment", "tool_error", "failed_request")}
        out[cname] = {"cells": rows, "n_cells": len(rows), "spearman_composite_vs_truth": round(spearman(xs, ys), 3),
                      "spearman_single_proxies": {k: round(v, 3) for k, v in singles.items()}, "groups": conf, "groups_matching": match, "groups_compared": len(conf),
                      "groups_with_proxy_tie": ties, "pairs_compared": pairs, "pairs_concordant": conc}
    return out, sig


# ---------------------------------------------------------------- 3. seats

def seats(ses, detected, truth):
    seat_list = json.load(open(os.path.join(D, "seats.json")))
    succ = {b for a, b in detected}
    per = collections.defaultdict(lambda: collections.Counter()); last = {}
    starts = collections.defaultdict(lambda: collections.Counter())
    for i, x in ses.items():
        per[x["user"]][x["platform"]] += 1
        starts[x["user"]][x["platform"]] += i not in succ
        last[(x["user"], x["platform"])] = max(last.get((x["user"], x["platform"]), x["start"]), x["start"])
    design = {(s["handle"], s["platform"]): s["designed_idle"] for s in truth["seats"]}
    rows = []
    for s in seat_list:
        u, p = s["handle"], s["platform"]; n, tot = per[u][p], sum(per[u].values())
        st, stot = starts[u][p], sum(starts[u].values())
        rows.append({"handle": u, "platform": p, "price": s["monthly_price"], "sessions": n, "share": round(n / tot, 3) if tot else 0, "task_starts": st,
                     "start_share": round(st / stot, 3) if stot else 0, "last_use": last[(u, p)].date().isoformat() if (u, p) in last else None,
                     "flag": (n / tot if tot else 0) < .10, "flag_starts": (st / stot if stot else 0) < .10, "designed_idle": design[(u, p)]})
    res = {"rows": rows}
    for name, key in (("by_sessions", "flag"), ("by_task_starts", "flag_starts")):
        tp = sum(r[key] and r["designed_idle"] for r in rows); fp = sum(r[key] and not r["designed_idle"] for r in rows); fn = sum(not r[key] and r["designed_idle"] for r in rows)
        res[name] = prf(tp, fp, fn) | {"flagged": sum(r[key] for r in rows), "monthly_saving": sum(r["price"] for r in rows if r[key]),
                                      "designed_idle": sum(r["designed_idle"] for r in rows), "designed_saving": sum(r["price"] for r in rows if r["designed_idle"])}
    res["total_seats"], res["monthly_spend"] = len(rows), sum(r["price"] for r in rows)
    res["single_seat_users"] = sum(1 for u in {r["handle"] for r in rows} if sum(r["handle"] == u for r in rows) == 1)
    return res


# ---------------------------------------------------------------- 4. routing

def routing(truth):
    rec = truth["recordings"]; types = sorted({r["designed"]["task_type"] for r in rec.values()})
    cell = {}
    for p in PLATFORMS:
        for tt in types:
            rs = [r for k, r in rec.items() if r["platform"] == p and r["designed"]["task_type"] == tt]
            ver, pas = sum(r["verifiable_turns"] for r in rs), sum(r["passed_turns"] for r in rs)
            turns = sum(len(r["turn_cost"]) for r in rs)
            cell[(p, tt)] = {"scripts": len(rs), "verifiable_turns": ver, "passed": pas, "pass_rate": round(pas / ver, 3) if ver else None,
                             "cost_per_1000_turns": round(1000 * sum(sum(r["turn_cost"]) for r in rs) / turns, 2), "cost": sum(sum(r["turn_cost"]) for r in rs), "turns": turns}
    best = {}
    for tt in types:
        c = {p: cell[(p, tt)] for p in PLATFORMS}
        if all(v["pass_rate"] is None for v in c.values()): best[tt] = min(PLATFORMS, key=lambda p: c[p]["cost"]); continue
        best[tt] = max(PLATFORMS, key=lambda p: (c[p]["pass_rate"] or 0, -c[p]["cost_per_1000_turns"]))
    # leave-one-script-out routing: pick the platform for a script from the other scripts of its task type
    def loo(script, tt):
        sc = {}
        for p in PLATFORMS:
            rs = [r for k, r in rec.items() if r["platform"] == p and r["designed"]["task_type"] == tt and r["script"] != script]
            v = sum(r["verifiable_turns"] for r in rs)
            sc[p] = ((sum(r["passed_turns"] for r in rs) / v) if v else 0, -sum(sum(r["turn_cost"]) for r in rs) / max(1, sum(len(r["turn_cost"]) for r in rs)))
        return max(PLATFORMS, key=lambda p: sc[p])
    rows = collections.defaultdict(lambda: collections.Counter())
    for t in truth["tasks"]:
        tt, sc_id = t["designed"]["task_type"], t["script"]
        ver = rec[f"atlas:{sc_id}"]["verifiable_turns"]
        first = t["sessions"][0]; final = t["sessions"][-1]
        def recs(p): return rec[f"{p}:{sc_id}"]
        actual_pass = sum(1 for s in [final] for ch in s["turn_checks"] if ch and all(ch))
        actual_cost = sum(s["cost"] for s in t["sessions"])
        for name, ps, cost in (("start_only", recs(first["platform"])["passed_turns"], sum(recs(first["platform"])["turn_cost"])),
                               ("actual", actual_pass, actual_cost),
                               ("routed", recs(best[tt])["passed_turns"], sum(recs(best[tt])["turn_cost"])),
                               ("routed_loo", recs(loo(sc_id, tt))["passed_turns"], sum(recs(loo(sc_id, tt))["turn_cost"]))):
            for key in ("all", t["role"]):
                rows[(name, key)].update({"passed": ps, "verifiable": ver, "cost": cost, "tasks": 1})
    pol = {}
    for (name, key), c in rows.items():
        pol.setdefault(name, {})[key] = {"tasks": c["tasks"], "verifiable_turns": c["verifiable"], "passed": c["passed"],
                                          "pass_rate": round(c["passed"] / c["verifiable"], 3), "shadow_cost": round(c["cost"], 4),
                                          "cost_per_task": round(c["cost"] / c["tasks"], 5)}
    return {"cells": [{"platform": p, "task_type": tt, **cell[(p, tt)]} for tt in types for p in PLATFORMS], "best": best, "policies": pol,
            "task_types": types, "task_counts": dict(collections.Counter(t["designed"]["task_type"] for t in truth["tasks"]))}


# ---------------------------------------------------------------- tasks outcome (for the cards)

def outcomes(truth):
    out = collections.defaultdict(lambda: collections.Counter())
    for t in truth["tasks"]:
        for key in ("all", t["role"]):
            o = out[key]; o["tasks"] += 1; o["switched"] += t["n_switches"] > 0; o["abandoned"] += t["final_fate"] == "abandoned"
            o["start_" + t["sessions"][0]["platform"]] += 1
            o["start_" + t["sessions"][0]["platform"] + "_switched"] += t["n_switches"] > 0
            o["start_" + t["sessions"][0]["platform"] + "_abandoned"] += t["final_fate"] == "abandoned"
            o["sessions"] += len(t["sessions"])
    return {k: dict(v) for k, v in out.items()}


def lake_outcomes(ses, detected, sig, feats):
    """Task chains rebuilt from the detected pairs (each session keeps its nearest detected predecessor). Lake and directory only."""
    role = {u["handle"]: u["role"] for u in json.load(open(os.path.join(D, "directory.json")))["users"]}
    gap = {(f["a"], f["b"]): f["gap"] for f in feats}
    pred = {}
    for a, b in detected:
        if b not in pred or gap[(a, b)] < gap[(pred[b], b)]: pred[b] = a
    nxt = {a: b for b, a in pred.items()}
    out = collections.defaultdict(collections.Counter)
    for i, x in ses.items():
        if i in pred: continue
        end = i; n = 1
        while end in nxt and n < 5: end = nxt[end]; n += 1
        for key in ("all", role[x["user"]]):
            c = out[key]; c["tasks"] += 1; c["switched"] += n > 1; c["abandoned"] += sig[end]["abandoned"]
            c["start_" + x["platform"]] += 1; c["start_" + x["platform"] + "_switched"] += n > 1; c["start_" + x["platform"] + "_abandoned"] += sig[end]["abandoned"]
    return {k: dict(v) for k, v in out.items()}


def main():
    truth = json.load(open(os.path.join(D, "truth.json")))
    ses = load_lake()
    hit, tot, nlab = attach_labels(ses, truth)
    det, detected, feats = detect(ses, truth)
    prox, sig = proxies(ses, truth, detected)
    res = {"lake": {"sessions": len(ses), "turns": sum(len(x["turns"]) for x in ses.values())},
           "label_lookup": {"script_match_correct": hit, "sessions": tot, "sessions_with_label": nlab},
           "switch_detection": det, "proxies": prox, "seats": seats(ses, detected, truth), "routing": routing(truth), "outcomes": outcomes(truth), "lake_outcomes": lake_outcomes(ses, detected, sig, feats),
           "detected_pairs": len(detected)}
    json.dump(res, open(os.path.join(D, "results.json"), "w"), indent=1, sort_keys=True)
    print(json.dumps({k: v for k, v in res.items() if k not in ("seats", "routing", "proxies")}, indent=1)[:6000])


if __name__ == "__main__":
    main()
