"""Normalise four sources into one session format and build context-condition views.

Sources: own Claude Code logs (raw), Fable-5 Claude Code traces (raw), DataClaw (exported), WildChat (chat).
Output: data/study_sessions.jsonl, one session per line with turns and views C1..C6 (+ C3H, which keeps injected text).
"""
import json, os, re, glob, random, ast, sys

HERE = os.path.dirname(os.path.abspath(__file__))
D = os.path.join(HERE, "data")
random.seed(7)

INJECT = re.compile(
    r"^\s*(<command-name>|<command-message>|<local-command|<task-notification>|<system-reminder>|"
    r"Base directory for this skill|Caveat: The messages below|This session is being continued from a previous conversation|"
    r"\[Request interrupted|<user-prompt-submit-hook>|Claude Code sent this note|<bash-stdout>|<bash-stderr>)", re.I)
NOISE = re.compile(r"<system-reminder>[\s\S]*?</system-reminder>|<ide_[a-z_]+>[\s\S]*?</ide_[a-z_]+>")
SECRET = [re.compile(p) for p in (r"sk-[A-Za-z0-9_\-]{16,}", r"AKIA[0-9A-Z]{16}", r"ghp_[A-Za-z0-9]{20,}", r"hf_[A-Za-z0-9]{20,}",
                                  r"eyJ[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}",
                                  r"(?i)(api[_-]?key|secret|token|password)\s*[:=]\s*['\"]?[^\s'\"]{8,}")]
EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")


def red(s):
    s = s or ""
    for p in SECRET: s = p.sub("[REDACTED]", s)
    return EMAIL.sub("[EMAIL]", s)


def ht(s, n):
    s = (s or "").strip()
    return s if len(s) <= 2 * n else s[:n] + " […] " + s[-n:]


def text_of(c):
    if isinstance(c, str): return c
    out = []
    for b in c or []:
        if isinstance(b, dict):
            if b.get("type") == "text": out.append(b.get("text", ""))
            elif b.get("type") == "tool_result":
                x = b.get("content"); out.append(x if isinstance(x, str) else text_of(x))
    return "\n".join(out)


def new_turn(user, ts):
    u = NOISE.sub("", user or "").strip()
    return {"user": u, "ts": ts, "injected": bool(INJECT.match(u)), "events": []}


# ---------- adapters ----------
def claude_code_raw(path):
    turns, cur = [], None
    for line in open(path, errors="ignore"):
        try: r = json.loads(line)
        except Exception: continue
        if r.get("type") not in ("user", "assistant"): continue
        m = r.get("message") or {}; c = m.get("content"); side = bool(r.get("isSidechain"))
        if r["type"] == "user" and not side:
            is_tr = isinstance(c, list) and any(isinstance(b, dict) and b.get("type") == "tool_result" for b in c)
            if not is_tr and not r.get("isMeta"):
                t = new_turn(text_of(c), r.get("timestamp"))
                if t["user"]:
                    cur = t; turns.append(cur)
                continue
        if cur is None: continue
        if r["type"] == "assistant" and isinstance(c, list):
            for b in c:
                if not isinstance(b, dict): continue
                k = b.get("type")
                if k == "text": cur["events"].append({"k": "text", "text": b.get("text", ""), "sub": side})
                elif k == "thinking": cur["events"].append({"k": "thinking", "text": b.get("thinking", ""), "sub": side})
                elif k == "tool_use": cur["events"].append({"k": "tool_use", "name": b.get("name"), "text": json.dumps(b.get("input"))[:20000], "sub": side})
        elif r["type"] == "user" and isinstance(c, list):
            for b in c:
                if isinstance(b, dict) and b.get("type") == "tool_result":
                    x = b.get("content"); x = x if isinstance(x, str) else text_of(x)
                    cur["events"].append({"k": "tool_result", "text": (x or "")[:20000], "err": bool(b.get("is_error")), "sub": side})
    return turns


def dataclaw(rec):
    turns, cur = [], None
    for m in rec.get("messages", []):
        if m.get("role") == "user":
            t = new_turn(m.get("content") if isinstance(m.get("content"), str) else text_of(m.get("content")), m.get("timestamp"))
            if t["user"]: cur = t; turns.append(cur)
        elif cur is not None:
            if m.get("thinking"): cur["events"].append({"k": "thinking", "text": m["thinking"], "sub": False})
            for tu in m.get("tool_uses") or []:
                cur["events"].append({"k": "tool_use", "name": tu.get("tool"), "text": str(tu.get("input"))[:20000], "sub": False})
            if m.get("content"): cur["events"].append({"k": "text", "text": m["content"] if isinstance(m["content"], str) else text_of(m["content"]), "sub": False})
    return turns


def wildchat(conv):
    turns, cur = [], None
    for m in conv:
        if m.get("role") == "user":
            cur = new_turn(m.get("content"), str(m.get("timestamp") or "")); turns.append(cur)
        elif cur is not None and m.get("role") == "assistant":
            cur["events"].append({"k": "text", "text": m.get("content") or "", "sub": False})
    return turns


# ---------- views ----------
EDIT = {"Edit", "Write", "MultiEdit", "NotebookEdit", "apply_patch"}


def activity(t):
    tools = [e for e in t["events"] if e["k"] == "tool_use"]
    if not tools: return None
    names = {}
    for e in tools: names[e["name"]] = names.get(e["name"], 0) + 1
    errs = sum(1 for e in t["events"] if e["k"] == "tool_result" and e.get("err"))
    sub = sum(1 for e in tools if e.get("sub"))
    top = ", ".join(f"{k}×{v}" for k, v in sorted(names.items(), key=lambda kv: -kv[1])[:6])
    return f"agent: {len(tools)} tool calls ({top}); {errs} errors; {sub} in subagents"


def final_reply(t):
    txt = [e["text"] for e in t["events"] if e["k"] == "text" and not e.get("sub") and e["text"].strip()]
    return txt[-1] if txt else ""


def err_excerpts(t):
    return [ht(e["text"], 120) for e in t["events"] if e["k"] == "tool_result" and e.get("err")][:3]


def view(turns, cond, has_tools, has_results):
    out = []
    for i, t in enumerate(turns, 1):
        if t["injected"] and cond != "C3H": continue
        lines = [f"[turn {i}] USER: {ht(t['user'], 1500)}"]
        if cond == "C1":
            out.append("\n".join(lines)); continue
        if cond in ("C2", "C3", "C3H", "C4") and has_tools:
            a = activity(t)
            if a: lines.append(a)
        if cond in ("C3", "C3H", "C4"):
            f = final_reply(t)
            if f: lines.append(f"ASSISTANT: {ht(f, 300)}")
        if cond == "C4" and has_results:
            for x in err_excerpts(t): lines.append(f"tool error: {x}")
        if cond == "C6":
            lines = [f"[turn {i}] USER: {t['user']}"]
            for e in t["events"]:
                tag = " (subagent)" if e.get("sub") else ""
                if e["k"] == "text": lines.append(f"ASSISTANT{tag}: {e['text']}")
                elif e["k"] == "thinking": lines.append(f"THINKING{tag}: {ht(e['text'], 1500)}")
                elif e["k"] == "tool_use": lines.append(f"TOOL_CALL{tag} {e['name']}: {ht(e['text'], 1500)}")
                elif e["k"] == "tool_result": lines.append(f"TOOL_RESULT{tag}{' ERROR' if e.get('err') else ''}: {ht(e['text'], 2000)}")
        out.append("\n".join(lines))
    s = red("\n\n".join(out))
    if cond == "C6" and len(s) > 400_000:  # ~100k tokens cap; keep head and tail of the session
        s = s[:200_000] + "\n\n[… middle of session omitted for length …]\n\n" + s[-200_000:]
    return s


def finish(sid, source, turns, has_tools, has_results):
    real = [t for t in turns if not t["injected"]]
    if len(real) < 3: return None
    rec = {"id": sid, "source": source, "has_tools": has_tools, "has_results": has_results,
           "n_turns": len(turns), "n_real": len(real), "n_injected": len(turns) - len(real),
           "turns": [{"user": red(ht(t["user"], 3000)), "injected": t["injected"], "activity": activity(t),
                      "final": red(ht(final_reply(t), 600)), "errors": [red(x) for x in err_excerpts(t)]} for t in turns]}
    for c in ("C1", "C2", "C3", "C3H", "C4", "C6"):
        rec[c] = view(turns, c, has_tools, has_results)
    return rec


def main():
    out = []
    own_root = os.path.expanduser("~/.claude/projects")
    exclude = set(filter(None, os.environ.get("PILOT_EXCLUDE_SESSIONS", "").split(",")))
    own = []
    for p in glob.glob(os.path.join(own_root, "*", "*.jsonl")):
        sid = os.path.basename(p)[:-6]
        if sid in exclude: continue
        r = finish(sid, "own", claude_code_raw(p), True, True)
        if r: own.append(r)
    fab = [r for r in (finish(os.path.basename(p)[:-6], "fable", claude_code_raw(p), True, True) for p in glob.glob(os.path.join(D, "fable", "*.jsonl"))) if r]
    dc_all = [json.loads(l) for l in open(os.path.join(D, "dataclaw.jsonl"))]
    random.shuffle(dc_all)
    dc = []
    for rec in dc_all:
        r = finish(rec["session_id"], "dataclaw", dataclaw(rec), True, False)
        if r: dc.append(r)
        if len(dc) >= 50: break
    wc = []
    import subprocess
    rows = json.loads(subprocess.run(["uv", "run", "-q", "--with", "pyarrow", "python", "-c",
        "import pyarrow.parquet as pq,json,sys;t=pq.read_table(sys.argv[1],columns=['conversation_hash','conversation','turn','language','toxic']);"
        "rows=[r for r in t.to_pylist() if r['turn'] and int(r['turn'])>=4 and str(r['toxic'])=='False'];"
        "print(json.dumps(rows,default=str))", os.path.join(D, "wildchat0.parquet")], capture_output=True, text=True).stdout)
    random.shuffle(rows)
    en = [r for r in rows if r["language"] == "English"][:25]
    other = [r for r in rows if r["language"] != "English"][:25]
    for r in en + other:
        conv = r["conversation"]
        if isinstance(conv, str): conv = ast.literal_eval(conv)
        x = finish(r["conversation_hash"], "wildchat", wildchat(conv), False, False)
        if x: x["language"] = r["language"]; wc.append(x)
    out = own + fab + dc + wc
    with open(os.path.join(D, "study_sessions.jsonl"), "w") as f:
        for r in out: f.write(json.dumps(r) + "\n")
    tok = lambda s: len(s) / 4
    print(f"{'source':9s} {'n':>3s} {'turns':>6s} {'inj%':>5s} " + " ".join(f"{c:>8s}" for c in ("C1", "C2", "C3", "C4", "C6")))
    for src in ("own", "fable", "dataclaw", "wildchat"):
        g = [r for r in out if r["source"] == src]
        if not g: continue
        nt = sum(r["n_turns"] for r in g); ni = sum(r["n_injected"] for r in g)
        print(f"{src:9s} {len(g):>3d} {nt:>6d} {100*ni/max(1,nt):>4.0f}% " + " ".join(f"{sum(tok(r[c]) for r in g)/len(g):>8.0f}" for c in ("C1", "C2", "C3", "C4", "C6")))
    print("(mean tokens per session by condition)")


if __name__ == "__main__":
    main()
