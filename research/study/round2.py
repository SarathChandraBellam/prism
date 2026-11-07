"""Round 2: (A) redefined labels and reference agreement, (B) per-turn context against SWE-chat's
human-validated prompt labels, (C) context curve on SWE-chat sessions. Cached; safe to rerun."""
import json, os, sys, re, concurrent.futures as cf
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import llm, build, label as L

HERE = os.path.dirname(os.path.abspath(__file__))
D = os.path.join(HERE, "data")
GEMMA, QWEN, DEEP = L.CHEAP
HAIKU, LUNA = L.REFS

# ---------------- SWE-chat sessions ----------------
def swe_sessions():
    path = os.path.join(D, "swe_sessions.jsonl")
    if os.path.exists(path):
        return [json.loads(l) for l in open(path)]
    picked = {x["session_id"]: x for x in json.load(open(os.path.join(D, "swe", "picked.json")))}
    out = []
    for sid, meta in picked.items():
        p = os.path.join(D, "swe", "transcripts", sid + ".jsonl")
        if not os.path.exists(p): continue
        r = build.finish(sid, "swechat", build.claude_code_raw(p), True, True)
        if r:
            r["swe"] = {k: meta.get(k) for k in ("user_persona", "session_success", "prompt_count", "tool_call_count")}
            out.append(r)
    with open(path, "w") as f:
        for r in out: f.write(json.dumps(r) + "\n")
    return out


# ---------------- (A) codebook v2 ----------------
V2_SYS = """You analyse how a person works with an AI assistant (chat assistant or coding agent) in ONE session.
Base every answer on evidence in the session. Turn numbers refer to the [turn N] markers.
Return ONLY a JSON object with exactly these keys:
{
 "collab_shares": {"directive": int, "feedback_loop": int, "task_iteration": int, "learning": int, "validation": int},
 "handed_over_upfront": true or false,
 "n_corrections": int,
 "n_feedback_relays": int,
 "n_refinements": int,
 "n_understanding_questions": int,
 "outcome": one of ["completed_confirmed","completed_unconfirmed","partial","failed_or_abandoned","unclear"],
 "outcome_evidence_turn": int or null,
 "reexplained_turns": [int, ...]
}
Definitions:
- collab_shares: percentages (sum 100) of the session's user turns that fit each pattern:
  directive = hands over work to be done with little steering; feedback_loop = relays errors, results or state back;
  task_iteration = steers, corrects or refines the assistant's output; learning = asks to understand something;
  validation = asks the assistant to check or improve the user's own work.
- handed_over_upfront: the first user turn already states a complete task AND later user turns are mostly approvals, continuations or relays (not new requirements).
- n_corrections: user turns saying the assistant was wrong, misunderstood, or did something unwanted.
- n_feedback_relays: user turns reporting errors, test output, results or state back.
- n_refinements: user turns asking to adjust the assistant's previous output without saying it was wrong.
- n_understanding_questions: user turns asking a question in order to understand something.
- outcome: completed_confirmed = the user explicitly confirms it works or is done; completed_unconfirmed = the assistant reports completion and the user does not object or moves on;
  partial = some but not all of what was asked got done; failed_or_abandoned = the session ends with the problem unresolved or the user gives up; unclear = cannot tell.
  outcome_evidence_turn = the turn that best supports the outcome (null if unclear).
- reexplained_turns: user turns that restate information the user had ALREADY given earlier in this session (same facts or instructions again). Empty list if none."""


def a_jobs(sessions):
    jobs = []
    for s in sessions:
        for m in (HAIKU, LUNA):
            jobs.append((m, V2_SYS, "SESSION:\n\n" + s["C3"]))
            jobs.append((m, L.SESSION_SYS, "SESSION:\n\n" + s["C3"]))  # v1 at C3 for the same comparison
    return jobs


# ---------------- (B) per-turn labels vs SWE-chat ----------------
TURN_SYS = """You label ONE user prompt sent to an AI coding agent. Context before the prompt may be given.
Return ONLY JSON: {"intent": one of ["create","refactor","debug","understand","connect","git","test","other"],
 "pushback": one of ["correction","rejection","failure_report","none"]}
intent: create = write new code or features; refactor = restructure or clean up existing code; debug = find or fix a bug;
understand = explain or explore code or concepts; connect = set up, configure or integrate tools/services; git = version-control operations;
test = write or run tests; other = anything else.
pushback: correction = says the agent did something wrong and how to fix it; rejection = refuses or rejects the agent's action or proposal;
failure_report = reports that something the agent did fails or errors; none = no pushback."""


def norm_txt(t):
    return re.sub(r"\s+", " ", (t or "")).strip()[:120].lower()


def aligned_turns():
    """Match our parsed human turns to SWE-chat's labelled prompt rows by text prefix."""
    rows = json.load(open(os.path.join(D, "swe", "prompt_labels.json")))
    by = {}
    for r in rows:
        by.setdefault(r["session_id"], []).append(r)
    out = []
    for s in swe_sessions():
        lab = {norm_txt(r["content"]): r for r in by.get(s["id"], []) if r.get("content")}
        real = [t for t in s["turns"] if not t["injected"]]
        for i, t in enumerate(real):
            key = norm_txt(t["user"])
            r = lab.get(key) or next((v for k, v in lab.items() if k[:60] and k[:60] == key[:60]), None)
            if r:
                out.append({"sid": s["id"], "i": i, "intent": r["prompt_intent"], "pushback": r["prompt_pushback"], "real": real})
    return out


def turn_ctx(real, i, layer):
    t = real[i]; p = real[i - 1] if i > 0 else None
    parts = []
    if layer >= 4 and i > 1:
        parts.append(f"two turns earlier, user said: {real[i-2]['user'][:300]}")
    if layer >= 4 and p:
        parts.append(f"previous user prompt: {p['user'][:400]}")
    if layer >= 3 and p:
        if p["activity"]: parts.append(f"agent activity after previous prompt: {p['activity']}")
        if p["errors"]: parts.append(f"tool errors: {' | '.join(p['errors'])[:300]}")
        if p["final"]: parts.append(f"agent's last reply: {p['final'][:500]}")
    parts.append(f"PROMPT: {t['user'][:2000]}")
    return "\n".join(parts)


def b_jobs():
    jobs = []
    for a in aligned_turns():
        for layer in (1, 3, 4):
            for m in (GEMMA, DEEP):
                jobs.append((m, TURN_SYS, turn_ctx(a["real"], a["i"], layer)))
    return jobs


# ---------------- (C) context curve on SWE-chat (v1 labels) ----------------
def c_jobs():
    jobs = []
    for s in swe_sessions():
        for c in ("C1", "C3", "C6"):
            for m in (GEMMA, DEEP):
                jobs.append((m, L.SESSION_SYS, "SESSION:\n\n" + s[c]))
        if s["n_injected"]:
            for m in (GEMMA, DEEP):
                jobs.append((m, L.SESSION_SYS, "SESSION:\n\n" + s["C3H"]))
        for m in (HAIKU, LUNA):
            jobs.append((m, L.SESSION_SYS, "SESSION:\n\n" + s["C6"]))
    return jobs


def run(jobs, tag):
    with cf.ThreadPoolExecutor(12) as ex:
        res = list(ex.map(lambda j: llm.call(*j), jobs))
    print(f"{tag}: {len(jobs)} calls, {sum(1 for r in res if r.get('labels') is None)} failed, spent ${llm.spent():.3f}")


if __name__ == "__main__":
    sw = swe_sessions()
    print(f"SWE-chat sessions parsed: {len(sw)}; aligned labelled turns: {len(aligned_turns())}")
    what = sys.argv[1:] or ["A", "B", "C"]
    if "A" in what: run(a_jobs(L.S + sw), "A codebook v2")
    if "B" in what: run(b_jobs(), "B per-turn vs SWE-chat")
    if "C" in what: run(c_jobs(), "C context curve on SWE-chat")
