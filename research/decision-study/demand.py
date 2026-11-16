"""Demand analysis: what work people bring, where it fails, and what a platform switch reveals.

    python3 demand.py          # writes data/demand.json and data/demand.md

Reads the span lake through base.py (sessions, rebuilt tasks, roles) and the session labels in
../cross-platform/data/labels.json. Six parts:
  1. what a switch reveals: capabilities the destination used that the origin platform never showed (spans only)
  2. tasks that end on trouble with no follow-up, by platform and role, with a small keyword lexicon (spans only)
  3. demand the chat-only platform cannot serve, with Atlas and Beacon for comparison (spans only)
  4. work map: role x domain, task type x start platform, task type x where it fails (labels)
  5. are labels comparable across platforms (agreement and Cohen's kappa; uses script identity, which is truth)
  6. identifiers typed into each tool (order/ticket/SKU ids, emails, customer names). Counts identifiers, not sensitivity.

LABELS. Labels exist per recording (platform x script), not per lake session. To label a lake session this script matches
it to the script whose texts its user turns resemble most (mean Jaccard against base.scripts() turn texts, as round 4's
attach_labels does) and takes the label of that platform:script. That matching step uses the SCRIPT TEXTS, which a real
company would not have. It stands in for labelling every session directly. It is scored against truth. Labels may be
incomplete while the background job runs: the script uses what is there, reports coverage, and a session without a label is
left out of the label tables (never guessed).

GROUND TRUTH (base.truth(), base.truth_tasks(), base.scripts(), recordings) is used only in functions named score_* and in
part 5 (which needs the script identity). No estimate is computed from it. Standard library only. No model. Deterministic.
"""
import collections, itertools, json, os, re
import base

LABELS = os.path.join(base.XP, "labels.json")
SMALL = 5

# What the person asked for, by keywords in the user text. First match wins, so the order matters.
# Built from the user prompts in the data (refund checks, ticket replies, stock checks, sales figures, shipping questions).
LEXICON = [("ticket / customer reply", r"ticket|triage|reply|customer|respond|inbox"),
           ("order / refund", r"refund|return|order|\b5\d{3}\b"),
           ("stock / reorder", r"stock|inventory|reorder|\b[A-Z]{3}-[A-Z]{3,5}\b"),
           ("sales / report", r"sales|revenue|report|figures|net |best sell|top \d|spend"),
           ("price / margin", r"price|margin|pricing|discount"),
           ("shipping / policy", r"ship|deliver|policy|automate"),
           ("file / document", r"file|document|save|note|memo|write|rewrite|description|draft")]
DATA_NEED = {"ticket / customer reply", "order / refund", "stock / reorder", "sales / report", "price / margin"}


def topic(*texts):
    t = " ".join(texts)
    for name, rx in LEXICON:
        if re.search(rx, t, re.I): return name
    return "other"


# ---------------------------------------------------------------- small helpers

def r(k, n):
    """k of n with a percentage; 'small n' when n < 5."""
    return f"{k}/{n} ({base.pct(k, n)})" + (" small n" if 0 < n < SMALL else "") if n else "0/0 small n"


def share(k, n): return round(k / n, 4) if n else None


def table(head, rows):
    return "\n".join(["| " + " | ".join(head) + " |", "|" + "---|" * len(head)] + ["| " + " | ".join(str(c) for c in row) + " |" for row in rows]) + "\n"


def kappa(pairs):
    n = len(pairs)
    if not n: return None
    po = sum(a == b for a, b in pairs) / n
    ca, cb = collections.Counter(a for a, _ in pairs), collections.Counter(b for _, b in pairs)
    pe = sum(ca[k] * cb[k] for k in ca) / (n * n)
    return None if pe == 1 else round((po - pe) / (1 - pe), 3)


def signal(t):
    return "no answer" if t["no_answer"] else "tool error" if t["tool_error"] else "inability" if t["inability"] else "nothing visible"


# ---------------------------------------------------------------- labels

def load_labels():
    return json.load(open(LABELS)) if os.path.exists(LABELS) else {}


def attach_labels(ses, labs):
    """Match each session to a script by text, then take that platform:script label (None when not labelled yet)."""
    scs = base.scripts()
    for x in ses.values():
        ts = [base.TOK(t["input"]) for t in x["turns"]]
        score = lambda sid: sum(base.jac(a, base.TOK(b["text"])) for a, b in zip(ts, scs[sid]["turns"])) / len(ts)
        x["script_guess"] = max(sorted(scs), key=score)
        x["label"] = labs.get(f"{x['platform']}:{x['script_guess']}")


def score_match(ses):
    """SCORING. Share of sessions matched to the script they were really played from, per platform."""
    want = {s["lake_session_id"]: t["script"] for t in base.truth()["tasks"] for s in t["sessions"]}
    out = {}
    for p in base.PLATFORMS:
        xs = [x for x in ses.values() if x["platform"] == p]
        out[p] = (sum(x["script_guess"] == want[x["id"]] for x in xs), len(xs))
    return out


def score_labels(ses, labs):
    """SCORING. Label accuracy against the designed domain and task type, for recordings and for lake sessions."""
    tr = base.truth(); rec = tr["recordings"]
    want = {s["lake_session_id"]: t["script"] for t in tr["tasks"] for s in t["sessions"]}
    out = {}
    for p in base.PLATFORMS:
        row = {}
        for field in ("domain", "task_type"):
            rk = [(labs[k][field], d["designed"][field]) for k, d in rec.items() if d["platform"] == p and k in labs]
            sk = [(x["label"][field], rec[f"{p}:{want[x['id']]}"]["designed"][field]) for x in ses.values() if x["platform"] == p and x["label"]]
            row[field] = {"recordings": [sum(a == b for a, b in rk), len(rk)], "sessions": [sum(a == b for a, b in sk), len(sk)]}
        out[p] = row
    return out


def score_agreement(labs):
    """SCORING (uses script identity, which is truth). Pairwise agreement, kappa and accuracy against designed labels."""
    rec = base.truth()["recordings"]
    scripts = sorted({k.split(":")[1] for k in rec})
    out = {}
    for field in ("domain", "task_type"):
        res = {"pairs": {}, "accuracy": {}}
        for a, b in itertools.combinations(base.PLATFORMS, 2):
            pr = [(labs[f"{a}:{s}"][field], labs[f"{b}:{s}"][field]) for s in scripts if f"{a}:{s}" in labs and f"{b}:{s}" in labs]
            res["pairs"][f"{a}-{b}"] = {"n": len(pr), "agree": sum(x == y for x, y in pr), "kappa": kappa(pr)}
        full = [s for s in scripts if all(f"{p}:{s}" in labs for p in base.PLATFORMS)]
        res["all_three"] = {"n": len(full), "agree": sum(len({labs[f"{p}:{s}"][field] for p in base.PLATFORMS}) == 1 for s in full)}
        for p in base.PLATFORMS:
            ok = [(labs[f"{p}:{s}"][field], rec[f"{p}:{s}"]["designed"][field]) for s in scripts if f"{p}:{s}" in labs]
            res["accuracy"][p] = {"n": len(ok), "correct": sum(x == y for x, y in ok)}
        out[field] = res
    return out


# ---------------------------------------------------------------- 1. what a switch reveals

def capabilities(x):
    """Capabilities seen in the execute_tool spans of one session: tools, skills, MCP servers (from the spans)."""
    caps = set()
    for t in x["turns"]:
        for k in t["tools"]:
            a = base.A(k); name = a["gen_ai.tool.name"]
            if a.get("gen_ai.skill.name"): caps.add(("skill", a["gen_ai.skill.name"]))
            elif name != "load_skill": caps.add(("tool", name))
            if base.server_of(name): caps.add(("MCP server", base.server_of(name)))
    return caps


def switches(ses, tasks):
    """Each consecutive pair of sessions inside a rebuilt task, with what the destination used that the origin platform never showed."""
    known = collections.defaultdict(set)
    for x in ses.values(): known[x["platform"]] |= capabilities(x)
    skills = {n for p in known for k, n in known[p] if k == "skill"}
    out = []
    for t in tasks:
        for a, b in zip(t["sessions"], t["sessions"][1:]):
            a, b = ses[a], ses[b]
            used = {("skill", n) if k == "tool" and n in skills else (k, n) for k, n in capabilities(b)}   # a skill name called as a tool is still a skill
            missing = sorted(used - known[a["platform"]])
            out.append({"origin": a, "dest": b, "missing": missing, "residual": signal(a["turns"][-1]) if not missing else None})
    return out


def agg_switches(sw):
    miss = collections.Counter(c for s in sw for c in s["missing"])
    kinds = collections.Counter(k for s in sw for k in {k for k, _ in s["missing"]})
    return {"switches": len(sw), "with_missing": sum(bool(s["missing"]) for s in sw), "missing_by_kind": dict(sorted(kinds.items())),
            "missing": {f"{k}: {n}": v for (k, n), v in sorted(miss.items(), key=lambda kv: (-kv[1], kv[0]))},
            "residual": dict(sorted(collections.Counter(s["residual"] for s in sw if not s["missing"]).items()))}


def score_switches(sw):
    """SCORING. Of the rebuilt switches, how many leave an origin session whose true fate is 'switched', and how many are adjacent in a true chain."""
    tr = base.truth(); fate = {s["lake_session_id"]: s["fate"] for t in tr["tasks"] for s in t["sessions"]}
    adj = {(t["sessions"][i]["lake_session_id"], t["sessions"][i + 1]["lake_session_id"]) for t in tr["tasks"] for i in range(len(t["sessions"]) - 1)}
    found = [(s["origin"]["id"], s["dest"]["id"]) for s in sw]
    true_sw = sum(f == "switched" for f in fate.values())
    return {"rebuilt": len(sw), "origin_fate_switched": sum(fate[a] == "switched" for a, _ in found), "adjacent_in_true_chain": sum(p in adj for p in found),
            "true_switches_in_truth": true_sw, "true_adjacent_pairs": len(adj)}


# ---------------------------------------------------------------- 2. tasks ending on trouble

def score_abandoned(tasks, ses):
    """SCORING. Estimate 'abandoned' = last session ends in trouble; truth = fate 'abandoned' of that last session."""
    fate = {s["lake_session_id"]: s["fate"] for t in base.truth()["tasks"] for s in t["sessions"]}
    tp = fp = fn = 0
    for t in tasks:
        est, tru = ses[t["sessions"][-1]]["ends_in_trouble"], fate[t["sessions"][-1]] == "abandoned"
        tp += est and tru; fp += est and not tru; fn += tru and not est
    return {"estimated": tp + fp, "true_abandoned": tp + fn, "hit": tp, "precision": share(tp, tp + fp), "recall": share(tp, tp + fn)}


# ---------------------------------------------------------------- 6. identifiers

def customer_names(ses):
    """Full customer names that appear in tool results (JSON 'customer_name' / 'name' keys next to customer data)."""
    names = set()
    for x in ses.values():
        for t in x["turns"]:
            for k in t["tools"]:
                names |= set(re.findall(r'"customer_name": "([A-Z][a-z]+ [A-Z][a-z]+)"', base.A(k).get("gen_ai.tool.call.result") or ""))
    return sorted(names)


# ---------------------------------------------------------------- main

def main():
    ses = base.sessions(); tasks = base.rebuild_tasks(ses); role = base.roles(); labs = load_labels()
    attach_labels(ses, labs)
    assert sum(len(t["sessions"]) for t in tasks) == len(ses) and len({s for t in tasks for s in t["sessions"]}) == len(ses)
    P = base.PLATFORMS; N = base.NAME
    res, md = {}, ["# Demand: what work people bring and where it fails\n",
                   "Built from spans only (Atlas, Beacon, Chatly), with the session labels where stated. Ground truth is used only to score. "
                   "Platforms are simulated: all numbers describe this lake, not a real company.\n"]
    last = lambda t: ses[t["sessions"][-1]]
    first = lambda t: ses[t["sessions"][0]]

    # ---- 1
    sw = switches(ses, tasks); sc = score_switches(sw)
    res["switches"] = {"all": agg_switches(sw), "score": sc, "by_pair": {}, "by_origin": {}}
    rows, rows_o = [], []
    for o, d in itertools.permutations(P, 2):
        s = [x for x in sw if x["origin"]["platform"] == o and x["dest"]["platform"] == d]
        if s: res["switches"]["by_pair"][f"{o}->{d}"] = agg_switches(s)
    for o in P:
        s = [x for x in sw if x["origin"]["platform"] == o]
        a = agg_switches(s); res["switches"]["by_origin"][o] = a
        for cap, v in a["missing"].items(): rows.append([N[o], cap, r(v, a["switches"])])
        for sig, v in a["residual"].items(): rows_o.append([N[o], sig, r(v, a["switches"])])
    pair_rows = []
    for k, a in res["switches"]["by_pair"].items():
        o, d = k.split("->")
        pair_rows.append([f"{N[o]} -> {N[d]}", a["switches"], r(a["with_missing"], a["switches"]), r(a["switches"] - a["with_missing"], a["switches"]),
                          ", ".join(f"{c} ({v})" for c, v in a["missing"].items()) or "none"])
    md += ["## Switches by origin and destination\n",
           "A switch is a consecutive pair of sessions in a rebuilt task (same person, another platform, within 30 minutes, similar first prompt). "
           "A capability is missing when the destination session used it (tool, skill or MCP server in an `execute_tool` span) and no session on the origin platform in the whole lake ever did.\n",
           table(["Pair", "Switches", "Something missing", "Nothing missing", "Missing capability (switches)"], pair_rows)]
    top = max(rows, key=lambda r_: int(r_[2].split("/")[0])) if rows else None
    md += [f"- {sw and sum(bool(s['missing']) for s in sw)} of {len(sw)} rebuilt switches ended on a platform that used something the origin platform never showed."
           + (f" The most common gap is {top[1]} from {top[0]} ({top[2]})." if top else ""),
           "- A gap is evidence, not proof. The destination may have used the capability only because it was there. Capabilities the origin has but never used in this two-week sample count as missing.",
           f"- Score against truth: {r(sc['origin_fate_switched'], sc['rebuilt'])} of the rebuilt switches leave a session whose true fate is 'switched'; "
           f"{r(sc['adjacent_in_true_chain'], sc['rebuilt'])} are adjacent in a true chain. The lake has {sc['true_switches_in_truth']} true switches, so the rebuild finds {base.pct(sc['adjacent_in_true_chain'], sc['true_adjacent_pairs'])} of {sc['true_adjacent_pairs']} true pairs.\n"]
    md += ["## Connector and skill roadmap: what to add to the origin platform\n",
           "Each row: one capability missing on the origin platform, and the number of switches from that platform that used it at the destination. Switches can appear in several rows.\n",
           table(["Add to", "Capability", "Re-dos it would address"], rows or [["-", "-", "-"]])]
    md += [f"- {len(rows)} capability gaps in total, across {sum(1 for o in P if res['switches']['by_origin'][o]['switches'])} origin platforms.",
           "- Counts are re-dos in this lake, not saved time. A switch with two gaps needs both added to be saved."
           " Small rows (n < 5) are small n.\n"]
    md += ["## Switches with nothing missing: what the origin session showed\n",
           "Where the two platforms have the same capabilities, the origin session's last turn is classed by the trace: no answer, tool error, inability phrase, or nothing visible.\n",
           table(["Origin", "Last turn of the origin session", "Switches (of all from that origin)"], rows_o or [["-", "-", "-"]])]
    nv = sum(v["residual"].get("nothing visible", 0) for v in res["switches"]["by_origin"].values()); nres = sum(sum(v["residual"].values()) for v in res["switches"]["by_origin"].values())
    md += [f"- {r(nv, nres)} of the switches with nothing missing show no sign of trouble in the trace: the person left and the trace says nothing about why.",
           "- Trouble signals are crude phrase and error checks on one turn. They can miss a wrong answer and flag a harmless tool error.\n"]

    # ---- 2
    ends = [t for t in tasks if last(t)["ends_in_trouble"]]
    res["trouble"] = {"tasks": len(tasks), "ending_in_trouble": len(ends), "score_abandoned": score_abandoned(tasks, ses), "by_platform": {}, "by_role": {}, "topics": {}}
    sig = lambda ts: {"no answer": sum(last(t)["turns"][-1]["no_answer"] for t in ts), "tool error": sum(last(t)["turns"][-1]["tool_error"] for t in ts),
                      "inability": sum(last(t)["turns"][-1]["inability"] for t in ts)}
    def trouble_rows(keyf, keys, name):
        out = []
        for k in keys:
            ts = [t for t in tasks if keyf(t) == k]; e = [t for t in ts if last(t)["ends_in_trouble"]]
            s = sig(e); res["trouble"][name][k] = {"tasks": len(ts), "ending_in_trouble": len(e), **s}
            out.append([N.get(k, k), r(len(e), len(ts)), s["no answer"], s["tool error"], s["inability"]])
        return out
    md += ["## Tasks that ended on trouble with no follow-up\n",
           "A task counts when its last session ends on a turn with no answer, a failed tool call, or an inability phrase. The signals overlap, so the three columns can add up to more than the total. "
           "The platform is the one of the last session.\n",
           table(["Last platform", "Tasks ending on trouble (of tasks ending there)", "No answer", "Tool error", "Inability"], trouble_rows(lambda t: last(t)["platform"], P, "by_platform")),
           table(["Role", "Tasks ending on trouble (of the role's tasks)", "No answer", "Tool error", "Inability"],
                 trouble_rows(lambda t: role[t["user"]], sorted(set(role[t["user"]] for t in tasks)), "by_role"))]
    sa = res["trouble"]["score_abandoned"]
    md += [f"- {r(len(ends), len(tasks))} of tasks end on trouble. {max(res['trouble']['by_platform'].items(), key=lambda kv: kv[1]['ending_in_trouble'] / max(kv[1]['tasks'], 1))[0].title()} has the highest share.",
           f"- Score against truth: the estimate flags {sa['estimated']} tasks; {sa['true_abandoned']} are truly abandoned; {sa['hit']} overlap. Precision {sa['precision']}, recall {sa['recall']}.",
           "- A trouble ending is a sign, not a decision to stop. Some people accept a partly wrong answer, and some leave without any trace of trouble.\n"]
    tp = collections.Counter(); tp_rows = []
    for t in ends:
        lt = last(t)["turns"][-1]
        if lt["no_answer"] or lt["inability"]: tp[topic(lt["input"], last(t)["first"])] += 1
    tot = sum(tp.values()); res["trouble"]["topics"] = dict(sorted(tp.items()))
    md += ["## What people were asking for when the answer failed\n",
           "Only no-answer and inability endings. Keywords are matched on the user text of that turn plus the session's first prompt; the first matching row wins.\n",
           table(["Topic", "Keywords (regex)", "Endings"], [[n, f"`{rx}`", r(tp[n], tot)] for n, rx in LEXICON] + [["other", "none of the above", r(tp["other"], tot)]])]
    md += [f"- {tot} endings with no answer or an inability phrase. The most common topic is {tp.most_common(1)[0][0] if tp else 'none'} ({tp.most_common(1)[0][1] if tp else 0}).",
           "- The lexicon is small and was built from the prompts in this lake. A different company needs its own words. Rows with fewer than 5 endings are small n.\n"]

    # ---- 3
    rows3, res["chat_only"] = [], {}
    for p in P:
        xs = [x for x in ses.values() if x["platform"] == p]; turns = [t for x in xs for t in x["turns"]]
        ts = [t for t in tasks if first(t)["platform"] == p]
        need = [x for x in xs if x["entities"] or topic(x["text"]) in DATA_NEED]
        v = {"turns": len(turns), "inability_turns": sum(t["inability"] for t in turns), "tasks_started": len(ts),
             "redone_or_trouble": sum(len(t["sessions"]) > 1 or last(t)["ends_in_trouble"] for t in ts), "redone": sum(len(t["sessions"]) > 1 for t in ts),
             "sessions": len(xs), "needing_company_data": len(need)}
        res["chat_only"][p] = v
        rows3.append([N[p], r(v["inability_turns"], v["turns"]), r(v["redone_or_trouble"], v["tasks_started"]), r(v["needing_company_data"], v["sessions"])])
    c, a = res["chat_only"]["chatly"], res["chat_only"]["atlas"]
    md += ["## Demand the chat-only platform cannot serve\n",
           "Per platform: turns whose reply has an inability phrase; tasks started there that were re-done on another platform or ended on trouble; sessions whose prompts name an order, ticket or SKU id or match the data-need words "
           "(" + ", ".join(sorted(DATA_NEED)) + "), meaning the work needs company data.\n",
           table(["Platform", "Turns with inability phrase", "Tasks started there that were re-done or ended on trouble", "Sessions needing company data"], rows3)]
    md += [f"- On Chatly, {r(c['inability_turns'], c['turns'])} of turns end in an inability phrase. On Atlas it is {r(a['inability_turns'], a['turns'])}.",
           f"- {r(c['needing_company_data'], c['sessions'])} of Chatly sessions ask for company data, which Chatly has no tools to reach.",
           f"- {r(c['redone_or_trouble'], c['tasks_started'])} of tasks started on Chatly were re-done elsewhere or ended on trouble ({c['redone']} re-done). Task counts are small, so read the shares with care.",
           "- The same scripts were played on every platform in the simulation, so these shares compare platforms on the same kind of work only if people chose the platform at random. That is not tested here.\n"]

    # ---- 4
    cov = {p: [sum(1 for x in ses.values() if x["platform"] == p and x["label"]), sum(1 for x in ses.values() if x["platform"] == p)] for p in P}
    lab_keys = [k for k in sorted(labs) if k.split(":")[0] in P]
    res["labels"] = {"file_entries": len(lab_keys), "by_platform_in_file": {p: sum(k.startswith(p + ":") for k in lab_keys) for p in P}, "expected_recordings": len(base.scripts()) * len(P),
                     "session_coverage": cov}
    lt = [t for t in tasks if first(t)["label"]]
    res["labels"]["tasks_labelled"] = [len(lt), len(tasks)]
    mt = score_match(ses); res["labels"]["score_match"] = mt
    sl = score_labels(ses, labs); res["labels"]["score_labels"] = sl
    doms = sorted({first(t)["label"]["domain"] for t in lt}); types = sorted({first(t)["label"]["task_type"] for t in lt})
    roles_ = sorted(set(role.values()))
    res["work_map"] = {"role_x_domain": {rl: {d: sum(role[t["user"]] == rl and first(t)["label"]["domain"] == d for t in lt) for d in doms} for rl in roles_},
                       "type_x_platform": {ty: {p: sum(first(t)["label"]["task_type"] == ty and first(t)["platform"] == p for t in lt) for p in P} for ty in types}, "type_fail": {}}
    md += ["## Label coverage and match accuracy\n",
           f"Labels file: {len(lab_keys)} of {res['labels']['expected_recordings']} recordings labelled at run time. A session gets the label of the script it most resembles on its own platform. "
           "This matching step uses the script texts (not available to a real company) and stands in for labelling every session directly. "
           f"{len(lt)} of {len(tasks)} tasks have a label for their first session; the tables below use only those.\n",
           table(["Platform", "Sessions with a label", "Recordings in labels file", "Session -> script match correct", "Domain correct (recordings)", "Task type correct (recordings)", "Domain correct (sessions)", "Task type correct (sessions)"],
                 [[N[p], r(*cov[p]), res["labels"]["by_platform_in_file"][p], r(*mt[p])] + [r(*sl[p][f][u]) for u in ("recordings", "sessions") for f in ("domain", "task_type")] for p in P])]
    md += [f"- The matching step picks the right script for {r(sum(v[0] for v in mt.values()), sum(v[1] for v in mt.values()))} sessions.",
           f"- Label coverage is {r(sum(v[0] for v in cov.values()), len(ses))} of sessions. If this is below 100%, rerun when the labels file is complete.",
           "- Recording-level accuracy scores the label against the designed domain and task type. Session-level accuracy also includes match errors.\n"]
    md += ["## Tasks by role and domain\n", f"Labelled tasks only (n = {len(lt)} of {len(tasks)}). Domain is the label of the task's first session.\n",
           table(["Role"] + doms + ["Total"], [[rl] + [res["work_map"]["role_x_domain"][rl][d] for d in doms] + [sum(res["work_map"]["role_x_domain"][rl].values())] for rl in roles_])]
    big = max(((rl, d, v) for rl, row in res["work_map"]["role_x_domain"].items() for d, v in row.items()), key=lambda z: z[2], default=None)
    md += [f"- The largest cell is {big[0]} / {big[1]} with {big[2]} tasks." if big else "- No labelled tasks yet.",
           "- Roles have 4 staff each, so one person can shape a whole row. Cells under 5 tasks are small n.\n"]
    md += ["## Tasks by task type and start platform\n", f"Labelled tasks only (n = {len(lt)}).\n",
           table(["Task type"] + [N[p] for p in P] + ["Total"], [[ty] + [res["work_map"]["type_x_platform"][ty][p] for p in P] + [sum(res["work_map"]["type_x_platform"][ty].values())] for ty in types])]
    md += ["- Task type is a label from a small model reading a compact view of the recording, not a measured fact." if types else "- No labelled tasks yet.",
           "- If people choose a platform by task type, this table shows it. If they choose by habit, it will look flat. The sample is too small to tell the two apart.\n"]
    rows4 = []
    for ty in types:
        ts = [t for t in lt if first(t)["label"]["task_type"] == ty]
        v = {"tasks": len(ts), "redone": sum(len(t["sessions"]) > 1 for t in ts), "trouble": sum(last(t)["ends_in_trouble"] for t in ts),
             "either": sum(len(t["sessions"]) > 1 or last(t)["ends_in_trouble"] for t in ts)}
        res["work_map"]["type_fail"][ty] = v
        rows4.append([ty, v["tasks"], r(v["redone"], v["tasks"]), r(v["trouble"], v["tasks"]), r(v["either"], v["tasks"])])
    worst = max(res["work_map"]["type_fail"].items(), key=lambda kv: kv[1]["either"] / max(kv[1]["tasks"], 1), default=None)
    md += ["## Where each kind of work fails\n", "Share of labelled tasks of each type that were re-done on another platform or ended on trouble (spans).\n",
           table(["Task type", "Tasks", "Re-done elsewhere", "Ended on trouble", "Either"], rows4 or [["-", 0, "-", "-", "-"]])]
    md += [f"- Highest failure share: {worst[0]}, {r(worst[1]['either'], worst[1]['tasks'])}." if worst else "- No labelled tasks yet.",
           "- Re-done and trouble overlap, so 'Either' is not the sum of the two. Types with fewer than 5 tasks are small n.\n"]

    # ---- 5
    ag = score_agreement(labs); res["label_agreement"] = ag
    rows5 = []
    for f in ("domain", "task_type"):
        for k, v in ag[f]["pairs"].items(): rows5.append([f, k, r(v["agree"], v["n"]), v["kappa"] if v["kappa"] is not None else "n/a"])
        rows5.append([f, "all three agree", r(ag[f]["all_three"]["agree"], ag[f]["all_three"]["n"]), ""])
    rows5b = [[f, N[p], r(v["correct"], v["n"])] for f in ("domain", "task_type") for p, v in ag[f]["accuracy"].items()]
    md += ["## Are labels comparable across platforms?\n",
           "The same script was recorded on all three platforms. This uses the script identity, which is ground truth: in a real company you would test it by running a set of tasks on purpose on every platform. Only scripts with the needed labels count (n shown).\n",
           table(["Field", "Platforms", "Agree", "Cohen's kappa"], rows5),
           table(["Field", "Platform", "Label equals designed label"], rows5b)]
    dp = ag["domain"]["pairs"].get("atlas-beacon", {"n": 0})
    md += [f"- Atlas-Beacon domain: {r(dp.get('agree', 0), dp['n'])} agree." if dp["n"] else "- No platform pair has enough labels yet; rerun when the labels file is complete.",
           f"- All three agree on domain for {r(ag['domain']['all_three']['agree'], ag['domain']['all_three']['n'])} scripts and on task type for {r(ag['task_type']['all_three']['agree'], ag['task_type']['all_three']['n'])}.",
           "- Kappa corrects for chance. With a few common labels and few scripts it is unstable; read it with n beside it.\n"]

    # ---- 6
    names = customer_names(ses); name_rx = re.compile("|".join(re.escape(n) for n in names), re.I) if names else None
    email_rx = re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+")
    rows6, res["identifiers"] = [], {"customer_names_found_in_tool_results": len(names)}
    utext = lambda x: "\n".join(t["input"] for t in x["turns"])
    for p in P:
        xs = [x for x in ses.values() if x["platform"] == p]
        v = {"sessions": len(xs), "id": sum(bool(x["entities"]) for x in xs), "email": sum(bool(email_rx.search(utext(x))) for x in xs),
             "name": sum(bool(name_rx and name_rx.search(utext(x))) for x in xs), "any": sum(bool(x["entities"] or email_rx.search(utext(x)) or (name_rx and name_rx.search(utext(x)))) for x in xs)}
        res["identifiers"][p] = v
        rows6.append([N[p], r(v["id"], v["sessions"]), r(v["email"], v["sessions"]), r(v["name"], v["sessions"]), r(v["any"], v["sessions"])])
    ci = res["identifiers"]["chatly"]
    md += ["## Identifiers typed into each tool\n",
           "Share of sessions whose user prompts contain an order, ticket or SKU id (`base.ENT`), an email address, or a full customer name. "
           f"Names come from `customer_name` fields in tool results ({len(names)} distinct names found); a name a person types that no tool ever returned is not found, and Chatly has no tools, so its names come from the other platforms' results. "
           "This counts identifiers, not sensitivity. The data has no sensitivity label.\n",
           table(["Platform", "Order/ticket/SKU id", "Email", "Customer name", "Any of the three"], rows6)]
    md += [f"- {r(ci['id'], ci['sessions'])} of Chatly sessions contain an order, ticket or SKU id, on the platform with no company data access.",
           f"- Across all platforms, {r(sum(res['identifiers'][p]['any'] for p in P), len(ses))} of sessions carry at least one identifier.",
           "- An order id alone may be harmless; a customer's name or email is more personal. This table does not rank them.\n"]

    base.save("demand.json", res)
    open(os.path.join(base.D, "demand.md"), "w").write("\n".join(md))
    print(f"sessions {len(ses)}  tasks {len(tasks)}  switches {len(sw)} ({sc['origin_fate_switched']} with origin fate 'switched')")
    print(f"tasks ending on trouble {len(ends)}  abandoned precision {sa['precision']} recall {sa['recall']}")
    print(f"labels {len(lab_keys)}/{res['labels']['expected_recordings']} recordings, {sum(v[0] for v in cov.values())}/{len(ses)} sessions labelled; match {sum(v[0] for v in mt.values())}/{len(ses)}")
    print("wrote data/demand.json and data/demand.md")


if __name__ == "__main__":
    main()
