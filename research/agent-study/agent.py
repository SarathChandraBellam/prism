"""The study agent: an OpenRouter tool-calling loop with MCP servers and skills,
logging every turn as OpenTelemetry-GenAI-style spans (JSONL).

    python3 agent.py                 # run all sessions (resumable), 3 in parallel
    python3 agent.py M01 A02         # run selected sessions
    ARM=noskill python3 agent.py     # ablation: same agent without the skills (writes data/traces-noskill.jsonl)
    AGENT_MODEL=openrouter/free      # default; any OpenRouter model id works

Span tree per user turn (= one trace):
    invoke_agent                     root; user text, final reply, check results
      chat                           one per model request, including failed attempts
      execute_tool                   one per tool call (MCP tool or load_skill)
Standard library only. The API key is read from OPEN_ROUTER_KEY.
"""
import datetime as dt, json, os, re, shutil, sqlite3, ssl, sys, threading, time, urllib.request, uuid
from concurrent.futures import ThreadPoolExecutor
import scenarios, shop_mcp
from mcp_client import start_servers

HERE = os.path.dirname(os.path.abspath(__file__))
MODEL = os.environ.get("AGENT_MODEL", "openrouter/free")
KEY = os.environ.get("OPEN_ROUTER_KEY", "proxy-injected")
ARM = os.environ.get("ARM", "base")                       # "noskill" runs the ablation without skills
SUFFIX = "" if ARM == "base" else "-" + ARM
RUN = os.path.join(HERE, "run" + SUFFIX)
TRACES = os.path.join(HERE, "data", "traces" + SUFFIX)
MAX_STEPS = 8
MIN_GAP = float(os.environ.get("MIN_GAP_S", "3.2"))       # free models allow about 20 requests a minute
SSL_CTX = ssl.create_default_context()

SYSTEM = """You are the operations assistant of Kettle & Crumb, a three-person online shop for coffee gear.
You are talking to {role}. Today is {today} ({weekday}). Amounts are in GBP.

Use the tools to check facts before you answer. Tool names are prefixed with their server:
shop__ (orders, customers, products, tickets), filesystem__ (the workspace: docs/ holds policies, out/ is for
files you write; use relative paths), memory__ (a knowledge graph that persists notes).

{skills}Be brief. Answer the question that was asked."""


def load_skills():
    out = {}
    root = os.path.join(HERE, "skills")
    for name in sorted(os.listdir(root)):
        txt = open(os.path.join(root, name, "SKILL.md")).read()
        m = re.match(r"---\n(.*?)\n---\n(.*)", txt, re.S)
        meta = dict(l.split(": ", 1) for l in m.group(1).splitlines())
        out[meta["name"]] = {"description": meta["description"], "body": m.group(2).strip()}
    return out


SKILLS = load_skills()
_rate_lock, _last = threading.Lock(), [0.0]
_err_text = {}                                            # last provider error body per thread, copied into the span


def now():
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="milliseconds")


def sid():
    return uuid.uuid4().hex[:16]


def post(body):
    """One HTTP request. Returns (json or None, error_type or None, http_status)."""
    with _rate_lock:
        wait = _last[0] + MIN_GAP - time.time()
        if wait > 0: time.sleep(wait)
        _last[0] = time.time()
    req = urllib.request.Request("https://openrouter.ai/api/v1/chat/completions", data=json.dumps(body).encode(),
                                 headers={"Authorization": f"Bearer {KEY}", "Content-Type": "application/json",
                                          "X-Title": "prism-agent-study"})
    try:
        r = json.load(urllib.request.urlopen(req, timeout=180, context=SSL_CTX))
    except urllib.error.HTTPError as e:
        try: _err_text[threading.get_ident()] = e.read().decode()[:500]
        except Exception: pass
        return None, f"http_{e.code}", e.code
    except Exception as e:
        return None, type(e).__name__, 0
    if "error" in r:
        _err_text[threading.get_ident()] = json.dumps(r["error"])[:500]
        return None, f"provider_{r['error'].get('code', 'error')}", 200
    if not r.get("choices"):
        return None, "no_choices", 200
    return r, None, 200


class Session:
    def __init__(self, sc):
        self.sc, self.id = sc, sc["session_id"]
        self.dir = os.path.join(RUN, self.id)
        shutil.rmtree(self.dir, ignore_errors=True)
        shutil.copytree(os.path.join(HERE, "workspace"), os.path.join(self.dir, "ws"))
        os.makedirs(os.path.join(self.dir, "ws", "out"), exist_ok=True)
        self.db = os.path.join(self.dir, "shop.db")
        shop_mcp.build(self.db)
        self.servers = start_servers(self.db, os.path.join(self.dir, "ws"), os.path.join(self.dir, "memory.json"))
        self.route, self.tools = {}, []
        for s in self.servers:
            for t in s.tools:
                name = f"{s.name}__{t['name']}"
                self.route[name] = (s, t["name"])
                schema = {k: v for k, v in t["inputSchema"].items() if k != "$schema"}
                self.tools.append({"type": "function", "function": {"name": name, "description": t.get("description", ""), "parameters": schema}})
        if ARM != "noskill": self.tools.append({"type": "function", "function": {
            "name": "load_skill", "description": "Load the full instructions of a skill by name.",
            "parameters": {"type": "object", "properties": {"name": {"type": "string", "enum": sorted(SKILLS)}}, "required": ["name"]}}})
        self.schema_chars = {s.name: sum(len(json.dumps(t)) for t in self.tools if t["function"]["name"].startswith(s.name + "__"))
                             for s in self.servers}
        self.schema_chars["skill"] = len(json.dumps(self.tools[-1])) if ARM != "noskill" else 0
        skills = ("Skills are instructions for recurring tasks. When a request matches a skill, call load_skill first and "
                  "follow it\nexactly. Available skills:\n" + "\n".join(f"- {n}: {s['description']}" for n, s in SKILLS.items()) + "\n\n")
        if ARM == "noskill": skills = ""
        self.system = SYSTEM.format(role=sc["role"], today=shop_mcp.TODAY, weekday=shop_mcp.TODAY.strftime("%A"), skills=skills)
        self.messages = [{"role": "system", "content": self.system}]
        self.spans = []
        self.sim = dt.datetime.fromisoformat(sc["sim_start"])
        self.t0 = time.time()

    def span(self, trace, parent, name, start, attrs, status="ok"):
        s = {"trace_id": trace, "span_id": sid(), "parent_span_id": parent, "name": name, "start_time": start,
             "end_time": now(), "status": status, "attributes": attrs}
        s["duration_ms"] = int((dt.datetime.fromisoformat(s["end_time"]) - dt.datetime.fromisoformat(start)).total_seconds() * 1000)
        self.spans.append(s)
        return s

    def chat(self, trace, root):
        """One model step with retries. Every attempt is a span. Returns the assistant message or None."""
        body = {"model": MODEL, "messages": self.messages, "tools": self.tools, "max_tokens": 1500, "temperature": 0.2,
                "usage": {"include": True}}
        for attempt in range(5):
            start = now()
            r, err, http = post(body)
            attrs = {"gen_ai.operation.name": "chat", "gen_ai.conversation.id": self.id, "gen_ai.request.model": MODEL,
                     "prism.attempt": attempt + 1, "prism.input_messages": len(self.messages),
                     "prism.input_chars": sum(len(json.dumps(m)) for m in self.messages),
                     "prism.tool_schema_chars": self.schema_chars, "http.status_code": http}
            msg = None
            if r:
                msg = r["choices"][0]["message"]
                u = r.get("usage") or {}
                calls = msg.get("tool_calls") or []
                attrs.update({"gen_ai.response.model": r.get("model"), "gen_ai.provider.name": r.get("provider"),
                              "gen_ai.usage.input_tokens": u.get("prompt_tokens"), "gen_ai.usage.output_tokens": u.get("completion_tokens"),
                              "gen_ai.usage.reasoning_tokens": (u.get("completion_tokens_details") or {}).get("reasoning_tokens"),
                              "gen_ai.usage.cached_tokens": (u.get("prompt_tokens_details") or {}).get("cached_tokens"),
                              "gen_ai.usage.cost": u.get("cost"),
                              "gen_ai.response.finish_reasons": [r["choices"][0].get("finish_reason")],
                              "gen_ai.output.text": msg.get("content") or "",
                              "gen_ai.output.tool_calls": [c["function"]["name"] for c in calls]})
                if not calls and not (msg.get("content") or "").strip():
                    err, msg = "empty_response", None
            if err:
                attrs["error.type"] = err
                attrs["error.message"] = _err_text.pop(threading.get_ident(), "")
            self.span(trace, root, f"chat {MODEL}", start, attrs, "error" if err else "ok")
            if msg: return msg
            time.sleep(min(4 * (attempt + 1), 20) if err in ("http_429", "provider_429") else 2)
        return None

    def tool(self, trace, root, call):
        name, start = call["function"]["name"], now()
        attrs = {"gen_ai.operation.name": "execute_tool", "gen_ai.conversation.id": self.id, "gen_ai.tool.name": name,
                 "gen_ai.tool.call.arguments": call["function"].get("arguments") or ""}
        err = None
        try:
            args = json.loads(call["function"].get("arguments") or "{}")
            if not isinstance(args, dict): raise ValueError
        except ValueError:
            args, err, text = None, "bad_arguments", "Error: arguments are not a valid JSON object"
        if err is None:
            if name == "load_skill":
                attrs["mcp.server.name"] = "skill"
                sk = SKILLS.get(args.get("name"))
                attrs["prism.skill.name"] = args.get("name")
                text, err = (sk["body"], None) if sk else (f"Error: unknown skill {args.get('name')}", "unknown_skill")
            elif name in self.route:
                server, tool = self.route[name]
                attrs["mcp.server.name"] = server.name
                text, bad = server.call(tool, args)
                err = "tool_error" if bad else None
            else:
                text, err = f"Error: unknown tool {name}", "unknown_tool"
        attrs["gen_ai.tool.call.result"] = text[:2000]
        attrs["prism.result_chars"] = len(text)
        if err: attrs["error.type"] = err
        self.span(trace, root, f"execute_tool {name}", start, attrs, "error" if err else "ok")
        return text[:3000]

    def turn(self, i, t):
        trace, root, start = uuid.uuid4().hex, sid(), now()
        self.sim += dt.timedelta(seconds=45 + (len(t["text"]) * 3) % 150)        # the person reads and types
        sim_start, real0 = self.sim, time.time()
        self.messages.append({"role": "user", "content": t["text"]})
        final, steps, stop = "", 0, "completed"
        while True:
            if steps == MAX_STEPS: stop = "step_limit"; break
            steps += 1
            msg = self.chat(trace, root)
            if msg is None: stop = "model_failure"; break
            keep = {"role": "assistant", "content": msg.get("content") or ""}
            if msg.get("tool_calls"):
                keep["tool_calls"] = [{"id": c.get("id") or sid(), "type": "function",
                                       "function": {"name": c["function"]["name"], "arguments": c["function"].get("arguments") or "{}"}}
                                      for c in msg["tool_calls"]]
            self.messages.append(keep)
            if not msg.get("tool_calls"):
                final = keep["content"]; break
            for c in keep["tool_calls"]:
                self.messages.append({"role": "tool", "tool_call_id": c["id"], "content": self.tool(trace, root, c)})
        if stop != "completed":
            self.messages.append({"role": "assistant", "content": final or "(no answer)"})
        self.sim += dt.timedelta(seconds=time.time() - real0)
        results = [check(c, final, self) for c in t["checks"]]
        s = {"trace_id": trace, "span_id": root, "parent_span_id": None, "name": "invoke_agent shop-assistant",
             "start_time": start, "end_time": now(), "status": "ok" if stop == "completed" else "error",
             "attributes": {"gen_ai.operation.name": "invoke_agent", "gen_ai.agent.name": "shop-assistant",
                            "gen_ai.conversation.id": self.id, "user.id": self.sc["user"],
                            "prism.turn_index": i + 1, "prism.sim_start": sim_start.isoformat(), "prism.sim_end": self.sim.isoformat(),
                            "prism.stop_reason": stop, "prism.model_steps": steps,
                            "gen_ai.input.text": t["text"], "gen_ai.output.text": final,
                            "eval.checks": len(results), "eval.passed": sum(results),
                            "eval.detail": [{"check": c[0], "ok": bool(r)} for c, r in zip(t["checks"], results)]}}
        if stop != "completed": s["attributes"]["error.type"] = stop
        s["duration_ms"] = int((time.time() - real0) * 1000)
        self.spans.append(s)

    def close(self):
        for s in self.servers: s.close()


NUM = re.compile(r"-?\d[\d,]*\.?\d*")


def check(c, reply, sess):
    kind, low = c[0], reply.lower()
    if kind == "num":
        vals = []
        for m in NUM.findall(reply):
            try: vals.append(float(m.replace(",", "").rstrip(".")))
            except ValueError: pass
        want = c[1] if isinstance(c[1], list) else [c[1]]
        return any(abs(v - w) <= max(0.005 * abs(w), 0.06) for v in vals for w in want)
    if kind == "has": return all(x.lower() in low for x in c[1])
    if kind == "any": return any(x.lower() in low for x in c[1])
    if kind == "not": return bool(reply.strip()) and not any(x.lower() in low for x in c[1])
    if kind == "file": return os.path.exists(os.path.join(sess.dir, "ws", c[1]))
    db = sqlite3.connect(sess.db)
    row = lambda tid: dict(zip(("status", "priority", "category", "note"),
                               db.execute("SELECT status, priority, category, note FROM tickets WHERE id=?", (tid,)).fetchone()))
    if kind == "ticket": return all(row(c[1]).get(k) == v for k, v in c[2].items())
    if kind == "note": return bool(row(c[1])["note"])
    if kind == "tickets": return sum(all(row(t).get(k) == v for k, v in want.items()) for t, want in c[1].items()) >= c[2]
    raise ValueError(kind)


def run_session(sc):
    path = os.path.join(TRACES, sc["session_id"] + ".jsonl")
    if os.path.exists(path): return
    sess = Session(sc)
    try:
        for i, t in enumerate(sc["turns"]):
            sess.turn(i, t)
    finally:
        sess.close()
    with open(path + ".tmp", "w") as f:
        for s in sess.spans: f.write(json.dumps(s) + "\n")
    os.rename(path + ".tmp", path)
    roots = [s for s in sess.spans if s["parent_span_id"] is None]
    print(sc["session_id"], "turns", len(roots), "chat", sum(s["name"].startswith("chat") for s in sess.spans),
          "tools", sum(s["name"].startswith("execute") for s in sess.spans),
          "checks", sum(r["attributes"]["eval.passed"] for r in roots), "/", sum(r["attributes"]["eval.checks"] for r in roots),
          f"{time.time() - sess.t0:.0f}s", flush=True)


def merge():
    with open(os.path.join(HERE, "data", f"traces{SUFFIX}.jsonl"), "w") as out:
        for f in sorted(os.listdir(TRACES)):
            if f.endswith(".jsonl"): out.write(open(os.path.join(TRACES, f)).read())


if __name__ == "__main__":
    os.makedirs(TRACES, exist_ok=True)
    todo = [s for s in scenarios.sessions() if not sys.argv[1:] or s["session_id"] in sys.argv[1:]]
    with ThreadPoolExecutor(int(os.environ.get("WORKERS", "3"))) as ex:
        for f in [ex.submit(run_session, s) for s in todo]:
            try: f.result()
            except Exception as e: print("session failed:", repr(e), flush=True)
    merge()
