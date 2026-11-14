"""Record the chat-only platform "Chatly": no tools, no skills, one model request per user turn.

    python3 chatly.py          # all 32 scripted sessions; resumable per turn; stops on a daily quota error

Every request is a record, failed attempts included (written to run/chatly/<session>.json).
The tally of requests is kept in run/requests.json. Model: openrouter/free only.
"""
import json, os, sys, time
from common import *
import agent

OUT = os.path.join(RUN, "chatly"); os.makedirs(OUT, exist_ok=True)
TALLY = os.path.join(RUN, "requests.json")
TEXT = {"num", "has", "any", "not"}
SYSTEM = """You are Chatly, a general-purpose chat assistant for the staff of Kettle & Crumb, an online shop for coffee gear.
You are talking to {role}. Today is 2026-11-13 (Friday). Amounts are in GBP.

You have no access to company systems: you cannot look up orders, customers, stock, tickets or files, and you cannot
change anything. Answer from what the user tells you and from general knowledge, and say plainly when you would need
company data. Be brief."""


class Quota(Exception): pass


def tally(kind, n=1):
    t = json.load(open(TALLY)) if os.path.exists(TALLY) else {}
    t[kind] = t.get(kind, 0) + n
    json.dump(t, open(TALLY, "w"))


def request(messages):
    """One HTTP request. Returns an attempt record."""
    t0 = time.time()
    r, err, http = agent.post({"model": agent.MODEL, "messages": messages, "max_tokens": 1500, "temperature": 0.2, "usage": {"include": True}})
    tally("chatly")
    ms = int((time.time() - t0) * 1000)
    rec = {"duration_ms": ms, "http": http, "error": err, "model": None, "tokens_in": None, "tokens_out": None, "text": "", "cost": None}
    if r:
        m, u = r["choices"][0]["message"], r.get("usage") or {}
        rec.update(model=r.get("model"), tokens_in=u.get("prompt_tokens"), tokens_out=u.get("completion_tokens"),
                   text=(m.get("content") or ""), cost=u.get("cost"), reasoning=(u.get("completion_tokens_details") or {}).get("reasoning_tokens"))
        if not rec["text"].strip(): rec["error"] = "empty_response"
    else:
        msg = agent._err_text.pop(__import__("threading").get_ident(), "")
        rec["error_message"] = msg
        if http == 429 and ("day" in msg.lower()): raise Quota(msg)
    return rec


def run(sc):
    path = os.path.join(OUT, sc["session_id"] + ".json")
    rec = json.load(open(path)) if os.path.exists(path) else {"session_id": sc["session_id"], "turns": []}
    if len(rec["turns"]) == len(sc["turns"]): return
    system = SYSTEM.format(role=sc["role"])
    msgs = [{"role": "system", "content": system}]
    for t, rt in zip(sc["turns"], rec["turns"]):
        msgs += [{"role": "user", "content": t["text"]}, {"role": "assistant", "content": rt["reply"] or "(no answer)"}]
    for i in range(len(rec["turns"]), len(sc["turns"])):
        t = sc["turns"][i]
        msgs.append({"role": "user", "content": t["text"]})
        attempts, reply = [], ""
        for a in range(3):
            r = request(msgs); attempts.append(r)
            if not r["error"]: reply = r["text"]; break
            time.sleep(min(4 * (a + 1), 15) if r["error"] in ("http_429", "provider_429") else 2)
        msgs.append({"role": "assistant", "content": reply or "(no answer)"})
        checks = [bool(agent.check(c, reply, None)) if c[0] in TEXT else False for c in t["checks"]]
        rec["turns"].append({"turn_index": i + 1, "attempts": attempts, "reply": reply, "answered": bool(reply), "checks": checks})
        json.dump(rec, open(path + ".tmp", "w")); os.replace(path + ".tmp", path)
    print(sc["session_id"], "turns", len(rec["turns"]), "requests", sum(len(t["attempts"]) for t in rec["turns"]),
          "passed", sum(sum(t["checks"]) for t in rec["turns"]), "/", sum(len(t["checks"]) for t in rec["turns"]), flush=True)


if __name__ == "__main__":
    scs = scenarios()
    try:
        for sid in sorted(scs):
            if not sys.argv[1:] or sid in sys.argv[1:]: run(scs[sid])
    except Quota as e:
        print("DAILY QUOTA REACHED, stopping:", str(e)[:300]); sys.exit(2)
    print("done", json.load(open(TALLY)))
