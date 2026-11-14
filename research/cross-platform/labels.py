"""Session labels per RECORDING (not per replayed session) with the round 3 prompt and compact view.

    python3 labels.py          # Beacon and Chatly: 1 draw per recording (64 calls, cached in cache/); Atlas: reused from round 3

Writes data/labels.json: {"<platform>:<script>": {"domain", "task_type", ...}}. Stops cleanly on a daily quota error and
can be rerun: finished labels are cached. Model: openrouter/free.
"""
import json, sys, threading
from common import *
import agent, prism
prism.CACHE = CACHE
TALLY = os.path.join(RUN, "requests.json")


class Quota(Exception): pass


_post = agent.post
def counted(body):
    r, err, http = _post(body)
    t = json.load(open(TALLY)) if os.path.exists(TALLY) else {}
    t["labels"] = t.get("labels", 0) + 1
    json.dump(t, open(TALLY, "w"))
    if http == 429 and "day" in agent._err_text.get(threading.get_ident(), "").lower():
        raise Quota(agent._err_text[threading.get_ident()])
    return r, err, http
agent.post = counted


def chatly_view(sid):
    r = json.load(open(os.path.join(RUN, "chatly", sid + ".json")))
    return {"turns": [({"attributes": {"prism.turn_index": t["turn_index"], "gen_ai.input.text": scenarios()[sid]["turns"][t["turn_index"] - 1]["text"],
                                        "gen_ai.output.text": t["reply"]}}, []) for t in r["turns"]]}


def main():
    out_path = os.path.join(D, "labels.json")
    out = json.load(open(out_path)) if os.path.exists(out_path) else {}
    old = json.load(open(os.path.join(AS, "data", "prism_labels.json")))["session"]
    for sid, v in old.items():
        lab = (v.get("a") or {}).get("labels") or (v.get("b") or {}).get("labels")
        if lab: out[f"atlas:{sid}"] = {**lab, "source": "round3"}
    sess, _ = prism.load()
    nos = {}
    spans = jl(os.path.join(AS, "data", "traces-noskill.jsonl"))
    import collections
    kids = collections.defaultdict(list)
    for s in spans:
        if s["parent_span_id"]: kids[s["trace_id"]].append(s)
    for s in spans:
        if s["parent_span_id"] is None:
            nos.setdefault(A(s)["gen_ai.conversation.id"], {"turns": []})["turns"].append((s, sorted(kids[s["trace_id"]], key=lambda k: k["start_time"])))
    for v in nos.values(): v["turns"].sort(key=lambda t: A(t[0])["prism.turn_index"])
    jobs = [(f"beacon:{sid}", prism.chat_view(nos[sid])) for sid in sorted(nos)] + [(f"chatly:{sid}", prism.chat_view(chatly_view(sid))) for sid in sorted(scenarios())]
    try:
        for key, view in jobs:
            if key in out: continue
            lab, model = prism.call(prism.SESSION_PROMPT, view, tag="a")
            if lab: out[key] = {**lab, "source": "round4", "model": model}
            json.dump(out, open(out_path, "w"), indent=1, sort_keys=True)
    except Quota as e:
        print("DAILY QUOTA REACHED:", str(e)[:200])
    json.dump(out, open(out_path, "w"), indent=1, sort_keys=True)
    miss = [k for k, _ in jobs if k not in out]
    print("labels", len(out), "pending", len(miss), miss)


if __name__ == "__main__":
    main()
