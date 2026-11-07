"""Run extraction approaches over parsed sessions via OpenRouter. Results are cached per call."""
import json, os, sys, hashlib, time, re, ssl, urllib.request, concurrent.futures as cf
SSL_CTX = ssl.create_default_context(cafile='/etc/ssl/cert.pem')

HERE = os.path.dirname(os.path.abspath(__file__))
CACHE = os.path.join(HERE, "cache"); os.makedirs(CACHE, exist_ok=True)
KEY = os.environ["OPEN_ROUTER_KEY"]
BUDGET_USD = float(os.environ.get("BUDGET_USD", "1.5"))

SCHEMA = """Return ONLY a JSON object with exactly these keys:
{
 "topics": [up to 3 short lowercase noun phrases],
 "domain": one of ["software_engineering","data_ml","writing","research","design_ux","devops_infra","business_product","personal","other"],
 "task_type": one of ["build_feature","debug_fix","refactor","explain_learn","plan_design","research_compare","write_docs","config_setup","review","other"],
 "collaboration_pattern": one of ["directive","feedback_loop","task_iteration","learning","validation"],
 "outcome": one of ["resolved","partial","abandoned","ongoing","unclear"],
 "context_reexplained": true or false,
 "summary": one sentence, no names, secrets or identifiers
}
Definitions for collaboration_pattern (pick the single most representative across the whole session):
- directive: user hands over the whole task with minimal back-and-forth.
- feedback_loop: task completion mainly driven by relaying environment feedback (errors, test output) back to the assistant.
- task_iteration: user and assistant refine the output together over several turns; user steers and edits.
- learning: user mainly seeks explanation or understanding, not a finished artifact.
- validation: user mainly asks the assistant to check, review or improve their own work.
context_reexplained: true if the user had to repeat context the assistant already had or should have known."""

SYS = "You analyse how a person works with an AI coding/chat assistant. You label one session. " + SCHEMA

FOLD_SYS = ("You maintain a running label record for one session of a person working with an AI assistant. "
            "You receive the current record (built from earlier traces) and the NEW traces. Update the record so it "
            "describes the WHOLE session so far. Keep what is still true, revise what the new traces change. " + SCHEMA)


def call(model, system, user, tag):
    h = hashlib.sha256(json.dumps([model, system, user]).encode()).hexdigest()[:24]
    path = os.path.join(CACHE, f"{h}.json")
    if os.path.exists(path):
        return json.load(open(path))
    body = {"model": model, "temperature": 0, "max_tokens": 6000, "response_format": {"type": "json_object"},
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
            "reasoning": {"enabled": False}, "usage": {"include": True},
            "provider": {"data_collection": "deny"}}
    for attempt in range(4):
        try:
            req = urllib.request.Request("https://openrouter.ai/api/v1/chat/completions", data=json.dumps(body).encode(),
                                         headers={"Authorization": f"Bearer {KEY}", "Content-Type": "application/json"})
            r = json.load(urllib.request.urlopen(req, timeout=300, context=SSL_CTX))
            if "error" in r:
                raise RuntimeError(r["error"])
            txt = r["choices"][0]["message"].get("content") or ""
            m = re.search(r"\{[\s\S]*\}", txt)
            out = {"tag": tag, "model": model, "raw": txt, "labels": json.loads(m.group(0)) if m else None,
                   "usage": r.get("usage", {})}
            if out["labels"] is not None:
                json.dump(out, open(path, "w"))
            return out
        except Exception as e:
            err = str(e)
            if hasattr(e, "read"):
                try: err += " " + e.read().decode()[:400]
                except Exception: pass
            if "reasoning" in err.lower() and "reasoning" in body:
                body.pop("reasoning")
            if "response_format" in err.lower() and "response_format" in body:
                body.pop("response_format")
            time.sleep(2 * (attempt + 1))
    return {"tag": tag, "model": model, "error": err, "labels": None, "usage": {}}


def spent():
    tot = 0.0
    for f in os.listdir(CACHE):
        try: tot += float(json.load(open(os.path.join(CACHE, f))).get("usage", {}).get("cost") or 0)
        except Exception: pass
    return tot


def jobs_for(model, approach, s):
    sid = s["session_id"]
    if approach in ("full", "chat", "chat_err"):
        return [(model, SYS, f"SESSION ({approach} view):\n\n{s[approach]}", f"{approach}|{sid}")]
    if approach == "per_trace":
        return [(model, SYS, f"SESSION (single trace only):\n\n{t}", f"per_trace|{sid}|{i}") for i, t in enumerate(s["per_trace"])]
    raise ValueError(approach)


def run_parallel(jobs, workers=8):
    with cf.ThreadPoolExecutor(workers) as ex:
        return list(ex.map(lambda j: call(*j), jobs))


def run_fold(model, s):
    """Sequential fold: trace 1 -> record, then record + next trace -> record ... Returns list of records per step."""
    recs = []
    first = call(model, SYS, f"SESSION (chat_err view):\n\n{s['per_trace'][0]}", f"fold|{s['session_id']}|0")
    rec = first["labels"]; recs.append(first)
    for i, t in enumerate(s["per_trace"][1:], 1):
        if rec is None:
            break
        r = call(model, FOLD_SYS, f"CURRENT RECORD:\n{json.dumps(rec)}\n\nNEW TRACES:\n{t}", f"fold|{s['session_id']}|{i}")
        if r["labels"]:
            rec = r["labels"]
        recs.append(r)
    return recs


if __name__ == "__main__":
    sessions = [json.loads(l) for l in open(os.path.join(HERE, "sessions.jsonl"))]
    plan = json.loads(sys.argv[1])  # {"models":[...], "approaches":[...], "fold":bool}
    print(f"spent so far ${spent():.4f}")
    jobs = []
    for m in plan["models"]:
        for a in plan.get("approaches", []):
            for s in sessions:
                jobs += jobs_for(m, a, s)
    res = run_parallel(jobs) if jobs else []
    errs = [r for r in res if r.get("labels") is None]
    print(f"{len(res)} calls, {len(errs)} failed; spent ${spent():.4f}")
    for e in errs[:5]:
        print("ERR", e["model"], e["tag"], (e.get("error") or e.get("raw", ""))[:300])
    if plan.get("fold") and spent() < BUDGET_USD:
        for m in plan["models"]:
            with cf.ThreadPoolExecutor(8) as ex:
                out = list(ex.map(lambda s: run_fold(m, s), [s for s in sessions if len(s["per_trace"]) > 1]))
            print(f"fold {m}: {sum(len(o) for o in out)} steps; spent ${spent():.4f}")
