"""Reactive replay: simulated users run the scripted tasks on the platforms they hold seats on.

    python3 replay.py          # needs the Chatly recording (chatly.py); no model calls

The user gets the RECORDED session of the platform they are on. At the first turn whose checks failed they notice with
probability 0.8; a noticed failure ends the session there, and the user re-does the task on another seat with
probability 0.7 (2 to 12 minutes later, first message paraphrased) or gives up. Writes the three platform exports and
data/truth.json. Everything is seeded: reruns give identical files.
"""
import collections, copy, datetime as dt, json, random, statistics
from common import *
import world

SEED = 20261113
P_NOTICE, P_SWITCH, MAX_SWITCH = 0.8, 0.7, 2
WINDOW = {"support": (9, 12), "operations": (13, 17), "management": (17, 20)}     # start hours by role
DAYS = [dt.date(2026, 11, d) for d in (2, 3, 4, 5, 6, 9, 10, 11, 12, 13)]
MODEL = "openrouter/free"


# ---------------------------------------------------------------- recordings

def shadow_pricer():
    import obs
    pr = obs.prices()
    twins = list(pr.values())
    fb = [statistics.median(t[0] for t in twins), statistics.median(t[1] for t in twins)]
    def f(model, tin, tout):
        m = model or ""
        p = pr.get(m[:-5] if m.endswith(":free") else m) or fb
        return (tin or 0) * p[0] + (tout or 0) * p[1]
    return f


def load_recordings():
    """rec[platform][script] = list of turns {dur_ms, checks, answered, spans | attempts, cost, tokens_in, tokens_out}"""
    price = shadow_pricer()
    rec = {p: {} for p in PLATFORMS}
    for p, f in (("atlas", "traces.jsonl"), ("beacon", "traces-noskill.jsonl")):
        spans = jl(os.path.join(AS, "data", f))
        kids = collections.defaultdict(list)
        for s in spans:
            if s["parent_span_id"]: kids[s["trace_id"]].append(s)
        for s in spans:
            if s["parent_span_id"] is not None: continue
            a = A(s)
            ks = sorted(kids[s["trace_id"]], key=lambda k: k["start_time"])
            chats = [k for k in ks if A(k)["gen_ai.operation.name"] == "chat"]
            rec[p].setdefault(a["gen_ai.conversation.id"], []).append({
                "idx": a["prism.turn_index"], "dur_ms": s["duration_ms"], "checks": [d["ok"] for d in a["eval.detail"]],
                "answered": bool((a["gen_ai.output.text"] or "").strip()), "root": s, "kids": ks,
                "cost": sum(price(A(k).get("gen_ai.response.model"), A(k).get("gen_ai.usage.input_tokens"), A(k).get("gen_ai.usage.output_tokens")) for k in chats),
                "tokens_in": sum(A(k).get("gen_ai.usage.input_tokens") or 0 for k in chats),
                "tokens_out": sum(A(k).get("gen_ai.usage.output_tokens") or 0 for k in chats)})
    for sid in rec["atlas"]:
        for p in ("atlas", "beacon"): rec[p][sid].sort(key=lambda t: t["idx"])
    for f in sorted(os.listdir(os.path.join(RUN, "chatly"))):
        r = json.load(open(os.path.join(RUN, "chatly", f)))
        sc = scenarios()[r["session_id"]]
        if len(r["turns"]) < len(sc["turns"]): raise SystemExit(f"Chatly recording incomplete: {r['session_id']}")
        rec["chatly"][r["session_id"]] = [{
            "idx": t["turn_index"], "dur_ms": sum(a["duration_ms"] for a in t["attempts"]), "checks": t["checks"], "answered": t["answered"],
            "attempts": t["attempts"], "reply": t["reply"],
            "cost": sum(price(a["model"], a["tokens_in"], a["tokens_out"]) for a in t["attempts"]),
            "tokens_in": sum(a["tokens_in"] or 0 for a in t["attempts"]), "tokens_out": sum(a["tokens_out"] or 0 for a in t["attempts"])}
            for t in r["turns"]]
    for p in PLATFORMS: assert len(rec[p]) == 32, (p, len(rec[p]))
    return rec


# ---------------------------------------------------------------- tasks and chains

def make_tasks(scs):
    rng = random.Random(SEED)
    by_role = collections.defaultdict(list)
    for u in world.USERS: by_role[u[2]].append(u[0])
    author_role = {v: k for k, v in world.ROLES.items()}
    tasks = []
    for sid in sorted(scs):
        role = author_role[scs[sid]["user"]]
        for h in rng.sample(by_role[role], 2): tasks.append({"script": sid, "user": h, "role": role})
    tasks.sort(key=lambda t: (t["user"], t["script"]))
    for i, t in enumerate(tasks): t["task_id"] = f"T{i + 1:02d}"
    return tasks


def play(task, rec, habit, rng):
    """Walk one task. Times are seconds relative to the task start."""
    seats = {p: w for p, w in habit.items()}
    pos = [p for p, w in seats.items() if w > 0]
    plat = rng.choices(pos, [seats[p] for p in pos])[0]
    tried, sessions, clock = [], [], 0.0
    while True:
        tried.append(plat)
        turns, cur, noticed = [], clock, False
        for i, t in enumerate(rec[plat][task["script"]]):
            if i: cur += rng.randint(20, 90)                                     # think and type time
            turns.append({"rec": t, "start": cur, "end": cur + t["dur_ms"] / 1000}); cur += t["dur_ms"] / 1000
            if t["checks"] and not all(t["checks"]):
                noticed = rng.random() < P_NOTICE
                break                                                            # one roll, at the first failed turn
        full = len(turns) == len(rec[plat][task["script"]])
        ses = {"platform": plat, "turns": turns, "start": clock, "end": cur, "noticed": noticed, "truncated": noticed and not full,
               "is_switch": len(sessions) > 0, "paraphrased": len(sessions) > 0}
        sessions.append(ses)
        if not noticed: ses["fate"] = "completed"; break
        rest = [p for p in seats if p not in tried]
        if rest and len(sessions) <= MAX_SWITCH and rng.random() < P_SWITCH:
            ses["fate"] = "switched"
            plat = rng.choices(rest, [seats[p] + .05 for p in rest])[0]
            clock = cur + rng.randint(120, 720)
        else:
            ses["fate"] = "abandoned"; break
    return sessions


def place(tasks, rng):
    """Put each task chain on a working day at a role-typical hour; some chains follow the user's previous one within minutes."""
    blocks = collections.defaultdict(list)
    for t in tasks:
        span = t["sessions"][-1]["end"]
        lo, hi = WINDOW[t["role"]]
        for _ in range(200):
            b = blocks[t["user"]]
            if b and rng.random() < .5:
                prev = rng.choice(b); start = prev[1] + rng.randint(180, 1500)
            else:
                day = rng.choice(DAYS); start = dt.datetime.combine(day, dt.time(lo), dt.timezone.utc).timestamp() + rng.randint(0, (hi - lo) * 3600)
            day0 = tshift(start).date()
            if tshift(start + span).date() != day0 or day0 not in DAYS: continue
            if any(start < e + 300 and s < start + span + 300 for s, e in b): continue
            if tshift(start + span).hour >= 22: continue
            b.append((start, start + span)); t["start_ts"] = start; break
        else: raise SystemExit("could not place " + t["task_id"])


def tshift(secs):
    return dt.datetime.fromtimestamp(secs, dt.timezone.utc)


# ---------------------------------------------------------------- exports

class Ids:
    def __init__(self): self.r = random.Random(SEED + 1)
    def hex(self, n): return "%0*x" % (n, self.r.getrandbits(4 * n))


def iso(ts): return tshift(ts).isoformat(timespec="milliseconds")


def export_atlas(ses, ids, handle):
    cid = "atl-" + ids.hex(10); out = []
    for k, t in enumerate(ses["turns"]):
        root, kids = t["rec"]["root"], t["rec"]["kids"]
        tid, rid = ids.hex(32), ids.hex(16)
        t0 = dt.datetime.fromisoformat(root["start_time"])
        base = ses["abs"] + t["start"]
        def conv(s, parent):
            a = {k2: v for k2, v in A(s).items() if not k2.startswith(("eval.", "prism."))}
            a["gen_ai.conversation.id"] = cid
            return a
        ra = conv(root, None); ra["user.id"] = handle; ra["session.turn_index"] = k + 1
        if k == 0 and ses["paraphrased"]: ra["gen_ai.input.text"] = ses["first_text"]
        out.append({"trace_id": tid, "span_id": rid, "parent_span_id": None, "name": root["name"], "start_time": iso(base),
                    "end_time": iso(base + t["rec"]["dur_ms"] / 1000), "status": root["status"], "attributes": ra, "duration_ms": root["duration_ms"]})
        for s in kids:
            off = (dt.datetime.fromisoformat(s["start_time"]) - t0).total_seconds()
            out.append({"trace_id": tid, "span_id": ids.hex(16), "parent_span_id": rid, "name": s["name"], "start_time": iso(base + off),
                        "end_time": iso(base + off + s["duration_ms"] / 1000), "status": s["status"], "attributes": conv(s, rid), "duration_ms": s["duration_ms"]})
    return cid, out


def export_beacon(ses, ids, email):
    th = "th_" + ids.hex(10); out = []
    for k, t in enumerate(ses["turns"]):
        root, kids = t["rec"]["root"], t["rec"]["kids"]
        ra, t0, cid = A(root), dt.datetime.fromisoformat(root["start_time"]), ids.hex(32)
        base = ses["abs"] + t["start"]
        meta = {"thread_id": th, "user_email": email}
        text = ses["first_text"] if k == 0 and ses["paraphrased"] else ra["gen_ai.input.text"]
        out.append({"id": cid, "parent_run_id": None, "root_id": cid, "run_type": "chain", "name": "shop-assistant",
                    "start_ms": int(base * 1000), "end_ms": int((base + t["rec"]["dur_ms"] / 1000) * 1000), "inputs": {"input": text},
                    "outputs": {"output": ra["gen_ai.output.text"]}, "error": ra.get("error.type"), "extra": {"metadata": meta}})
        for s in kids:
            a, off = A(s), (dt.datetime.fromisoformat(s["start_time"]) - t0).total_seconds()
            r = {"id": ids.hex(32), "parent_run_id": cid, "root_id": cid, "start_ms": int((base + off) * 1000),
                 "end_ms": int((base + off + s["duration_ms"] / 1000) * 1000), "error": a.get("error.type"), "extra": {"metadata": meta}}
            if a["gen_ai.operation.name"] == "chat":
                r.update(run_type="llm", name=a["gen_ai.request.model"], inputs={"model": a["gen_ai.request.model"]},
                         outputs={"text": a.get("gen_ai.output.text", ""), "tool_calls": a.get("gen_ai.output.tool_calls", [])})
                r["extra"]["model"] = a.get("gen_ai.response.model") or a["gen_ai.request.model"]
                if a.get("gen_ai.usage.input_tokens") is not None:
                    r["extra"]["usage"] = {"prompt_tokens": a["gen_ai.usage.input_tokens"], "completion_tokens": a["gen_ai.usage.output_tokens"]}
            else:
                r.update(run_type="tool", name=a["gen_ai.tool.name"], inputs={"input": a["gen_ai.tool.call.arguments"]},
                         outputs={"output": a["gen_ai.tool.call.result"]})
            out.append(r)
    return th, out


def export_chatly(ses, ids, emp):
    cid = "cvn_" + ids.hex(12); msgs = []
    for k, t in enumerate(ses["turns"]):
        base = ses["abs"] + t["start"]; rt = t["rec"]
        text = ses["first_text"] if k == 0 and ses["paraphrased"] else ses["script_turns"][k]["text"]
        msgs.append({"role": "user", "content": text, "ts": iso(base), "model": None, "usage": None})
        if rt["answered"]:
            ok = [a for a in rt["attempts"] if not a["error"]][0]
            msgs.append({"role": "assistant", "content": rt["reply"], "ts": iso(base + rt["dur_ms"] / 1000), "model": ok["model"],
                         "usage": {"prompt_tokens": ok["tokens_in"], "completion_tokens": ok["tokens_out"]}})
    return cid, {"conversation_id": cid, "employee_id": emp, "created_at": msgs[0]["ts"], "messages": msgs}


def counts(ses):
    """What the recording holds for the turns that were played (compared with the export and the lake in the fidelity table)."""
    ts = [t["rec"] for t in ses["turns"]]
    chats = lambda t: [k for k in t["kids"] if A(k)["gen_ai.operation.name"] == "chat"]
    tools = lambda t: [k for k in t["kids"] if A(k)["gen_ai.operation.name"] == "execute_tool"]
    if ses["platform"] == "chatly":
        att = [a for t in ts for a in t["attempts"]]
        return {"turns": len(ts), "requests": len(att), "failed_requests": sum(bool(a["error"]) for a in att), "tool_calls": 0,
                "tool_errors": 0, "tokens_in": sum(a["tokens_in"] or 0 for a in att), "tokens_out": sum(a["tokens_out"] or 0 for a in att)}
    return {"turns": len(ts), "requests": sum(len(chats(t)) for t in ts), "failed_requests": sum(k["status"] == "error" for t in ts for k in chats(t)),
            "tool_calls": sum(len(tools(t)) for t in ts), "tool_errors": sum(k["status"] == "error" for t in ts for k in tools(t)),
            "tokens_in": sum(t["tokens_in"] for t in ts), "tokens_out": sum(t["tokens_out"] for t in ts)}


# ---------------------------------------------------------------- main

def main():
    scs, rec = scenarios(), load_recordings()
    para = json.load(open(os.path.join(D, "paraphrases.json")))
    tasks = make_tasks(scs)
    users = {u[0]: u for u in world.USERS}
    for t in tasks:
        t["sessions"] = play(t, rec, users[t["user"]][3], random.Random(f"{SEED}-{t['task_id']}"))
    place(tasks, random.Random(SEED + 2))
    directory = {u["handle"]: u for u in json.load(open(os.path.join(D, "directory.json")))["users"]}
    ids = Ids()
    exports = {p: [] for p in PLATFORMS}
    truth = {"seed": SEED, "rules": {"p_notice": P_NOTICE, "p_switch": P_SWITCH, "max_switches": MAX_SWITCH, "switch_gap_minutes": [2, 12]},
             "tasks": [], "seats": [], "recordings": {}}
    for t in sorted(tasks, key=lambda x: x["start_ts"]):
        sc, ch = scs[t["script"]], []
        for n, ses in enumerate(t["sessions"]):
            ses["abs"] = t["start_ts"] + ses["start"]
            ses["first_text"] = para[t["script"]]; ses["script_turns"] = sc["turns"]
            d = directory[t["user"]]
            if ses["platform"] == "atlas": nid, rows = export_atlas(ses, ids, d["handle"]); exports["atlas"] += rows
            elif ses["platform"] == "beacon": nid, rows = export_beacon(ses, ids, d["email"]); exports["beacon"] += rows
            else: nid, rows = export_chatly(ses, ids, d["employee_id"]); exports["chatly"].append(rows)
            ch.append({"lake_session_id": f"{ses['platform']}:{nid}", "platform": ses["platform"], "start": iso(ses["abs"]),
                       "end": iso(t["start_ts"] + ses["end"]), "is_switch": ses["is_switch"], "paraphrased": ses["paraphrased"],
                       "turns_played": len(ses["turns"]), "turns_in_script": len(sc["turns"]), "noticed_failure": ses["noticed"],
                       "fate": ses["fate"], "turn_checks": [t2["rec"]["checks"] for t2 in ses["turns"]],
                       "turn_answered": [t2["rec"]["answered"] for t2 in ses["turns"]],
                       "truncated": ses["truncated"], "cost": sum(t2["rec"]["cost"] for t2 in ses["turns"]), "counts": counts(ses)})
        truth["tasks"].append({"task_id": t["task_id"], "user": t["user"], "role": t["role"], "script": t["script"],
                               "designed": {"domain": sc["designed"]["domain"], "task_type": sc["designed"]["task_type"]},
                               "start": ch[0]["start"], "sessions": ch, "final_fate": ch[-1]["fate"],
                               "n_switches": len(ch) - 1})
    for u in world.USERS:
        for p, w in u[3].items():
            truth["seats"].append({"handle": u[0], "platform": p, "start_weight": w, "designed_idle": w < world.IDLE_THRESHOLD})
    for p in PLATFORMS:
        for sid, turns in rec[p].items():
            ver = [t for t in turns if t["checks"]]
            truth["recordings"][f"{p}:{sid}"] = {
                "platform": p, "script": sid, "designed": scs[sid]["designed"], "verifiable_turns": len(ver),
                "passed_turns": sum(all(t["checks"]) for t in ver), "turn_checks": [t["checks"] for t in turns],
                "turn_answered": [t["answered"] for t in turns], "turn_cost": [round(t["cost"], 8) for t in turns],
                "tokens_in": sum(t["tokens_in"] for t in turns), "tokens_out": sum(t["tokens_out"] for t in turns),
                "requests": sum(len(t["attempts"]) if "attempts" in t else sum(A(k)["gen_ai.operation.name"] == "chat" for k in t["kids"]) for t in turns),
                "tool_calls": sum(sum(A(k)["gen_ai.operation.name"] == "execute_tool" for k in t["kids"]) for t in turns if "kids" in t)}
    truth["tasks"].sort(key=lambda x: x["task_id"])
    json.dump(truth, open(os.path.join(D, "truth.json"), "w"), indent=1)
    for p, name in (("atlas", "export_atlas"), ("beacon", "export_beacon"), ("chatly", "export_chatly")):
        with open(os.path.join(D, name + ".jsonl"), "w") as f:
            for r in exports[p]: f.write(json.dumps(r, sort_keys=True) + "\n")
    n_s = collections.Counter(s["platform"] for t in truth["tasks"] for s in t["sessions"])
    print("tasks", len(tasks), "sessions", dict(n_s), "switches", sum(t["n_switches"] for t in truth["tasks"]),
          "abandoned", sum(t["final_fate"] == "abandoned" for t in truth["tasks"]))


if __name__ == "__main__":
    main()
