"""Re-apply the current checks in scenarios.py to stored traces.

Checks on the reply text are re-evaluated from the stored reply. Checks on state
(database rows, files) keep the result recorded at run time. Turns whose list of
checks changed shape are re-evaluated on text checks only.

    python3 rescore.py
"""
import json, os
import agent, scenarios

D = os.path.join(agent.HERE, "data")
TEXT = {"num", "has", "any", "not"}
sc = {s["session_id"]: s for s in scenarios.sessions()}
json.dump(list(sc.values()), open(os.path.join(D, "scenarios.json"), "w"), indent=1)
for name in ("traces.jsonl", "traces-noskill.jsonl"):
    path = os.path.join(D, name)
    if not os.path.exists(path): continue
    out, changed = [], 0
    for line in open(path):
        s = json.loads(line); a = s["attributes"]
        if a["gen_ai.operation.name"] == "invoke_agent":
            checks = sc[a["gen_ai.conversation.id"]]["turns"][a["prism.turn_index"] - 1]["checks"]
            old = {d["check"]: d["ok"] for d in a["eval.detail"] if d["check"] not in TEXT}
            detail = [{"check": c[0], "ok": bool(agent.check(c, a["gen_ai.output.text"], None)) if c[0] in TEXT else old[c[0]]} for c in checks]
            changed += detail != a["eval.detail"]
            a["eval.detail"], a["eval.checks"], a["eval.passed"] = detail, len(detail), sum(d["ok"] for d in detail)
        out.append(json.dumps(s))
    open(path, "w").write("\n".join(out) + "\n")
    print(name, "turns rescored with a different result:", changed)
