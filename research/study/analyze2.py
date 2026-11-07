"""Analyse round 2. Prints markdown."""
import json, os, sys, hashlib, collections, statistics as st
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault("OPEN_ROUTER_KEY", "x")
import llm, label as L, round2 as R

HAIKU, LUNA = L.REFS
GEMMA, QWEN, DEEP = L.CHEAP


def cached(model, system, user):
    k = hashlib.sha256(json.dumps([model, system, user, True]).encode()).hexdigest()[:24]
    p = os.path.join(llm.CACHE, k + ".json")
    r = json.load(open(p)) if os.path.exists(p) else None
    return (r or {}).get("labels")


def n(v): return str(v).strip().lower()


def kappa(pairs):
    if not pairs: return float("nan")
    po = sum(a == b for a, b in pairs) / len(pairs)
    ca, cb = collections.Counter(a for a, _ in pairs), collections.Counter(b for _, b in pairs)
    pe = sum(ca[k] * cb[k] for k in ca) / len(pairs) ** 2
    return (po - pe) / (1 - pe) if pe < 1 else 1.0


def ranks(x):
    o = sorted(range(len(x)), key=lambda i: x[i]); r = [0.0] * len(x); i = 0
    while i < len(o):
        j = i
        while j + 1 < len(o) and x[o[j + 1]] == x[o[i]]: j += 1
        for k in range(i, j + 1): r[o[k]] = (i + j) / 2
        i = j + 1
    return r


def spearman(a, b):
    if len(a) < 3: return float("nan")
    ra, rb = ranks(a), ranks(b); ma, mb = st.mean(ra), st.mean(rb)
    num = sum((x - ma) * (y - mb) for x, y in zip(ra, rb))
    den = (sum((x - ma) ** 2 for x in ra) * sum((y - mb) ** 2 for y in rb)) ** .5
    return num / den if den else float("nan")


def num(v):
    try: return int(v)
    except Exception: return 0


SW = R.swe_sessions()
ALL = L.S + SW

# ---------------- A ----------------
print("## A. Do the reference models agree more with redefined labels? (both at C3, same sessions)\n")
v1p, v2 = collections.defaultdict(list), collections.defaultdict(list)
share_diff, ext = [], []
for s in ALL:
    a1, b1 = cached(HAIKU, L.SESSION_SYS, "SESSION:\n\n" + s["C3"]), cached(LUNA, L.SESSION_SYS, "SESSION:\n\n" + s["C3"])
    a2, b2 = cached(HAIKU, R.V2_SYS, "SESSION:\n\n" + s["C3"]), cached(LUNA, R.V2_SYS, "SESSION:\n\n" + s["C3"])
    if not (a1 and b1 and a2 and b2): continue
    for f in ("domain", "task_type", "collaboration_pattern", "outcome", "context_reexplained"):
        v1p[f].append((n(a1.get(f)), n(b1.get(f))))
    sa, sb = a2.get("collab_shares") or {}, b2.get("collab_shares") or {}
    pats = ["directive", "feedback_loop", "task_iteration", "learning", "validation"]
    dom = lambda x: max(pats, key=lambda p: num(x.get(p))) if x else None
    v2["collab dominant"].append((dom(sa), dom(sb)))
    share_diff.append(sum(abs(num(sa.get(p)) - num(sb.get(p))) for p in pats) / 2)
    v2["handed over upfront"].append((n(a2.get("handed_over_upfront")), n(b2.get("handed_over_upfront"))))
    v2["outcome v2"].append((n(a2.get("outcome")), n(b2.get("outcome"))))
    coarse = lambda o: "completed" if n(o).startswith("completed") else n(o)
    v2["outcome v2 (completed merged)"].append((coarse(a2.get("outcome")), coarse(b2.get("outcome"))))
    ra, rb = set(a2.get("reexplained_turns") or []), set(b2.get("reexplained_turns") or [])
    v2["reexplained (any)"].append((bool(ra), bool(rb)))
    for c in ("n_corrections", "n_feedback_relays", "n_refinements", "n_understanding_questions"):
        v2[c].append((num(a2.get(c)), num(b2.get(c))))
    ext.append((s, a2, b2))
print(f"Sessions with all four outputs: {len(v1p['domain'])}\n")
print("| label | definition | raw agreement | κ |\n|---|---|---|---|")
for f, pairs in v1p.items():
    print(f"| {f} | v1 | {100*sum(a==b for a,b in pairs)/len(pairs):.0f}% | {kappa(pairs):.2f} |")
for f in ("collab dominant", "handed over upfront", "outcome v2", "outcome v2 (completed merged)", "reexplained (any)"):
    pairs = v2[f]; print(f"| {f} | v2 | {100*sum(a==b for a,b in pairs)/len(pairs):.0f}% | {kappa(pairs):.2f} |")
print(f"\nCollaboration shares: mean disagreement between references = {st.mean(share_diff):.0f} percentage points (0 = identical, 100 = disjoint).\n")
print("| count (v2) | within ±1 | Spearman ρ between references |\n|---|---|---|")
for c in ("n_corrections", "n_feedback_relays", "n_refinements", "n_understanding_questions"):
    pairs = v2[c]
    print(f"| {c} | {100*sum(abs(a-b)<=1 for a,b in pairs)/len(pairs):.0f}% | {spearman([a for a,_ in pairs],[b for _,b in pairs]):.2f} |")

# external validity on SWE-chat
rows = json.load(open(os.path.join(R.D, "swe", "prompt_labels.json")))
corr = collections.Counter(r["session_id"] for r in rows if r["prompt_pushback"] == "correction")
fail = collections.Counter(r["session_id"] for r in rows if r["prompt_pushback"] == "failure_report")
und = collections.Counter(r["session_id"] for r in rows if r["prompt_intent"] == "understand")
print("\n**External check on SWE-chat** (their per-prompt labels were validated against human experts):\n")
print("| our count (v2) | SWE-chat count | Spearman ρ (Haiku) | Spearman ρ (Luna) | n |\n|---|---|---|---|---|")
swe_ext = [(s, a, b) for s, a, b in ext if s["source"] == "swechat"]
for ours, theirs, name in (("n_corrections", corr, "correction pushback"), ("n_feedback_relays", fail, "failure reports"), ("n_understanding_questions", und, "'understand' intent")):
    xs = [theirs.get(s["id"], 0) for s, _, _ in swe_ext]
    print(f"| {ours} | {name} | {spearman([num(a.get(ours)) for _,a,_ in swe_ext], xs):.2f} | {spearman([num(b.get(ours)) for _,_,b in swe_ext], xs):.2f} | {len(swe_ext)} |")
print("\n| our outcome (v2) | mean SWE-chat session_success (Haiku labels) | n | (Luna labels) | n |\n|---|---|---|---|---|")
for o in ("completed_confirmed", "completed_unconfirmed", "partial", "failed_or_abandoned", "unclear"):
    ha = [float(s["swe"]["session_success"]) for s, a, _ in swe_ext if n(a.get("outcome")) == o]
    lu = [float(s["swe"]["session_success"]) for s, _, b in swe_ext if n(b.get("outcome")) == o]
    fm = lambda v: f"{st.mean(v):.0f}" if v else "–"
    print(f"| {o} | {fm(ha)} | {len(ha)} | {fm(lu)} | {len(lu)} |")

# ---------------- B ----------------
print("\n## B. Per-turn labels vs SWE-chat's human-validated labels, by context layer (one call per turn)\n")
IMAP = {"create": "create new code"}
PMAP = {"none": "non_pushback"}
al = R.aligned_turns()
print(f"Aligned turns: {len(al)}\n")
print("| layer | model | intent acc | intent κ | pushback acc | pushback κ | correction recall | correction precision |\n|---|---|---|---|---|---|---|---|")
names = {1: "L1 prompt only", 3: "L3 + previous reply, activity, errors", 4: "L4 + previous prompts"}
for layer in (1, 3, 4):
    for m in (GEMMA, DEEP):
        ip, pp = [], []
        for a in al:
            r = cached(m, R.TURN_SYS, R.turn_ctx(a["real"], a["i"], layer))
            if not r: continue
            ip.append((IMAP.get(n(r.get("intent")), n(r.get("intent"))), n(a["intent"])))
            pp.append((PMAP.get(n(r.get("pushback")), n(r.get("pushback"))), n(a["pushback"])))
        if not ip: continue
        tp = sum(1 for x, y in pp if x == y == "correction"); rec = tp / max(1, sum(1 for _, y in pp if y == "correction")); pre = tp / max(1, sum(1 for x, _ in pp if x == "correction"))
        print(f"| {names[layer]} | {m.split('/')[1]} | {100*sum(x==y for x,y in ip)/len(ip):.0f}% | {kappa(ip):.2f} | {100*sum(x==y for x,y in pp)/len(pp):.0f}% | {kappa(pp):.2f} | {100*rec:.0f}% | {100*pre:.0f}% |")

# ---------------- C ----------------
print("\n## C. SWE-chat context curve (v1 labels, cheap models vs reference consensus on C6)\n")
F = ["domain", "task_type", "collaboration_pattern", "outcome", "context_reexplained"]
gold = {f: {} for f in F}; agree = collections.defaultdict(list)
for s in SW:
    a, b = cached(HAIKU, L.SESSION_SYS, "SESSION:\n\n" + s["C6"]), cached(LUNA, L.SESSION_SYS, "SESSION:\n\n" + s["C6"])
    if not (a and b): continue
    for f in F:
        agree[f].append(n(a.get(f)) == n(b.get(f)))
        if n(a.get(f)) == n(b.get(f)): gold[f][s["id"]] = n(a.get(f))
print("Reference agreement on SWE-chat (C6): " + ", ".join(f"{f} {100*sum(v)/len(v):.0f}%" for f, v in agree.items()) + "\n")
print("| condition | " + " | ".join(F) + " | tokens/session |\n|---|" + "---|" * (len(F) + 1))
for c in ("C1", "C3", "C6", "C3H"):
    cells = []
    pool = [s for s in SW if c != "C3H" or s["n_injected"]]
    ids = {s["id"] for s in pool}
    for f in F:
        v = [n(r.get(f)) == g for sid, g in gold[f].items() if sid in ids for m in (GEMMA, DEEP)
             if (r := cached(m, L.SESSION_SYS, "SESSION:\n\n" + next(s for s in SW if s["id"] == sid)[c]))]
        cells.append(f"{100*sum(v)/max(1,len(v)):.0f}% (n={len(v)//2})")
    print(f"| {c} | " + " | ".join(cells) + f" | {st.mean(len(s[c])/4 for s in pool):,.0f} |")
print(f"\nTotal study spend so far: ${llm.spent():.3f}")
