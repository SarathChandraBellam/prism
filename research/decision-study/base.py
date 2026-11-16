"""Shared loader for the decision study. Reads only spans in the docs/trace-schema.md shape (data/lake_otel.jsonl).

Everything here is computed from the spans, the directory and the seat list. Ground truth is loaded by truth() and may
be used only to score. Standard library only. No model.

    sessions()      conversations: turns in order, user, platform, text
    rebuild_tasks() task chains across platforms, by a fixed rule (not tuned here)
    cost(span)      shadow cost of a model call: tokens at the list price of the model that answered
"""
import collections, datetime as dt, json, os, re, statistics

HERE = os.path.dirname(os.path.abspath(__file__))
XP = os.path.join(os.path.dirname(HERE), "cross-platform", "data")      # round 4 data: directory, seats, truth, labels
AS = os.path.join(os.path.dirname(HERE), "agent-study", "data")         # round 3 data: price table, scripts
D = os.path.join(HERE, "data")
PLATFORMS = ["atlas", "beacon", "chatly"]
NAME = {"atlas": "Atlas", "beacon": "Beacon", "chatly": "Chatly"}

A = lambda s: s["attributes"]
op = lambda s: A(s)["gen_ai.operation.name"]
failed = lambda s: s["status"]["code"] == "ERROR"
platform = lambda s: s["resource"]["service.name"]
T = lambda x: dt.datetime.fromisoformat(x)
seconds = lambda s: (T(s["end_time"]) - T(s["start_time"])).total_seconds()


def jl(path): return [json.loads(l) for l in open(path)]
def load(name): return json.load(open(os.path.join(D, name)))
def save(name, obj): json.dump(obj, open(os.path.join(D, name), "w"), indent=1, sort_keys=True)
def directory(): return json.load(open(os.path.join(XP, "directory.json")))["users"]
def roles(): return {u["handle"]: u["role"] for u in directory()}
def seat_list(): return json.load(open(os.path.join(XP, "seats.json")))
def truth(): return json.load(open(os.path.join(XP, "truth.json")))            # SCORING ONLY
def scripts(): return {s["session_id"]: s for s in json.load(open(os.path.join(AS, "scenarios.json")))}   # SCORING ONLY


def text_of(messages):
    """All text parts of a list of messages, joined."""
    return "\n".join(p["content"] for m in (messages or []) for p in m["parts"] if p["type"] == "text")


def server_of(tool):
    """The MCP server of a tool, from the harness's `server__tool` naming. The conventions have no attribute for it."""
    return tool.split("__")[0] if "__" in tool else None


# ---------------------------------------------------------------- cost

_prices = None
def cost(span):
    """Shadow cost in USD of one model call. The conventions carry no cost, so it is tokens x a price table."""
    global _prices, _fallback
    if _prices is None:
        _prices = json.load(open(os.path.join(AS, "prices.json")))
        _fallback = [statistics.median(p[0] for p in _prices.values()), statistics.median(p[1] for p in _prices.values())]
    a = A(span); m = a.get("gen_ai.response.model") or ""
    p = _prices.get(m[:-5] if m.endswith(":free") else m) or _fallback
    return (a.get("gen_ai.usage.input_tokens") or 0) * p[0] + (a.get("gen_ai.usage.output_tokens") or 0) * p[1]


# ---------------------------------------------------------------- sessions

STOP = set("a an the of to for and or is are was were be do does can could we you i it me my our this that on in at with please what how which who".split())
TOK = lambda s: {w for w in re.findall(r"[a-z0-9\-]+", s.lower()) if w not in STOP}
ENT = re.compile(r"\b[59]\d{3}\b|\b[A-Z]{3}-[A-Z]{3,5}\b")                 # order and ticket numbers, SKUs
INABILITY = ("don't have access", "do not have access", "can't access", "cannot access", "no access", "unable to", "i can't", "i cannot",
             "i'm not able", "i am not able", "don't have real-time", "do not have real-time", "don't have the ability", "not able to look")


def jac(a, b): return len(a & b) / len(a | b) if a | b else 0.0


def sessions(path=None):
    """{conversation id: session}. A session has id, platform, user, start, end, first, text, entities and turns.
    A turn has idx (1-based, by start time), root, kids, chats, tools, input, output, and the signals no_answer,
    tool_error, inability and trouble (any of the three)."""
    spans = jl(path or os.path.join(D, "lake_otel.jsonl"))
    kids = collections.defaultdict(list)
    for s in spans:
        if s["parent_span_id"]: kids[s["trace_id"]].append(s)
    ses = {}
    for s in spans:
        if s["parent_span_id"] is not None: continue
        a = A(s); cid = a["gen_ai.conversation.id"]
        x = ses.setdefault(cid, {"id": cid, "platform": platform(s), "user": a["user.id"], "turns": []})
        ks = sorted(kids[s["trace_id"]], key=lambda k: k["start_time"])
        out = text_of(a.get("gen_ai.output.messages"))
        t = {"root": s, "kids": ks, "chats": [k for k in ks if op(k) == "chat"], "tools": [k for k in ks if op(k) == "execute_tool"],
             "input": text_of(a.get("gen_ai.input.messages")), "output": out}
        t["no_answer"] = not out.strip()
        t["tool_error"] = any(failed(k) for k in t["tools"])
        t["inability"] = any(p in out.lower() for p in INABILITY)
        t["trouble"] = t["no_answer"] or t["tool_error"] or t["inability"]
        t["cost"] = sum(cost(k) for k in t["chats"])
        x["turns"].append(t)
    for x in ses.values():
        x["turns"].sort(key=lambda t: t["root"]["start_time"])
        for i, t in enumerate(x["turns"]): t["idx"] = i + 1
        x["start"], x["end"] = T(x["turns"][0]["root"]["start_time"]), T(x["turns"][-1]["root"]["end_time"])
        x["first"] = x["turns"][0]["input"]
        x["text"] = " ".join(t["input"] for t in x["turns"])
        x["entities"] = set(ENT.findall(x["text"]))
        x["cost"] = sum(t["cost"] for t in x["turns"])
        x["ends_in_trouble"] = x["turns"][-1]["trouble"]
    return ses


# ---------------------------------------------------------------- tasks

WINDOW_S, MIN_OVERLAP = 30 * 60, 0.10


def rebuild_tasks(ses):
    """Task chains from the spans alone. Session B continues session A when: same user, another platform, B starts 0 to
    30 minutes after A ends, and their first prompts share words (Jaccard >= 0.10) or an order, ticket or SKU id. Each
    session keeps its nearest predecessor and each predecessor its nearest successor. The rule and its numbers are the
    ones round 4 reported; they are fixed here and not tuned again. Returns a list of tasks, each
    {id, user, sessions: [session ids in order], start, end}."""
    by = collections.defaultdict(list)
    for x in ses.values(): by[x["user"]].append(x)
    links = []
    for xs in by.values():
        for a in xs:
            for b in xs:
                gap = (b["start"] - a["end"]).total_seconds()
                if a["platform"] != b["platform"] and 0 <= gap <= WINDOW_S and \
                        (jac(TOK(a["first"]), TOK(b["first"])) >= MIN_OVERLAP or a["entities"] & b["entities"]):
                    links.append((gap, a["id"], b["id"]))
    pred, succ = {}, {}
    for gap, a, b in sorted(links):
        if b not in pred and a not in succ: pred[b] = a; succ[a] = b
    tasks = []
    for x in sorted(ses.values(), key=lambda x: (x["start"], x["id"])):
        if x["id"] in pred: continue
        chain = [x["id"]]
        while chain[-1] in succ: chain.append(succ[chain[-1]])
        tasks.append({"id": f"K{len(tasks) + 1:02d}", "user": x["user"], "sessions": chain, "start": x["start"], "end": ses[chain[-1]]["end"]})
    return tasks


def truth_tasks():
    """SCORING ONLY. {session id: (task id, position)} and the list of true chains."""
    t = truth()
    return {s["lake_session_id"]: (k["task_id"], i) for k in t["tasks"] for i, s in enumerate(k["sessions"])}, \
        [[s["lake_session_id"] for s in k["sessions"]] for k in t["tasks"]]


# ---------------------------------------------------------------- small statistics

def wilson(k, n, z=1.96):
    """95% Wilson interval for a share k of n."""
    if not n: return (0.0, 1.0)
    p = k / n; d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d; h = z * ((p * (1 - p) / n + z * z / (4 * n * n)) ** .5) / d
    return (max(0.0, c - h), min(1.0, c + h))


def pct(a, b): return f"{100 * a / b:.0f}%" if b else "–"
