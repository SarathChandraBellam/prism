"""Run all labelling jobs for the context study (cached; safe to rerun)."""
import json, os, sys, random, concurrent.futures as cf
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import llm

HERE = os.path.dirname(os.path.abspath(__file__))
S = [json.loads(l) for l in open(os.path.join(HERE, "data", "study_sessions.jsonl"))]
random.seed(11)

CHEAP = ["google/gemma-4-26b-a4b-it", "qwen/qwen3.7-flash", "deepseek/deepseek-v4.1-flash"]
REFS = ["anthropic/claude-haiku-5.5", "openai/gpt-6-luna"]
CONDS = ["C1", "C2", "C3", "C4", "C6"]

SESSION_SYS = """You analyse how a person works with an AI assistant (a chat assistant or a coding agent). You label ONE session.
Return ONLY a JSON object with exactly these keys:
{
 "topics": [up to 3 short lowercase noun phrases],
 "domain": one of ["software_engineering","data_ml","writing","research","design_ux","devops_infra","business_product","education","personal","creative","other"],
 "task_type": one of ["build_feature","debug_fix","refactor","explain_learn","plan_design","research_compare","write_content","config_setup","review","translate","other"],
 "collaboration_pattern": one of ["directive","feedback_loop","task_iteration","learning","validation"],
 "outcome": one of ["resolved","partial","abandoned","ongoing","unclear"],
 "context_reexplained": true or false,
 "summary": one sentence, no names, secrets or identifiers
}
collaboration_pattern (single most representative for the whole session):
- directive: the user hands over the task with minimal back-and-forth.
- feedback_loop: completion is driven mainly by relaying environment feedback (errors, test output, results) back to the assistant.
- task_iteration: user and assistant refine the work together over several turns; the user steers and edits.
- learning: the user mainly seeks explanation or understanding, not a finished artifact.
- validation: the user mainly asks the assistant to check, review or improve the user's own work.
context_reexplained: true if the user had to repeat context the assistant already had or should have known.
The session may be shown in a reduced form (only some parts of each turn). Label it as well as you can from what is shown."""

ACTS = ["instruct", "plan_together", "relay_feedback", "correct", "refine", "ask_explain", "request_review", "approve_continue", "reexplain", "unclear"]
ACT_SYS = """You label each USER turn in a session between a person and an AI assistant with ONE interaction act.
- instruct: gives a new task or concrete direction to carry out
- plan_together: brainstorms, ideates or plans with the assistant without asking for the work to be carried out yet
- relay_feedback: reports results, errors or state back ("still failing", "try now", pastes an error)
- correct: says the assistant got something wrong or misunderstood
- refine: asks to adjust the assistant's previous output ("shorter", "also add X")
- ask_explain: asks a question to understand something
- request_review: asks the assistant to check or review work
- approve_continue: approves or lets the assistant carry on ("yes", "go ahead")
- reexplain: repeats context the assistant already had
- unclear: cannot tell from the context given (prefer this over guessing)
Return ONLY JSON: {"turns":[{"i":<turn number>,"act":"<act>","confidence":<0..1>}]} with exactly one entry per USER turn shown."""

FOLD_SYS = SESSION_SYS.replace("You label ONE session.", "You maintain a running label record for ONE session. You receive the current record (from earlier turns) and the NEW turns; return the updated record describing the whole session so far.")


def session_jobs():
    jobs = []
    for s in S:
        conds = list(CONDS) + (["C3H"] if s["n_injected"] and s["has_tools"] else [])
        for c in conds:
            for m in CHEAP + REFS[:1]:
                jobs.append(("sess", s["id"], c, m, SESSION_SYS, "SESSION:\n\n" + s[c]))
        jobs.append(("sess", s["id"], "C6", REFS[1], SESSION_SYS, "SESSION:\n\n" + s["C6"]))
        jobs.append(("sess", s["id"], "C3", REFS[1], SESSION_SYS, "SESSION:\n\n" + s["C3"]))
    return jobs


def turn_block(s, layer):
    real = [t for t in s["turns"] if not t["injected"]]
    parts = []
    for i, t in enumerate(real, 1):
        p = real[i - 2] if i > 1 else None
        L = [f"--- TURN {i}"]
        if layer >= 4 and p: L.append(f"previous user turn: {p['user'][:400]}")
        if layer >= 2 and p and p["activity"]: L.append(f"agent activity before this turn: {p['activity']}")
        if layer >= 2 and p and p["errors"]: L.append(f"errors before this turn: {' | '.join(p['errors'])[:300]}")
        if layer >= 3 and p and p["final"]: L.append(f"previous assistant reply: {p['final'][:500]}")
        L.append(f"USER: {t['user'][:1500]}")
        parts.append("\n".join(L))
    return len(real), "\n\n".join(parts)


def turn_sessions():
    by = {}
    for s in S:
        n = sum(1 for t in s["turns"] if not t["injected"])
        if 4 <= n <= 30: by.setdefault(s["source"], []).append(s)
    pick = []
    for src, k in (("own", 10), ("fable", 6), ("dataclaw", 15), ("wildchat", 15)):
        g = by.get(src, []); random.shuffle(g); pick += g[:k]
    return pick


def turn_jobs():
    jobs = []
    for s in turn_sessions():
        for L in (1, 2, 3, 4):
            n, txt = turn_block(s, L)
            for m in CHEAP[:2]:
                jobs.append(("turn", s["id"], f"L{L}", m, ACT_SYS, txt))
        n, txt = turn_block(s, 4)
        for m in REFS:
            jobs.append(("turn", s["id"], "L4", m, ACT_SYS, txt))
    return jobs


def fold_sessions():
    g = [s for s in S if s["source"] != "wildchat" and 6 <= sum(1 for t in s["turns"] if not t["injected"]) <= 25]
    random.shuffle(g)
    return g[:25]


def turn_text(t, i):
    L = [f"[turn {i}] USER: {t['user'][:1500]}"]
    if t["activity"]: L.append(t["activity"])
    if t["final"]: L.append(f"ASSISTANT: {t['final'][:600]}")
    return "\n".join(L)


def run_fold(model, s):
    real = [t for t in s["turns"] if not t["injected"]]
    r = llm.call(model, SESSION_SYS, "SESSION:\n\n" + turn_text(real[0], 1))
    rec = r.get("labels"); steps = [rec]
    for i, t in enumerate(real[1:], 2):
        if rec is None: break
        r = llm.call(model, FOLD_SYS, f"CURRENT RECORD:\n{json.dumps(rec)}\n\nNEW TURNS:\n{turn_text(t, i)}")
        if r.get("labels"): rec = r["labels"]
        steps.append(rec)
    return steps


def run(jobs):
    def go(j):
        r = llm.call(j[3], j[4], j[5])
        return j[:4], r
    out = []
    with cf.ThreadPoolExecutor(12) as ex:
        for k, r in ex.map(go, jobs):
            out.append((k, r))
    bad = sum(1 for _, r in out if r.get("labels") is None)
    return out, bad


if __name__ == "__main__":
    what = sys.argv[1:] or ["sess", "turn", "fold"]
    if "sess" in what:
        j = session_jobs(); o, bad = run(j); print(f"session jobs {len(j)} failed {bad} spent ${llm.spent():.3f}")
    if "turn" in what:
        j = turn_jobs(); o, bad = run(j); print(f"turn jobs {len(j)} failed {bad} spent ${llm.spent():.3f}")
    if "fold" in what:
        fs = fold_sessions()
        with cf.ThreadPoolExecutor(10) as ex:
            res = list(ex.map(lambda s: run_fold(CHEAP[1], s), fs))
        print(f"fold sessions {len(fs)} steps {sum(len(x) for x in res)} spent ${llm.spent():.3f}")
