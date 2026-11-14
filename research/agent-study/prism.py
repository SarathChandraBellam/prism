"""Prism pipeline over the agent-study traces: facts -> chat view -> labels -> SQL -> narrative.

    python3 prism.py label       # session labels (two independent draws) and per-prompt acts, cached
    python3 prism.py report      # aggregates in SQLite, evaluation against the designed labels, narrated reports

All model calls go to PRISM_MODEL (default openrouter/free). Count definitions are the
round 2 codebook (research/study/round2.py). Standard library only.
"""
import collections, hashlib, json, os, re, sqlite3, sys, time
from concurrent.futures import ThreadPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__))
D = os.path.join(HERE, "data")
CACHE = os.path.join(HERE, "cache"); os.makedirs(CACHE, exist_ok=True)
MODEL = os.environ.get("PRISM_MODEL", "openrouter/free")
DOMAINS = ["support", "operations", "strategy", "writing"]
TASKS = ["lookup", "decide", "triage", "report", "analysis", "draft", "advise"]
ACTS = ["request", "refinement", "correction", "feedback_relay", "question", "reexplain"]
A = lambda s: s["attributes"]

SESSION_PROMPT = """You label one session between a person and an AI assistant for a small online shop.
You see a compact view: each user turn (U), one line of tool activity, and the head of the assistant reply (A).

Return ONLY JSON:
{"domain": one of %s,
 "task_type": one of %s,
 "topics": [1 to 3 short topic phrases],
 "outcome": one of ["completed","partial","failed","unclear"],
 "n_corrections": int, "n_feedback_relays": int, "n_refinements": int, "n_understanding_questions": int,
 "reexplained_turns": [int, ...],
 "summary": "one sentence, no names or order numbers"}

domain: support = customer orders, refunds, tickets, replies to customers; operations = sales reporting, stock, data
 questions about the business; strategy = decisions, pricing, planning, advice for the owner; writing = copy or templates
 that are not about one customer case.
task_type (the MAIN task of the session): lookup = fetch a fact; decide = apply a rule to reach a decision;
 triage = sort or prioritise items; report = produce a recurring or periodic report; analysis = ad-hoc questions on data;
 draft = write text; advise = think a decision or plan through.
- n_corrections: user turns saying the assistant was wrong, misunderstood, or did something unwanted.
- n_feedback_relays: user turns reporting errors, results, or what someone else said back to the assistant.
- n_refinements: user turns asking to adjust the assistant's previous output without saying it was wrong.
- n_understanding_questions: user turns asking a question in order to understand something.
- reexplained_turns: numbers of user turns that restate information the user had ALREADY given earlier in this
  session (same facts or instructions again). Empty list if none.""" % (json.dumps(DOMAINS), json.dumps(TASKS))

TURN_PROMPT = """You label ONE message that a person sent to an AI assistant, in the middle of a work session.
Return ONLY JSON: {"act": one of %s}

request = asks for a new piece of work or a fact; refinement = asks to adjust the previous output without saying it
was wrong (shorter, another format, add something); correction = says the assistant was wrong, misunderstood, or did
something unwanted; feedback_relay = reports an error message, a result, or what another person said, back to the
assistant; question = asks in order to understand or to get an opinion (why, how, should we, which would you);
reexplain = repeats facts or instructions the person says they already gave ("as I said", "again").""" % json.dumps(ACTS)

NARRATE_PROMPT = """You write a short reflection report for one person about how they worked with an AI assistant in the
period. You get aggregates as JSON. Rules: use ONLY numbers that appear in the JSON, never compute new ones; no
praise; plain language. Write: (1) a narrative of 4 to 6 sentences, (2) "Questions to reflect on" with 2 questions,
(3) "Suggestions" with 2 concrete suggestions. Markdown."""


def call(system, user, tag=""):
    """Cached model call returning (parsed JSON or text, served model)."""
    import agent
    key = hashlib.sha256(json.dumps([MODEL, system, user, tag]).encode()).hexdigest()[:24]
    path = os.path.join(CACHE, key + ".json")
    if os.path.exists(path):
        c = json.load(open(path)); return c["out"], c["model"]
    want_json = "ONLY JSON" in system
    for attempt in range(6):
        r, err, _ = agent.post({"model": MODEL, "temperature": 0, "max_tokens": 1200,
                                "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}]})
        if r:
            txt = r["choices"][0]["message"].get("content") or ""
            out = txt
            if want_json:
                m = re.search(r"\{[\s\S]*\}", txt)
                try: out = json.loads(m.group(0)) if m else None
                except ValueError: out = None
            if out:
                json.dump({"out": out, "model": r.get("model"), "usage": r.get("usage")}, open(path, "w"))
                return out, r.get("model")
        time.sleep(3 * (attempt + 1))
    return None, None


# ---------------------------------------------------------------- stage 0: sessions and trace facts (no LLM)

def load():
    spans = [json.loads(l) for l in open(os.path.join(D, "traces.jsonl"))]
    sc = {s["session_id"]: s for s in json.load(open(os.path.join(D, "scenarios.json")))}
    sess = collections.defaultdict(lambda: {"turns": []})
    kids = collections.defaultdict(list)
    for s in spans:
        if s["parent_span_id"]: kids[s["trace_id"]].append(s)
    for s in spans:
        if s["parent_span_id"] is None:
            sess[A(s)["gen_ai.conversation.id"]]["turns"].append((s, sorted(kids[s["trace_id"]], key=lambda k: k["start_time"])))
    for v in sess.values(): v["turns"].sort(key=lambda t: A(t[0])["prism.turn_index"])
    return sess, sc


def facts(sid, v):
    roots = [t[0] for t in v["turns"]]
    kids = [k for t in v["turns"] for k in t[1]]
    tools = [k for k in kids if A(k)["gen_ai.operation.name"] == "execute_tool"]
    chats = [k for k in kids if A(k)["gen_ai.operation.name"] == "chat"]
    srv = collections.Counter(A(k).get("mcp.server.name") for k in tools)
    return {"session_id": sid, "user": A(roots[0])["user.id"], "started_at": A(roots[0])["prism.sim_start"],
            "ended_at": A(roots[-1])["prism.sim_end"], "turns": len(roots), "model_calls": len(chats), "tool_calls": len(tools),
            "tool_errors": sum(k["status"] == "error" for k in tools), "shop_calls": srv["shop"], "fs_calls": srv["filesystem"],
            "memory_calls": srv["memory"], "skill_loads": srv["skill"],
            "skills": ",".join(sorted({A(k).get("prism.skill.name") or "" for k in tools if A(k).get("mcp.server.name") == "skill"})),
            "tokens_in": sum(A(k).get("gen_ai.usage.input_tokens") or 0 for k in chats),
            "tokens_out": sum(A(k).get("gen_ai.usage.output_tokens") or 0 for k in chats),
            "checks": sum(A(r)["eval.checks"] for r in roots), "checks_passed": sum(A(r)["eval.passed"] for r in roots),
            "turns_checked": sum(A(r)["eval.checks"] > 0 for r in roots),
            "turns_passed": sum(A(r)["eval.checks"] > 0 and A(r)["eval.passed"] == A(r)["eval.checks"] for r in roots)}


def chat_view(v):
    """Compact view (C3 in the context study): user text, one line of tool activity, reply head and tail.
    Skill bodies and tool outputs are harness text and are left out."""
    lines = []
    for root, kids in v["turns"]:
        i = A(root)["prism.turn_index"]
        lines.append(f"U{i}: {A(root)['gen_ai.input.text']}")
        acts = []
        for k in kids:
            if A(k)["gen_ai.operation.name"] != "execute_tool": continue
            name = A(k)["gen_ai.tool.name"]
            if name == "load_skill": name = f"load_skill({A(k).get('prism.skill.name')})"
            acts.append(f"{name} {'ERROR' if k['status'] == 'error' else 'ok'}")
        if acts: lines.append("   tools: " + "; ".join(acts))
        rep = " ".join((A(root)["gen_ai.output.text"] or "(no answer)").split())
        lines.append(f"A{i}: " + (rep if len(rep) <= 420 else rep[:300] + " […] " + rep[-100:]))
    return "\n".join(lines)


# ---------------------------------------------------------------- stage 1: labels

def label():
    sess, sc = load()
    jobs = []
    for sid, v in sorted(sess.items()):
        view = chat_view(v)
        for draw in ("a", "b"):
            jobs.append(("session", sid, draw, SESSION_PROMPT, view))
        for root, _ in v["turns"]:
            jobs.append(("turn", sid, A(root)["prism.turn_index"], TURN_PROMPT, A(root)["gen_ai.input.text"]))
    out = {"session": collections.defaultdict(dict), "turn": collections.defaultdict(dict), "view_chars": {}}
    for sid, v in sess.items(): out["view_chars"][sid] = len(chat_view(v))

    def run(j):
        kind, sid, k, system, user = j
        return j, call(system, user, tag=str(k) if kind == "session" else "")
    with ThreadPoolExecutor(3) as ex:
        for (kind, sid, k, _, _), (lab, model) in ex.map(run, jobs):
            out[kind][sid][str(k)] = {"labels": lab, "model": model}
    json.dump(out, open(os.path.join(D, "prism_labels.json"), "w"), indent=1)
    bad = sum(1 for kind in ("session", "turn") for s in out[kind].values() for x in s.values() if not x["labels"])
    print("labelled", len(jobs), "calls,", bad, "failed")


# ---------------------------------------------------------------- stages 3-4 and evaluation

def spearman(x, y):
    def rank(v):
        o = sorted(range(len(v)), key=lambda i: v[i]); r = [0.0] * len(v); i = 0
        while i < len(o):
            j = i
            while j + 1 < len(o) and v[o[j + 1]] == v[o[i]]: j += 1
            for k in range(i, j + 1): r[o[k]] = (i + j) / 2
            i = j + 1
        return r
    a, b = rank(x), rank(y); ma, mb = sum(a) / len(a), sum(b) / len(b)
    den = (sum((p - ma) ** 2 for p in a) * sum((p - mb) ** 2 for p in b)) ** .5
    return sum((p - ma) * (q - mb) for p, q in zip(a, b)) / den if den else float("nan")


def kappa(x, y):
    n = len(x); po = sum(p == q for p, q in zip(x, y)) / n
    cx, cy = collections.Counter(x), collections.Counter(y)
    pe = sum(cx[k] * cy[k] for k in cx) / n / n
    return (po - pe) / (1 - pe) if pe < 1 else float("nan")


def report():
    sess, sc = load()
    lab = json.load(open(os.path.join(D, "prism_labels.json")))
    lines = []
    def P(s=""): lines.append(s); print(s)
    def table(head, rows):
        P("| " + " | ".join(head) + " |"); P("|" + "---|" * len(head))
        for r in rows: P("| " + " | ".join(str(x) for x in r) + " |")
        P()
    sids = sorted(sess)
    des = {s: sc[s]["designed"] for s in sids}
    S = {d: {s: (lab["session"][s].get(d) or {}).get("labels") or {} for s in sids} for d in "ab"}
    T = {s: {int(k): ((v.get("labels") or {}).get("act")) for k, v in lab["turn"][s].items()} for s in sids}
    turn_models = collections.Counter(v.get("model") for s in sids for v in lab["turn"][s].values())
    sess_models = collections.Counter(v.get("model") for s in sids for v in lab["session"][s].values())

    P("# Prism evaluation (generated by prism.py)\n")
    P(f"Sessions: {len(sids)}. Labelling model: `{MODEL}`, which served {len(sess_models)} different models for session labels and {len(turn_models)} for turn labels.\n")
    P("## 1. Session labels against the designed labels\n")
    rows = []
    for f, key in (("domain", "domain"), ("task_type", "task_type")):
        row = [f]
        for d in "ab":
            ok = [S[d][s].get(key) == des[s][f] for s in sids if S[d][s]]
            row.append(f"{100 * sum(ok) / len(ok):.0f}% (n={len(ok)})")
        both = [s for s in sids if S["a"][s] and S["b"][s]]
        row.append(f"{100 * sum(S['a'][s].get(key) == S['b'][s].get(key) for s in both) / len(both):.0f}%, κ {kappa([S['a'][s].get(key) for s in both], [S['b'][s].get(key) for s in both]):.2f}")
        rows.append(row)
    table(["Label", "Draw A correct", "Draw B correct", "A–B agreement"], rows)

    P("## 2. Behaviour counts: session-level label vs per-prompt label, against the design\n")
    cnt = {"corrections": ("n_corrections", "correction"), "feedback_relays": ("n_feedback_relays", "feedback_relay"),
           "refinements": ("n_refinements", "refinement"), "questions": ("n_understanding_questions", "question")}
    rows = []
    derived = {s: collections.Counter(T[s].values()) for s in sids}
    for name, (skey, act) in cnt.items():
        truth = [des[s][name] for s in sids]
        row = [name, sum(truth)]
        for src in ("a", "b", "turn"):
            got = [derived[s][act] if src == "turn" else int(S[src][s].get(skey) or 0) for s in sids]
            row += [sum(got), f"{100 * sum(g == t for g, t in zip(got, truth)) / len(sids):.0f}%", f"{spearman(got, truth):.2f}"]
        rows.append(row)
    table(["Count", "Designed total", "A total", "A exact", "A ρ", "B total", "B exact", "B ρ", "Per-prompt total", "Per-prompt exact", "Per-prompt ρ"], rows)
    truth_re = [bool(des[s]["reexplained_turns"]) for s in sids]
    rows = []
    for src in ("a", "b", "turn"):
        got = [("reexplain" in T[s].values()) if src == "turn" else bool(S[src][s].get("reexplained_turns")) for s in sids]
        tp = sum(g and t for g, t in zip(got, truth_re))
        rows.append([{"a": "session label, draw A", "b": "session label, draw B", "turn": "per-prompt label"}[src], sum(truth_re), sum(got), tp])
    table(["Re-explanation detected by", "Designed sessions", "Flagged sessions", "Correct flags"], rows)

    P("## 3. Per-prompt act labels (prompt only) against the design\n")
    pairs = [(sc[s]["turns"][i - 1]["act"], T[s].get(i)) for s in sids for i in T[s]]
    ok = sum(a == b for a, b in pairs)
    P(f"Accuracy {100 * ok / len(pairs):.0f}% (n={len(pairs)}), κ {kappa([p[0] for p in pairs], [str(p[1]) for p in pairs]):.2f}.\n")
    rows = []
    for a in ACTS:
        tp = sum(x == a and y == a for x, y in pairs); n = sum(x == a for x, _ in pairs); m = sum(y == a for _, y in pairs)
        rows.append([a, n, m, f"{100 * tp / n:.0f}%" if n else "–", f"{100 * tp / m:.0f}%" if m else "–",
                     ", ".join(f"{k}×{c}" for k, c in collections.Counter(str(y) for x, y in pairs if x == a and y != a).most_common(3))])
    table(["Act", "Designed", "Predicted", "Recall", "Precision", "Confused with"], rows)

    # ---- stage 3: aggregates in SQL. Records use draw A for topics/domain/task and per-prompt acts for counts.
    db_path = os.path.join(D, "prism.db")
    if os.path.exists(db_path): os.remove(db_path)
    db = sqlite3.connect(db_path)
    F = [facts(s, sess[s]) for s in sids]
    db.execute(f"CREATE TABLE facts({', '.join(F[0])})")
    db.executemany(f"INSERT INTO facts VALUES({','.join('?' * len(F[0]))})", [tuple(f.values()) for f in F])
    db.execute("CREATE TABLE records(session_id, domain, task_type, outcome, topics, summary, corrections, feedback_relays, refinements, questions, reexplains)")
    for s in sids:
        r, c = S["a"][s] or S["b"][s], derived[s]
        db.execute("INSERT INTO records VALUES(?,?,?,?,?,?,?,?,?,?,?)", (s, r.get("domain"), r.get("task_type"), r.get("outcome"),
                   json.dumps(r.get("topics") or []), r.get("summary"), c["correction"], c["feedback_relay"], c["refinement"], c["question"], c["reexplain"]))
    db.commit()
    Q = lambda q, *a: db.execute(q, a).fetchall()

    P("## 4. Aggregates (plain SQL over records and trace facts)\n")
    table(["Person", "Sessions", "Turns", "Turns per session", "Active days", "Corrections", "Feedback relays", "Refinements", "Questions", "Re-explanations",
           "Tool calls per turn", "Sessions with a skill", "Verified turns passed"],
          Q("""SELECT f.user, count(*), sum(f.turns), round(1.0*sum(f.turns)/count(*),1), count(DISTINCT substr(f.started_at,1,10)),
                      sum(r.corrections), sum(r.feedback_relays), sum(r.refinements), sum(r.questions), sum(r.reexplains),
                      round(1.0*sum(f.tool_calls)/sum(f.turns),1), sum(f.skill_loads>0), sum(f.turns_passed)||'/'||sum(f.turns_checked)
               FROM facts f JOIN records r USING(session_id) GROUP BY f.user"""))
    table(["Person", "Domain", "Sessions"], Q("SELECT f.user, r.domain, count(*) FROM facts f JOIN records r USING(session_id) GROUP BY 1,2 ORDER BY 1,3 DESC"))
    table(["Person", "Task type", "Sessions"], Q("SELECT f.user, r.task_type, count(*) FROM facts f JOIN records r USING(session_id) GROUP BY 1,2 ORDER BY 1,3 DESC"))
    table(["Person", "Part of day", "Sessions"], Q("""SELECT user, CASE WHEN cast(substr(started_at,12,2) AS int)<12 THEN 'morning'
               WHEN cast(substr(started_at,12,2) AS int)<18 THEN 'afternoon' ELSE 'evening' END, count(*) FROM facts GROUP BY 1,2 ORDER BY 1,3 DESC"""))
    P("Where the two analyses meet: behaviour counts joined to verified answer quality.\n")
    table(["Sessions with…", "Sessions", "Verified turns passed", "Model calls per turn", "Input tokens per turn"],
          Q("""SELECT CASE WHEN r.corrections+r.reexplains>0 THEN 'a correction or re-explanation' ELSE 'neither' END, count(*),
                      sum(f.turns_passed)||'/'||sum(f.turns_checked), round(1.0*sum(f.model_calls)/sum(f.turns),1), sum(f.tokens_in)/sum(f.turns)
               FROM facts f JOIN records r USING(session_id) GROUP BY 1"""))
    table(["Task type (labelled)", "Sessions", "Verified turns passed", "Skill loaded in", "Tokens in per turn"],
          Q("""SELECT r.task_type, count(*), sum(f.turns_passed)||'/'||sum(f.turns_checked), sum(f.skill_loads>0), sum(f.tokens_in)/sum(f.turns)
               FROM facts f JOIN records r USING(session_id) GROUP BY 1 ORDER BY 2 DESC"""))

    # ---- stage 4: one narrator call per person, numbers validated against the aggregates
    P("## 5. Narrated reports\n")
    view_tok = sum(lab["view_chars"].values()) / 4
    full_tok = sum(f["tokens_in"] for f in F)
    P(f"Extraction input: the compact view is about {view_tok / len(sids):,.0f} tokens per session; the agent itself consumed {full_tok / len(sids):,.0f} input tokens per session ({100 * view_tok / full_tok:.1f}%).\n")
    for user in sorted({f["user"] for f in F}):
        cols = ["sessions", "turns", "active_days", "corrections", "feedback_relays", "refinements", "understanding_questions", "reexplanations",
                "tool_calls", "sessions_with_a_skill", "verified_turns_passed", "verified_turns_total"]
        agg = dict(zip(cols, Q("""SELECT count(*), sum(f.turns), count(DISTINCT substr(f.started_at,1,10)), sum(r.corrections), sum(r.feedback_relays),
              sum(r.refinements), sum(r.questions), sum(r.reexplains), sum(f.tool_calls), sum(f.skill_loads>0), sum(f.turns_passed), sum(f.turns_checked)
              FROM facts f JOIN records r USING(session_id) WHERE f.user=?""", user)[0]))
        agg["domains"] = dict(Q("SELECT r.domain, count(*) FROM facts f JOIN records r USING(session_id) WHERE f.user=? GROUP BY 1", user))
        agg["task_types"] = dict(Q("SELECT r.task_type, count(*) FROM facts f JOIN records r USING(session_id) WHERE f.user=? GROUP BY 1", user))
        agg["sessions_by_part_of_day"] = dict(Q("""SELECT CASE WHEN cast(substr(started_at,12,2) AS int)<12 THEN 'morning' WHEN cast(substr(started_at,12,2) AS int)<18
              THEN 'afternoon' ELSE 'evening' END, count(*) FROM facts WHERE user=? GROUP BY 1""", user))
        agg["skills_used"] = dict(collections.Counter(k for f in F if f["user"] == user for k in f["skills"].split(",") if k))
        agg["example_summaries"] = [x[0] for x in Q("SELECT r.summary FROM facts f JOIN records r USING(session_id) WHERE f.user=? AND r.summary IS NOT NULL LIMIT 4", user)]
        text, model = call(NARRATE_PROMPT, json.dumps({"person": user, "period": "2 to 13 November 2026", "aggregates": agg}, indent=1))
        allowed = set(re.findall(r"\d+(?:\.\d+)?", json.dumps(agg))) | {"2", "13", "2026", "1", "3"}
        nums = set(re.findall(r"\d+(?:\.\d+)?", re.sub(r"(?m)^\s*\d+\.\s", "", text or "")))
        P(f"### {user} (narrator: `{model}`)\n")
        P(f"Number check: {len(nums - allowed)} numbers not found in the aggregates{' → ' + ', '.join(sorted(nums - allowed)) if nums - allowed else ''}.\n")
        P("\n".join("> " + l for l in (text or "(no narrative returned)").strip().splitlines()) + "\n")
    open(os.path.join(D, "prism_report.md"), "w").write("\n".join(lines) + "\n")


if __name__ == "__main__":
    {"label": label, "report": report}[sys.argv[1]]()
