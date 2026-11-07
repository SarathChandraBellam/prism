"""Score approaches against the reference (strong model on full trace)."""
import json, os, re, collections, hashlib

HERE = os.path.dirname(os.path.abspath(__file__))
import importlib.util
spec = importlib.util.spec_from_file_location("run", os.path.join(HERE, "run.py"))
os.environ.setdefault("OPEN_ROUTER_KEY", "x")
run = importlib.util.module_from_spec(spec); spec.loader.exec_module(run)

REF = "z-ai/glm-5.3"
CHEAP = ["z-ai/glm-5.3-flash", "qwen/qwen3.7-flash", "deepseek/deepseek-v4.1-flash"]
FIELDS = ["domain", "task_type", "collaboration_pattern", "outcome", "context_reexplained"]
sessions = [json.loads(l) for l in open(os.path.join(HERE, "sessions.jsonl"))]


def cached(model, system, user):
    h = hashlib.sha256(json.dumps([model, system, user]).encode()).hexdigest()[:24]
    p = os.path.join(run.CACHE, f"{h}.json")
    return json.load(open(p)) if os.path.exists(p) else None


def single(model, view, s):
    r = cached(model, run.SYS, f"SESSION ({view} view):\n\n{s[view]}")
    return r


def per_trace_rollup(model, s):
    recs, cost = [], 0.0
    for t in s["per_trace"]:
        r = cached(model, run.SYS, f"SESSION (single trace only):\n\n{t}")
        if r and r.get("labels"):
            recs.append(r["labels"]); cost += float(r["usage"].get("cost") or 0)
    if not recs:
        return None, cost, 0
    mode = lambda k: collections.Counter(str(x.get(k)) for x in recs).most_common(1)[0][0]
    topics = collections.Counter(tp for x in recs for tp in (x.get("topics") or []))
    lab = {k: mode(k) for k in ["domain", "task_type", "collaboration_pattern"]}
    lab["outcome"] = recs[-1].get("outcome")
    lab["context_reexplained"] = any(x.get("context_reexplained") is True for x in recs)
    lab["topics"] = [t for t, _ in topics.most_common(3)]
    return lab, cost, len(recs)


def fold_steps(model, s):
    steps, cost = [], 0.0
    r = cached(model, run.SYS, f"SESSION (chat_err view):\n\n{s['per_trace'][0]}")
    if not r or not r.get("labels"):
        return [], cost
    rec = r["labels"]; steps.append(rec); cost += float(r["usage"].get("cost") or 0)
    for t in s["per_trace"][1:]:
        r = cached(model, run.FOLD_SYS, f"CURRENT RECORD:\n{json.dumps(rec)}\n\nNEW TRACES:\n{t}")
        if not r:
            break
        if r.get("labels"):
            rec = r["labels"]
        cost += float(r["usage"].get("cost") or 0)
        steps.append(rec)
    return steps, cost


def norm(v):
    return str(v).strip().lower()


def words(ts):
    return {w for t in (ts or []) for w in re.findall(r"[a-z0-9]+", str(t).lower()) if len(w) > 2}


def jacc(a, b):
    a, b = words(a), words(b)
    return len(a & b) / len(a | b) if a | b else 1.0


def kappa(pairs):
    if not pairs:
        return float("nan")
    po = sum(a == b for a, b in pairs) / len(pairs)
    ca, cb = collections.Counter(a for a, _ in pairs), collections.Counter(b for _, b in pairs)
    pe = sum(ca[k] * cb[k] for k in ca) / len(pairs) ** 2
    return (po - pe) / (1 - pe) if pe < 1 else 1.0


ref = {}
for s in sessions:
    r = single(REF, "full", s)
    if r and r.get("labels"):
        ref[s["session_id"]] = (r["labels"], float(r["usage"].get("cost") or 0), r["usage"].get("prompt_tokens", 0))
print(f"reference labels: {len(ref)}/{len(sessions)} sessions; ref cost ${sum(v[1] for v in ref.values()):.4f}\n")

rows = []
all_labels = {}
for m in CHEAP:
    for appr in ["full", "chat", "chat_err", "per_trace", "fold"]:
        got, cost, toks = {}, 0.0, 0
        for s in sessions:
            sid = s["session_id"]
            if appr in ("full", "chat", "chat_err"):
                r = single(m, appr, s)
                if r and r.get("labels"):
                    got[sid] = r["labels"]; cost += float(r["usage"].get("cost") or 0); toks += r["usage"].get("prompt_tokens", 0)
            elif appr == "per_trace":
                lab, c, _ = per_trace_rollup(m, s)
                if lab: got[sid] = lab; cost += c
            else:
                if len(s["per_trace"]) == 1:
                    r = single(m, "chat_err", s)  # one trace: fold == single extraction
                    if r and r.get("labels"): got[sid] = r["labels"]; cost += float(r["usage"].get("cost") or 0)
                else:
                    st, c = fold_steps(m, s)
                    if st and len(st) == len(s["per_trace"]): got[sid] = st[-1]; cost += c
        all_labels[(m, appr)] = got
        common = [sid for sid in got if sid in ref]
        row = {"model": m.split("/")[1], "approach": appr, "n": len(common), "cost": cost}
        for f in FIELDS:
            pairs = [(norm(got[sid].get(f)), norm(ref[sid][0].get(f))) for sid in common]
            row[f] = sum(a == b for a, b in pairs) / len(pairs) if pairs else float("nan")
        row["topics_j"] = sum(jacc(got[sid].get("topics"), ref[sid][0].get("topics")) for sid in common) / max(1, len(common))
        rows.append(row)

hdr = f"{'model':22s} {'approach':10s} {'n':>3s} {'domain':>7s} {'task':>6s} {'collab':>7s} {'outcome':>8s} {'reexpl':>7s} {'topicJ':>7s} {'cost$':>8s}"
print("AGREEMENT WITH REFERENCE (glm-5.3 on full trace)\n" + hdr)
for r in rows:
    print(f"{r['model']:22s} {r['approach']:10s} {r['n']:>3d} {r['domain']:>7.0%} {r['task_type']:>6.0%} {r['collaboration_pattern']:>7.0%} {r['outcome']:>8.0%} {r['context_reexplained']:>7.0%} {r['topics_j']:>7.2f} {r['cost']:>8.4f}")

# Model-vs-model agreement (noise floor): same approach, different cheap models
print("\nCROSS-MODEL AGREEMENT (how much cheap models agree with each other; a noise floor)")
for appr in ["full", "chat_err"]:
    for i in range(len(CHEAP)):
        for j in range(i + 1, len(CHEAP)):
            a, b = all_labels[(CHEAP[i], appr)], all_labels[(CHEAP[j], appr)]
            common = [s for s in a if s in b]
            vals = []
            for f in FIELDS:
                pairs = [(norm(a[s].get(f)), norm(b[s].get(f))) for s in common]
                vals.append(sum(x == y for x, y in pairs) / max(1, len(pairs)))
            print(f"  {appr:9s} {CHEAP[i].split('/')[1]:20s} vs {CHEAP[j].split('/')[1]:20s} n={len(common):2d} " + " ".join(f"{f[:6]}={v:.0%}" for f, v in zip(FIELDS, vals)))

# Fold drift: fold final vs same model's whole-session chat_err extraction, by number of folds
print("\nFOLD DRIFT (fold final record vs same model on whole session chat_err), by traces in session")
bins = [(2, 3), (4, 9), (10, 99)]
for m in CHEAP:
    line = f"  {m.split('/')[1]:22s}"
    for lo, hi in bins:
        agree, n = 0, 0
        for s in sessions:
            k = len(s["per_trace"])
            if not (lo <= k <= hi):
                continue
            st, _ = fold_steps(m, s)
            w = single(m, "chat_err", s)
            if not st or len(st) != k or not w or not w.get("labels"):
                continue
            n += 1
            agree += sum(norm(st[-1].get(f)) == norm(w["labels"].get(f)) for f in FIELDS) / len(FIELDS)
        line += f"  traces {lo}-{hi}: {agree / n:.0%} (n={n})" if n else f"  traces {lo}-{hi}: n=0"
    print(line)

# Collaboration pattern distribution per approach (bias check: does per_trace inflate directive/feedback?)
print("\nCOLLABORATION PATTERN DISTRIBUTION (glm-5.3-flash)")
for appr in ["full", "chat", "chat_err", "per_trace", "fold"]:
    c = collections.Counter(norm(v.get("collaboration_pattern")) for v in all_labels[("z-ai/glm-5.3-flash", appr)].values())
    print(f"  {appr:10s} {dict(c.most_common())}")
c = collections.Counter(norm(v[0].get("collaboration_pattern")) for v in ref.values())
print(f"  {'REFERENCE':10s} {dict(c.most_common())}")
print(f"\nTotal spent: ${run.spent():.4f}")
