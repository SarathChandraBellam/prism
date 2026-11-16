"""Transformer: the round 4 lake -> spans that follow docs/trace-schema.md, plus a conformance report.

    python3 conform.py          # writes data/lake_otel.jsonl and data/conformance.json

ADR 0003 says Prism reads only OpenTelemetry GenAI traces. The research lake predates the schema document and uses some
names of its own. This is the first transformer. It renames what has a standard name, restructures content into
messages, moves the platform to the resource, and drops what the conventions cannot express. Every change is counted,
so the report says what the schema carries and what it does not. Standard library only. No model.
"""
import collections, json, os, re

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
SRC = os.path.join(os.path.dirname(HERE), "cross-platform", "data", "lake.jsonl")
D = os.path.join(HERE, "data")
os.makedirs(D, exist_ok=True)

KIND = {"invoke_agent": "INTERNAL", "chat": "CLIENT", "execute_tool": "INTERNAL"}
FINISH = {"tool_calls": "tool_call", "stop": "stop", "length": "length", "content_filter": "content_filter", "error": "error"}
# what a chat span must carry (Required in the conventions), and what the analyses read when it is there
REQUIRED = {"invoke_agent": ["gen_ai.operation.name"], "chat": ["gen_ai.operation.name", "gen_ai.provider.name"],
            "execute_tool": ["gen_ai.operation.name", "gen_ai.tool.name"]}


def standard_names():
    """Every dotted name in backticks in docs/trace-schema.md. The schema document is the allow-list."""
    text = open(os.path.join(ROOT, "docs", "trace-schema.md")).read()
    names, patterns = set(), []
    for tok in re.findall(r"`([a-z0-9_]+(?:\.[a-z0-9_{},*]+)+)`", text):
        if "{" in tok or "*" in tok:
            rx = re.escape(tok).replace(r"\*", r"[a-z0-9_.]+")
            rx = re.sub(r"\\\{([^}]*)\\\}", lambda m: "(" + "|".join(m.group(1).replace("\\", "").split(",")) + ")", rx)
            patterns.append(re.compile("^" + rx + "$"))
        else:
            names.add(tok)
    return names, patterns


def text_part(t): return {"type": "text", "content": t}


def convert(s, log):
    a = dict(s["attributes"]); op = a["gen_ai.operation.name"]
    out = {}

    def move(old, new=None, when=lambda v: True):
        if old not in a: return
        v = a.pop(old)
        if new and when(v):
            out[new] = v; log["renamed"][f"{old} -> {new}"] += 1
        elif new is None:
            log["dropped"][old] += 1

    platform = a.pop("platform"); log["moved_to_resource"]["platform -> resource service.name"] += 1
    for k in ("gen_ai.operation.name", "gen_ai.conversation.id", "gen_ai.agent.name", "gen_ai.provider.name", "gen_ai.request.model",
              "gen_ai.response.model", "gen_ai.usage.input_tokens", "gen_ai.usage.output_tokens", "gen_ai.tool.name",
              "gen_ai.tool.call.arguments", "gen_ai.tool.call.result", "error.type", "user.id"):
        if k in a:
            v = a.pop(k)
            if v is not None: out[k] = v
    move("gen_ai.usage.cached_tokens", "gen_ai.usage.cache_read.input_tokens", when=bool)
    move("gen_ai.usage.reasoning_tokens", "gen_ai.usage.reasoning.output_tokens", when=bool)
    move("gen_ai.usage.cost")            # no cost attribute in the conventions: derive it from tokens and a price table
    move("http.status_code")             # error.type already carries the failure class
    move("session.turn_index")           # derivable: order of the root spans of one conversation by start time
    move("mcp.server.name")              # the conventions have no name for a local MCP server

    fr = a.pop("gen_ai.response.finish_reasons", None)
    if fr:
        out["gen_ai.response.finish_reasons"] = [FINISH.get(x, x) for x in fr]
        if any(x not in FINISH.values() for x in fr): log["renamed"]["finish reason tool_calls -> tool_call"] += 1

    if "gen_ai.input.text" in a:
        t = a.pop("gen_ai.input.text")
        out["gen_ai.input.messages"] = [{"role": "user", "parts": [text_part(t)]}]
        log["restructured"]["gen_ai.input.text -> gen_ai.input.messages"] += 1
    txt, calls = a.pop("gen_ai.output.text", None), a.pop("gen_ai.output.tool_calls", None)
    if txt or calls:
        parts = ([text_part(txt)] if txt else []) + [{"type": "tool_call", "name": n} for n in (calls or [])]
        reason = (out.get("gen_ai.response.finish_reasons") or [None])[0]
        if reason is None:
            reason = "tool_call" if calls else "stop"; log["inferred"]["finish_reason of the output message"] += 1
        out["gen_ai.output.messages"] = [{"role": "assistant", "parts": parts, "finish_reason": reason}]
        log["restructured"]["gen_ai.output.text (+ tool_calls) -> gen_ai.output.messages"] += 1

    name = s["name"]
    if op == "execute_tool":
        tool = out["gen_ai.tool.name"]
        if tool == "load_skill":
            try: skill = json.loads(out.get("gen_ai.tool.call.arguments") or "{}").get("name")
            except ValueError: skill = None
            if skill:
                out["gen_ai.skill.name"] = skill; name = f"execute_tool load_skill {skill}"
                log["inferred"]["gen_ai.skill.name from the load_skill arguments"] += 1
        elif "__" in tool:
            out["mcp.method.name"] = "tools/call"; log["inferred"]["mcp.method.name from the tool-name prefix"] += 1
    for k in a: log["unmapped"][k] += 1
    return {"trace_id": s["trace_id"], "span_id": s["span_id"], "parent_span_id": s["parent_span_id"], "name": name, "kind": KIND[op],
            "start_time": s["start_time"], "end_time": s["end_time"], "status": {"code": "ERROR" if s["status"] == "error" else "OK"},
            "resource": {"service.name": platform}, "attributes": out}


def main():
    names, patterns = standard_names()
    ok = lambda k: k in names or any(p.match(k) for p in patterns)
    log = collections.defaultdict(collections.Counter)
    spans = [convert(json.loads(l), log) for l in open(SRC)]
    spans.sort(key=lambda s: (s["start_time"], s["trace_id"], s["parent_span_id"] or "", s["span_id"]))
    with open(os.path.join(D, "lake_otel.jsonl"), "w") as f:
        for s in spans: f.write(json.dumps(s, sort_keys=True) + "\n")
    non_standard, missing, n = collections.Counter(), collections.defaultdict(collections.Counter), collections.Counter()
    for s in spans:
        a, p = s["attributes"], s["resource"]["service.name"]; op = a["gen_ai.operation.name"]; n[(p, op)] += 1
        for k in list(a) + list(s["resource"]):
            if not ok(k): non_standard[k] += 1
        for k in REQUIRED[op]:
            if k not in a: missing[f"{p} {op}"][k] += 1
    rep = {"spans": len(spans), "spans_by_platform_and_type": {f"{p} {o}": v for (p, o), v in sorted(n.items())},
           "standard_names_in_schema_doc": len(names), **{k: dict(sorted(v.items())) for k, v in sorted(log.items())},
           "non_standard_after_conversion": dict(non_standard), "required_missing": {k: dict(v) for k, v in sorted(missing.items())}}
    json.dump(rep, open(os.path.join(D, "conformance.json"), "w"), indent=1, sort_keys=True)
    print(json.dumps(rep, indent=1, sort_keys=True))
    assert not non_standard and not log.get("unmapped"), "a non-standard name is left"


if __name__ == "__main__":
    main()
