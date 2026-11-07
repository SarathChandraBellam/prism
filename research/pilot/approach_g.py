"""Approach G: label each user turn with an interaction act (batched per session, layered context),
then derive session collaboration pattern deterministically. Compared with session-level extraction."""
import json, os, re, collections, sys
import run  # reuses call(), SYS, cache, spent()

HERE = os.path.dirname(os.path.abspath(__file__))
PICK = [x for x in os.environ.get("PILOT_G_SESSIONS", "").split(",") if x]  # session id prefixes; empty = all sessions with 4-10 traces
CHEAP, REF = "z-ai/glm-5.3-flash", "z-ai/glm-5.3"
ACTS = ["instruct", "relay_feedback", "correct", "refine", "ask_explain", "request_review", "approve_continue", "reexplain", "unclear"]

ACT_SYS = """You label each USER turn in a session between a person and an AI coding/chat assistant with ONE interaction act.
Acts:
- instruct: gives a new task or direction (build, run, change something new)
- relay_feedback: reports results/errors/state back (pastes error, "still failing", "try now", "it works but...")
- correct: says the assistant got something wrong or misunderstood ("no, I meant...")
- refine: asks to adjust the assistant's previous output ("shorter", "also add X", "rename")
- ask_explain: asks a question to understand something
- request_review: asks the assistant to check/review/verify work
- approve_continue: approves or lets the assistant carry on ("yes", "go", "finish what's needed")
- reexplain: repeats context the assistant already had
- unclear: cannot tell from the given context (prefer this over guessing)
Return ONLY JSON: {"turns":[{"i":<turn number>,"act":"<act>","confidence":<0..1>}]} with one entry per turn."""

ERR = re.compile(r"(Traceback|Error:|exception|failed|stack trace|TypeError|ENOENT|exit code)", re.I)


def turns_of(s):
    out = []
    for t in s["per_trace"]:
        u = re.search(r"USER: (.*?)(\ntool=|\nASSISTANT|\Z)", t, re.S)
        tools = re.findall(r"^tool=(\S+) status=(\S+)", t, re.M)
        fin = re.search(r"ASSISTANT\(final\): (.*)", t, re.S)
        out.append({"user": (u.group(1) if u else "").strip(),
                    "tools": tools, "final": (fin.group(1) if fin else "").strip()})
    return out


def render(turns, layer):
    parts = []
    for i, t in enumerate(turns, 1):
        p = turns[i - 2] if i > 1 else None
        lines = [f"--- TURN {i}"]
        if layer >= 4 and p:
            lines.append(f"previous user turn: {p['user'][:400]}")
        if layer >= 2 and p:
            n = len(p["tools"]); e = sum(1 for _, st in p["tools"] if st == "error")
            edits = sum(1 for nm, _ in p["tools"] if nm in ("Edit", "Write", "MultiEdit", "NotebookEdit"))
            runs = sum(1 for nm, _ in p["tools"] if nm == "Bash")
            lines.append(f"agent activity before this turn: {n} tool calls, {edits} edits, {runs} commands, {e} errors")
        if layer >= 3 and p and p["final"]:
            f = p["final"]; f = f if len(f) <= 500 else f[:250] + " […] " + f[-250:]
            lines.append(f"previous assistant reply: {f}")
        lines.append(f"USER: {t['user'][:1500]}")
        parts.append("\n".join(lines))
    return "\n\n".join(parts)


def label_turns(model, s, layer):
    turns = turns_of(s)
    r = run.call(model, ACT_SYS, f"(context layer {layer})\n\n" + render(turns, layer), f"G|{s['session_id']}|L{layer}")
    lab = {}
    for x in ((r.get("labels") or {}).get("turns") or []):
        try: lab[int(x["i"])] = (x.get("act") if x.get("act") in ACTS else "unclear", float(x.get("confidence", 0)))
        except Exception: pass
    return [lab.get(i, ("unclear", 0.0)) for i in range(1, len(turns) + 1)], r


def reduce_pattern(acts, conf_min=0.5):
    """Deterministic mapping from act shares to Economic Index pattern (hand-written v0)."""
    a = [x for x, c in acts if x != "unclear" and c >= conf_min]
    if not a:
        return "unclear", {}
    c = collections.Counter(a); n = len(a); sh = {k: v / n for k, v in c.items()}
    scores = {
        "feedback_loop": sh.get("relay_feedback", 0),
        "task_iteration": sh.get("refine", 0) + sh.get("correct", 0),
        "learning": sh.get("ask_explain", 0),
        "validation": sh.get("request_review", 0),
        "directive": sh.get("instruct", 0) + sh.get("approve_continue", 0) * 0.5,
    }
    return max(scores, key=scores.get), {k: round(v, 2) for k, v in sorted(sh.items(), key=lambda kv: -kv[1])}


def session_label(model, view, s):
    r = run.call(model, run.SYS, f"SESSION ({view} view):\n\n{s[view]}", f"{view}|{s['session_id']}")
    return (r.get("labels") or {}), r


if __name__ == "__main__":
    ss = [json.loads(l) for l in open(os.path.join(HERE, "sessions.jsonl"))]
    if PICK:
        ss = [s for s in ss if s["session_id"][:8] in PICK]
    else:
        ss = [s for s in ss if 4 <= len(s["per_trace"]) <= 10][:6]
    start = run.spent()
    rows, layer_agree, turn_total = [], collections.defaultdict(list), 0
    for s in ss:
        ref_s, _ = session_label(REF, "full", s)
        base_s, _ = session_label(CHEAP, "chat_err", s)
        ref_turns, _ = label_turns(REF, s, 4)          # turn-level reference: strong model, widest context
        per_layer = {L: label_turns(CHEAP, s, L)[0] for L in (1, 2, 3, 4)}
        turn_total += len(ref_turns)
        for L, acts in per_layer.items():
            layer_agree[L] += [a[0] == b[0] for a, b in zip(acts, ref_turns)]
        g_pat, shares = reduce_pattern(per_layer[3])
        ref_g_pat, _ = reduce_pattern(ref_turns)
        rows.append({"sid": s["session_id"][:8], "proj": s["project"][:10], "traces": len(ref_turns),
                     "ref_full": ref_s.get("collaboration_pattern"), "session_llm": base_s.get("collaboration_pattern"),
                     "G_cheap": g_pat, "G_ref_turns": ref_g_pat, "shares": shares,
                     "ref_reexpl": ref_s.get("context_reexplained"),
                     "G_reexpl": any(a == "reexplain" for a, c in per_layer[3]),
                     "unclear_L3": sum(a == "unclear" for a, _ in per_layer[3]),
                     "turns_ref": [a for a, _ in ref_turns], "turns_L3": [a for a, _ in per_layer[3]]})

    print(f"sessions {len(ss)}, turns {turn_total}, spent this run ${run.spent() - start:.4f}, total ${run.spent():.4f}\n")
    print("TURN-ACT AGREEMENT vs strong model (L4) by context layer (cheap model):")
    names = {1: "user msg only", 2: "+ agent activity", 3: "+ prev reply", 4: "+ prev user turn"}
    for L in (1, 2, 3, 4):
        v = layer_agree[L]; print(f"  L{L} {names[L]:18s} {sum(v)}/{len(v)} = {sum(v)/len(v):.0%}")
    print("\nSESSION COLLABORATION PATTERN:")
    print(f"  {'session':9s} {'project':10s} {'tr':>2s}  {'REF(full)':15s} {'session-LLM':15s} {'G(cheap)':15s} {'G(ref turns)':15s} unclear  shares(L3)")
    for r in rows:
        print(f"  {r['sid']:9s} {r['proj']:10s} {r['traces']:>2d}  {str(r['ref_full']):15s} {str(r['session_llm']):15s} {r['G_cheap']:15s} {r['G_ref_turns']:15s} {r['unclear_L3']:>5d}    {r['shares']}")
    agree = lambda k: sum(r[k] == r["ref_full"] for r in rows)
    print(f"\n  match REF: session-LLM {agree('session_llm')}/{len(rows)}, G(cheap) {agree('G_cheap')}/{len(rows)}, G(ref turns) {agree('G_ref_turns')}/{len(rows)}")
    print(f"  context_reexplained match REF: G {sum(r['G_reexpl'] == bool(r['ref_reexpl']) for r in rows)}/{len(rows)}")
    print("\nTURN LABELS (ref vs cheap L3):")
    for r in rows:
        print(f"  {r['sid']}: ref {r['turns_ref']}\n            L3  {r['turns_L3']}")
    json.dump(rows, open(os.path.join(HERE, "g_results.json"), "w"), indent=1)
