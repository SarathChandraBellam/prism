"""Three adapters: platform exports -> one common span shape (OpenTelemetry GenAI, as in round 3) -> data/lake.jsonl.

    python3 adapters.py          # writes data/lake.jsonl and data/fidelity.json

Identity is resolved through data/directory.json only (handle, email or employee id). The adapters read the exports
and nothing else.
"""
import collections, datetime as dt, json
from common import *

DIR = json.load(open(os.path.join(D, "directory.json")))["users"]
BY = {"atlas": {u["handle"]: u["handle"] for u in DIR}, "beacon": {u["email"]: u["handle"] for u in DIR},
      "chatly": {u["employee_id"]: u["handle"] for u in DIR}}
ms_iso = lambda ms: dt.datetime.fromtimestamp(ms / 1000, dt.timezone.utc).isoformat(timespec="milliseconds")
dur = lambda a, b: int((dt.datetime.fromisoformat(b) - dt.datetime.fromisoformat(a)).total_seconds() * 1000)


def span(trace, parent, sid, name, start, end, status, attrs):
    return {"trace_id": trace, "span_id": sid, "parent_span_id": parent, "name": name, "start_time": start, "end_time": end,
            "status": status, "duration_ms": dur(start, end), "attributes": attrs}


def atlas(path):
    """OTel GenAI JSONL. Nearly the target shape: resolve the user, add the platform, prefix the session id."""
    for s in jl(path):
        a = dict(s["attributes"]); a["platform"] = "atlas"
        a["gen_ai.conversation.id"] = "atlas:" + a["gen_ai.conversation.id"]
        if "user.id" in a: a["user.id"] = BY["atlas"][a["user.id"]]
        yield {**s, "attributes": a}


def beacon(path):
    """Run trees. Turn index = order of the chain runs in the thread; tool server = prefix of the tool name."""
    runs = jl(path)
    kids = collections.defaultdict(list)
    for r in runs:
        if r["parent_run_id"]: kids[r["parent_run_id"]].append(r)
    threads = collections.defaultdict(list)
    for r in runs:
        if r["run_type"] == "chain": threads[r["extra"]["metadata"]["thread_id"]].append(r)
    for th, chains in threads.items():
        chains.sort(key=lambda r: r["start_ms"])
        for i, r in enumerate(chains):
            user, conv = BY["beacon"][r["extra"]["metadata"]["user_email"]], "beacon:" + th
            ra = {"gen_ai.operation.name": "invoke_agent", "gen_ai.conversation.id": conv, "user.id": user, "platform": "beacon",
                  "session.turn_index": i + 1, "gen_ai.input.text": r["inputs"]["input"], "gen_ai.output.text": r["outputs"]["output"]}
            if r["error"]: ra["error.type"] = r["error"]
            yield span(r["id"], None, r["id"], "invoke_agent shop-assistant", ms_iso(r["start_ms"]), ms_iso(r["end_ms"]),
                       "error" if r["error"] else "ok", ra)
            for k in sorted(kids[r["id"]], key=lambda k: k["start_ms"]):
                a = {"gen_ai.conversation.id": conv, "platform": "beacon"}
                if k["run_type"] == "llm":
                    a.update({"gen_ai.operation.name": "chat", "gen_ai.request.model": k["name"], "gen_ai.response.model": k["extra"].get("model"),
                              "gen_ai.output.text": k["outputs"]["text"], "gen_ai.output.tool_calls": k["outputs"]["tool_calls"]})
                    u = k["extra"].get("usage")
                    if u: a["gen_ai.usage.input_tokens"], a["gen_ai.usage.output_tokens"] = u["prompt_tokens"], u["completion_tokens"]
                    name = "chat " + k["name"]
                else:
                    a.update({"gen_ai.operation.name": "execute_tool", "gen_ai.tool.name": k["name"], "mcp.server.name": k["name"].split("__")[0],
                              "gen_ai.tool.call.arguments": k["inputs"]["input"], "gen_ai.tool.call.result": k["outputs"]["output"]})
                    name = "execute_tool " + k["name"]
                if k["error"]: a["error.type"] = k["error"]
                yield span(r["id"], r["id"], k["id"], name, ms_iso(k["start_ms"]), ms_iso(k["end_ms"]), "error" if k["error"] else "ok", a)


def chatly(path):
    """Chat exports. One turn = a user message plus the assistant message that follows it. A user message without
    a reply is a turn with no answer; the export has no trace of the failed requests behind it."""
    for c in jl(path):
        user, conv, m = BY["chatly"][c["employee_id"]], "chatly:" + c["conversation_id"], c["messages"]
        turn = 0
        for i, u in enumerate(m):
            if u["role"] != "user": continue
            turn += 1
            rep = m[i + 1] if i + 1 < len(m) and m[i + 1]["role"] == "assistant" else None
            tid = f"{c['conversation_id']}-t{turn}"
            ra = {"gen_ai.operation.name": "invoke_agent", "gen_ai.conversation.id": conv, "user.id": user, "platform": "chatly",
                  "session.turn_index": turn, "gen_ai.input.text": u["content"], "gen_ai.output.text": rep["content"] if rep else ""}
            if not rep: ra["error.type"] = "no_reply_inferred"
            yield span(tid, None, tid, "invoke_agent chat", u["ts"], rep["ts"] if rep else u["ts"], "ok" if rep else "error", ra)
            if rep:
                a = {"gen_ai.operation.name": "chat", "gen_ai.conversation.id": conv, "platform": "chatly", "gen_ai.request.model": rep["model"],
                     "gen_ai.response.model": rep["model"], "gen_ai.usage.input_tokens": rep["usage"]["prompt_tokens"],
                     "gen_ai.usage.output_tokens": rep["usage"]["completion_tokens"], "gen_ai.output.text": rep["content"]}
                yield span(tid, tid, tid + "-c", "chat " + str(rep["model"]), u["ts"], rep["ts"], "ok", a)


ADAPTERS = {"atlas": atlas, "beacon": beacon, "chatly": chatly}


def counts_lake(spans):
    ops = lambda o: [s for s in spans if A(s)["gen_ai.operation.name"] == o]
    roots, chats, tools = ops("invoke_agent"), ops("chat"), ops("execute_tool")
    return {"sessions": len({A(s)["gen_ai.conversation.id"] for s in roots}), "turns": len(roots), "requests": len(chats),
            "failed_requests": sum(s["status"] == "error" for s in chats), "tool_calls": len(tools),
            "tool_errors": sum(s["status"] == "error" for s in tools),
            "tokens_in": sum(A(s).get("gen_ai.usage.input_tokens") or 0 for s in chats),
            "tokens_out": sum(A(s).get("gen_ai.usage.output_tokens") or 0 for s in chats)}


def counts_native(p):
    """Counted straight from the export format, without the adapter."""
    path = os.path.join(D, f"export_{p}.jsonl"); rows = jl(path)
    if p == "atlas":
        op = lambda o: [s for s in rows if A(s)["gen_ai.operation.name"] == o]
        ch, tl, ro = op("chat"), op("execute_tool"), op("invoke_agent")
        return {"sessions": len({A(s)["gen_ai.conversation.id"] for s in ro}), "turns": len(ro), "requests": len(ch),
                "failed_requests": sum(s["status"] == "error" for s in ch), "tool_calls": len(tl), "tool_errors": sum(s["status"] == "error" for s in tl),
                "tokens_in": sum(A(s).get("gen_ai.usage.input_tokens") or 0 for s in ch), "tokens_out": sum(A(s).get("gen_ai.usage.output_tokens") or 0 for s in ch)}
    if p == "beacon":
        t = lambda k: [r for r in rows if r["run_type"] == k]
        us = [r["extra"].get("usage") or {} for r in t("llm")]
        return {"sessions": len({r["extra"]["metadata"]["thread_id"] for r in t("chain")}), "turns": len(t("chain")), "requests": len(t("llm")),
                "failed_requests": sum(bool(r["error"]) for r in t("llm")), "tool_calls": len(t("tool")), "tool_errors": sum(bool(r["error"]) for r in t("tool")),
                "tokens_in": sum(u.get("prompt_tokens", 0) for u in us), "tokens_out": sum(u.get("completion_tokens", 0) for u in us)}
    asst = [m for c in rows for m in c["messages"] if m["role"] == "assistant"]
    return {"sessions": len(rows), "turns": sum(m["role"] == "user" for c in rows for m in c["messages"]), "requests": len(asst), "failed_requests": 0,
            "tool_calls": 0, "tool_errors": 0, "tokens_in": sum(m["usage"]["prompt_tokens"] for m in asst), "tokens_out": sum(m["usage"]["completion_tokens"] for m in asst)}


def main():
    lake, fid = [], {}
    truth = json.load(open(os.path.join(D, "truth.json")))
    for p in PLATFORMS:
        rows = list(ADAPTERS[p](os.path.join(D, f"export_{p}.jsonl")))
        lake += rows
        rec = collections.Counter()
        for t in truth["tasks"]:
            for s in t["sessions"]:
                if s["platform"] == p:
                    rec["sessions"] += 1
                    for k, v in s["counts"].items(): rec[k] += v
        fid[p] = {"recording": dict(rec), "export": counts_native(p), "lake": counts_lake(rows)}
    lake.sort(key=lambda s: (s["start_time"], s["span_id"]))
    with open(os.path.join(D, "lake.jsonl"), "w") as f:
        for s in lake: f.write(json.dumps(s, sort_keys=True) + "\n")
    json.dump(fid, open(os.path.join(D, "fidelity.json"), "w"), indent=1)
    keys = ["sessions", "turns", "requests", "failed_requests", "tool_calls", "tool_errors", "tokens_in", "tokens_out"]
    print("| Platform | Source | " + " | ".join(keys) + " |"); print("|" + "---|" * (len(keys) + 2))
    for p in PLATFORMS:
        for src in ("recording", "export", "lake"):
            print(f"| {p} | {src} | " + " | ".join(f"{fid[p][src].get(k, 0):,}" for k in keys) + " |")
    print("lake spans", len(lake))


if __name__ == "__main__":
    main()
