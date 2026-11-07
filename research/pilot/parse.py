"""Parse Claude Code JSONL logs into sessions -> traces, and build input views.

Views:
  full      : everything the agent saw/produced (user, assistant text, thinking, tool inputs, tool outputs)
  chat      : user messages + head/tail of final assistant reply per trace + one line per tool call
  chat_err  : chat + short excerpt of failing tool outputs
Outputs sessions.jsonl in the same folder.
"""
import json, re, sys, glob, os, hashlib

ROOT = os.path.expanduser(os.environ.get("PILOT_LOG_ROOT", "~/.claude/projects"))
OUT = os.path.join(os.path.dirname(__file__), "sessions.jsonl")
EXCLUDE_SESSIONS = set(filter(None, os.environ.get("PILOT_EXCLUDE_SESSIONS", "").split(",")))  # e.g. the session running the pilot

SECRET_PATTERNS = [
    re.compile(r"sk-[A-Za-z0-9_\-]{16,}"),
    re.compile(r"(?i)(api[_-]?key|secret|token|password|passwd|bearer)\s*[:=]\s*['\"]?[^\s'\"]{8,}"),
    re.compile(r"AKIA[0-9A-Z]{16}"),
    re.compile(r"ghp_[A-Za-z0-9]{20,}"),
    re.compile(r"eyJ[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}"),
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----[\s\S]*?-----END [A-Z ]*PRIVATE KEY-----"),
]
HOME_PREFIX = os.path.expanduser("~").replace("/", "-") + "-"
EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
NOISE = re.compile(r"<system-reminder>[\s\S]*?</system-reminder>|<ide_[a-z_]+>[\s\S]*?</ide_[a-z_]+>")


def redact(s: str) -> str:
    for p in SECRET_PATTERNS:
        s = p.sub("[REDACTED]", s)
    return EMAIL.sub("[EMAIL]", s)


def text_of(content):
    if isinstance(content, str):
        return content
    out = []
    for b in content or []:
        if isinstance(b, dict):
            if b.get("type") == "text":
                out.append(b.get("text", ""))
            elif b.get("type") == "tool_result":
                c = b.get("content")
                out.append(text_of(c) if not isinstance(c, str) else c)
    return "\n".join(out)


def is_real_user(rec):
    """A human-typed prompt, not a tool_result or harness-injected message."""
    if rec.get("type") != "user" or rec.get("isSidechain"):
        return False
    m = rec.get("message") or {}
    c = m.get("content")
    if isinstance(c, list) and any(isinstance(b, dict) and b.get("type") == "tool_result" for b in c):
        return False
    t = NOISE.sub("", text_of(c)).strip()
    if not t or t.startswith("<local-command") or t.startswith("<command-") and "<command-args></command-args>" in t and len(t) < 300:
        return bool(t) and not t.startswith("<local-command")
    return True


def ht(s, n):
    s = s.strip()
    return s if len(s) <= 2 * n else s[:n] + " […] " + s[-n:]


def parse_file(path):
    recs = []
    for line in open(path, errors="ignore"):
        try:
            recs.append(json.loads(line))
        except Exception:
            pass
    sid = os.path.basename(path)[:-6]
    traces, cur = [], None
    for r in recs:
        if r.get("type") not in ("user", "assistant"):
            continue
        if is_real_user(r):
            cur = {"ts": r.get("timestamp"), "user": NOISE.sub("", text_of(r["message"]["content"])).strip(),
                   "events": [], "cwd": r.get("cwd")}
            traces.append(cur)
            continue
        if cur is None:
            continue
        m = r.get("message") or {}
        c = m.get("content")
        side = bool(r.get("isSidechain"))
        if r["type"] == "assistant" and isinstance(c, list):
            for b in c:
                if not isinstance(b, dict):
                    continue
                if b.get("type") == "text":
                    cur["events"].append(("text", b.get("text", ""), side))
                elif b.get("type") == "thinking":
                    cur["events"].append(("thinking", b.get("thinking", ""), side))
                elif b.get("type") == "tool_use":
                    cur["events"].append(("tool_use", json.dumps({"name": b.get("name"), "input": b.get("input")})[:200000], side))
            cur["end"] = r.get("timestamp")
        elif r["type"] == "user" and isinstance(c, list):
            for b in c:
                if isinstance(b, dict) and b.get("type") == "tool_result":
                    body = b.get("content")
                    body = body if isinstance(body, str) else text_of(body)
                    cur["events"].append(("tool_result", body or "", side, bool(b.get("is_error"))))
    traces = [t for t in traces if t["user"]]
    return sid, traces


def views(traces):
    full, chat, chat_err, per_trace_chat = [], [], [], []
    for i, t in enumerate(traces, 1):
        f = [f"### Trace {i} ({t['ts']})", f"USER: {t['user']}"]
        c = [f"### Trace {i} ({t['ts']})", f"USER: {ht(t['user'], 1500)}"]
        ce = list(c)
        last_text = ""
        pending = None
        for ev in t["events"]:
            kind = ev[0]
            if kind == "text":
                f.append(f"ASSISTANT: {ev[1]}")
                if not ev[2]:
                    last_text = ev[1]
            elif kind == "thinking":
                f.append(f"THINKING: {ev[1]}")
            elif kind == "tool_use":
                f.append(f"TOOL_CALL{' (subagent)' if ev[2] else ''}: {ev[1]}")
                try:
                    pending = json.loads(ev[1]).get("name")
                except Exception:
                    pending = "?"
            elif kind == "tool_result":
                f.append(f"TOOL_RESULT: {ev[1]}")
                status = "error" if ev[3] else "ok"
                line = f"tool={pending} status={status} out={len(ev[1])//1024}KB{' subagent' if ev[2] else ''}"
                c.append(line)
                ce.append(line + (f" err=\"{ht(ev[1], 120)}\"" if ev[3] else ""))
        if last_text:
            c.append(f"ASSISTANT(final): {ht(last_text, 400)}")
            ce.append(f"ASSISTANT(final): {ht(last_text, 400)}")
        full.append("\n".join(f)); chat.append("\n".join(c)); chat_err.append("\n".join(ce))
        per_trace_chat.append("\n".join(ce))
    return ("\n\n".join(full), "\n\n".join(chat), "\n\n".join(chat_err), per_trace_chat)


def facts(traces):
    n_tools = sum(1 for t in traces for e in t["events"] if e[0] == "tool_use")
    n_err = sum(1 for t in traces for e in t["events"] if e[0] == "tool_result" and e[3])
    n_sub = sum(1 for t in traces for e in t["events"] if e[0] == "tool_use" and e[2])
    names = {}
    for t in traces:
        for e in t["events"]:
            if e[0] == "tool_use":
                try:
                    n = json.loads(e[1]).get("name")
                except Exception:
                    n = "?"
                names[n] = names.get(n, 0) + 1
    return {"traces": len(traces), "tool_calls": n_tools, "tool_errors": n_err, "subagent_tool_calls": n_sub,
            "tools": names, "start": traces[0]["ts"], "end": traces[-1].get("end") or traces[-1]["ts"]}


def main():
    files = glob.glob(os.path.join(ROOT, "*", "*.jsonl"))
    n = 0
    with open(OUT, "w") as out:
        for p in sorted(files):
            sid, traces = parse_file(p)
            if sid in EXCLUDE_SESSIONS or not traces:
                continue
            full, chat, chat_err, per_trace = views(traces)
            rec = {"session_id": sid, "project": os.path.basename(os.path.dirname(p)).replace(HOME_PREFIX, "") or "home",
                   "facts": facts(traces),
                   "full": redact(full), "chat": redact(chat), "chat_err": redact(chat_err),
                   "per_trace": [redact(x) for x in per_trace]}
            out.write(json.dumps(rec) + "\n")
            n += 1
    print(f"wrote {n} sessions to {OUT}")


if __name__ == "__main__":
    main()
