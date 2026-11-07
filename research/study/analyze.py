"""Analyse the context study. Prints markdown tables; writes data/results.json."""
import json, os, sys, random, hashlib, collections, statistics as st
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault("OPEN_ROUTER_KEY", "x")
import llm, label as L

random.seed(3)
S = {s["id"]: s for s in L.S}
FIELDS = ["domain", "task_type", "collaboration_pattern", "outcome", "context_reexplained"]
SHORT = {"domain": "domain", "task_type": "task", "collaboration_pattern": "collab", "outcome": "outcome", "context_reexplained": "reexpl"}


def cached(model, system, user, reasoning_off=True):
    k = hashlib.sha256(json.dumps([model, system, user, reasoning_off]).encode()).hexdigest()[:24]
    p = os.path.join(llm.CACHE, k + ".json")
    return json.load(open(p)) if os.path.exists(p) else None


def sess(model, sid, cond):
    r = cached(model, L.SESSION_SYS, "SESSION:\n\n" + S[sid][cond])
    return r


def norm(v):
    return str(v).strip().lower()


def kappa(pairs):
    if not pairs: return float("nan")
    po = sum(a == b for a, b in pairs) / len(pairs)
    ca, cb = collections.Counter(a for a, _ in pairs), collections.Counter(b for _, b in pairs)
    pe = sum(ca[k] * cb[k] for k in ca) / len(pairs) ** 2
    return (po - pe) / (1 - pe) if pe < 1 else 1.0


def boot(vals, n=1000):
    if not vals: return (float("nan"),) * 3
    m = sum(vals) / len(vals)
    bs = sorted(sum(random.choice(vals) for _ in vals) / len(vals) for _ in range(n))
    return m, bs[int(.025 * n)], bs[int(.975 * n)]


R1, R2 = L.REFS
res = {}

# ---------- 1. reference reliability ----------
ref = {}
print("## 1. How often do the two reference models agree on the full trace (C6)?\n")
print("| source | n | " + " | ".join(SHORT[f] for f in FIELDS) + " |\n|---|---|" + "---|" * len(FIELDS))
rows = collections.defaultdict(lambda: collections.defaultdict(list))
for sid, s in S.items():
    a, b = sess(R1, sid, "C6"), sess(R2, sid, "C6")
    if not (a and b and a.get("labels") and b.get("labels")): continue
    ref[sid] = (a["labels"], b["labels"])
    for f in FIELDS:
        same = norm(a["labels"].get(f)) == norm(b["labels"].get(f))
        rows[s["source"]][f].append(same); rows["ALL"][f].append(same)
for src in ("own", "fable", "dataclaw", "wildchat", "ALL"):
    g = rows[src]
    if not g: continue
    print(f"| {src} | {len(g[FIELDS[0]])} | " + " | ".join(f"{100*sum(g[f])/len(g[f]):.0f}%" for f in FIELDS) + " |")
kap = {f: kappa([(norm(a.get(f)), norm(b.get(f))) for a, b in ref.values()]) for f in FIELDS}
print("| kappa (ALL) | | " + " | ".join(f"{kap[f]:.2f}" for f in FIELDS) + " |\n")
res["ref_agreement"] = {src: {f: sum(v) / len(v) for f, v in g.items()} for src, g in rows.items()}
res["ref_kappa"] = kap

# consensus gold: field-wise where both refs agree
gold = {f: {sid: norm(a.get(f)) for sid, (a, b) in ref.items() if norm(a.get(f)) == norm(b.get(f))} for f in FIELDS}

# ---------- 2. context curve ----------
print("## 2. Agreement with the reference consensus, by context condition (cheap models averaged)\n")
print("Only sessions where both references agree on that field count.\n")
print("| condition | " + " | ".join(SHORT[f] for f in FIELDS) + " | mean tokens/session |\n|---|" + "---|" * (len(FIELDS) + 1))
curve = {}
for c in L.CONDS + ["C3H"]:
    cells = []
    for f in FIELDS:
        vals = []
        for sid, g in gold[f].items():
            if c == "C3H" and not (S[sid]["n_injected"] and S[sid]["has_tools"]): continue
            for m in L.CHEAP:
                r = sess(m, sid, c)
                if r and r.get("labels"): vals.append(norm(r["labels"].get(f)) == g)
        m_, lo, hi = boot([1.0 if v else 0.0 for v in vals], 400)
        cells.append((m_, lo, hi, len(vals)))
    pool = [sid for sid in S if c != "C3H" or (S[sid]["n_injected"] and S[sid]["has_tools"])]
    toks = st.mean(len(S[sid][c]) / 4 for sid in pool)
    curve[c] = {f: cells[i][0] for i, f in enumerate(FIELDS)}
    label_c = c + (" (injected text kept)" if c == "C3H" else "")
    print(f"| {label_c} | " + " | ".join(f"{x[0]*100:.0f}% ({x[1]*100:.0f}–{x[2]*100:.0f})" for x in cells) + f" | {toks:,.0f} |")
res["curve"] = curve
print()

# ---------- 2b. same for the reference model itself (does even a strong model need full context?) ----------
print("## 3. Does the strong model itself need the full trace? (Claude Haiku 5.5 at each condition vs consensus)\n")
print("| condition | " + " | ".join(SHORT[f] for f in FIELDS) + " |\n|---|" + "---|" * len(FIELDS))
for c in L.CONDS:
    out = []
    for f in FIELDS:
        vals = [norm(r["labels"].get(f)) == g for sid, g in gold[f].items() if (r := sess(R1, sid, c)) and r.get("labels")]
        out.append(f"{100*sum(vals)/max(1,len(vals)):.0f}%")
    print(f"| {c} | " + " | ".join(out) + " |")
print("\n(C6 is partly circular here: Haiku on C6 is one of the two references.)\n")

# ---------- 4. per source at key conditions ----------
print("## 4. By source: collaboration pattern and task type, cheap models vs consensus\n")
print("| source | field | C1 | C2 | C3 | C4 | C6 |\n|---|---|---|---|---|---|---|")
for src in ("own", "fable", "dataclaw", "wildchat"):
    for f in ("task_type", "collaboration_pattern", "outcome"):
        row = []
        for c in L.CONDS:
            vals = [norm(r["labels"].get(f)) == g for sid, g in gold[f].items() if S[sid]["source"] == src
                    for m in L.CHEAP if (r := sess(m, sid, c)) and r.get("labels")]
            row.append(f"{100*sum(vals)/len(vals):.0f}% (n={len(vals)//3})" if vals else "–")
        print(f"| {src} | {SHORT[f]} | " + " | ".join(row) + " |")
print()

# ---------- 5. model differences at C3 vs C6 ----------
print("## 5. By model (mean over the five fields)\n")
print("| model | C1 | C3 | C6 | $/session at C3 | $/session at C6 |\n|---|---|---|---|---|---|")
for m in L.CHEAP + [R1, R2]:
    row = []; costs = {}
    for c in ("C1", "C3", "C6"):
        vals = []; cs = []
        for f in FIELDS:
            for sid, g in gold[f].items():
                r = sess(m, sid, c)
                if r and r.get("labels"): vals.append(norm(r["labels"].get(f)) == g)
        for sid in S:
            r = sess(m, sid, c)
            if r: cs.append(float(r["usage"].get("cost") or 0))
        row.append(f"{100*sum(vals)/max(1,len(vals)):.0f}%" if vals else "–"); costs[c] = st.mean(cs) if cs else float("nan")
    print(f"| {m.split('/')[1]} | " + " | ".join(row) + f" | ${costs['C3']:.5f} | ${costs['C6']:.5f} |")
print()

# ---------- 6. distribution shift ----------
print("## 6. What a user would see: collaboration-pattern shares across all sessions\n")
pats = ["directive", "feedback_loop", "task_iteration", "learning", "validation"]
print("| labels from | " + " | ".join(pats) + " |\n|---|" + "---|" * len(pats))
def shares(lbls):
    c = collections.Counter(norm(x) for x in lbls); n = sum(c.values()) or 1
    return " | ".join(f"{100*c[p]/n:.0f}%" for p in pats)
print(f"| reference Haiku, C6 | {shares(a.get('collaboration_pattern') for a, b in ref.values())} |")
print(f"| reference Luna, C6 | {shares(b.get('collaboration_pattern') for a, b in ref.values())} |")
for c in ("C1", "C3", "C6"):
    lb = [r["labels"].get("collaboration_pattern") for sid in S for m in L.CHEAP if (r := sess(m, sid, c)) and r.get("labels")]
    print(f"| cheap models, {c} | {shares(lb)} |")
print()

# ---------- 7. turn acts ----------
print("## 7. Turn-level acts: agreement with reference consensus by context layer\n")
tsess = L.turn_sessions()
def acts(model, s, layer):
    n, txt = L.turn_block(s, layer)
    r = cached(model, L.ACT_SYS, txt)
    lab = {}
    for x in ((r or {}).get("labels") or {}).get("turns") or []:
        try: lab[int(x["i"])] = x.get("act")
        except Exception: pass
    return [lab.get(i) for i in range(1, n + 1)], (r or {}).get("labels") is not None and len(lab) == n
tgold, ref_turn_agree, bad_count = {}, [], 0
for s in tsess:
    a, oka = acts(R1, s, 4); b, okb = acts(R2, s, 4)
    if not (oka and okb): continue
    for i, (x, y) in enumerate(zip(a, b)):
        ref_turn_agree.append(x == y)
        if x == y and x: tgold[(s["id"], i)] = x
print(f"Reference models agree on {100*sum(ref_turn_agree)/max(1,len(ref_turn_agree)):.0f}% of {len(ref_turn_agree)} turns; consensus turns: {len(tgold)}\n")
print("| layer | " + " | ".join(["all", "own", "fable", "dataclaw", "wildchat"]) + " | turn-count mismatches |\n|---|---|---|---|---|---|---|")
for layer in (1, 2, 3, 4):
    by = collections.defaultdict(list); mism = 0
    for s in tsess:
        for m in L.CHEAP[:2]:
            a, ok = acts(m, s, layer)
            if not ok: mism += 1
            for i, x in enumerate(a):
                if (s["id"], i) in tgold:
                    v = x == tgold[(s["id"], i)]; by[s["source"]].append(v); by["all"].append(v)
    names = {1: "L1 message only", 2: "L2 + activity/errors", 3: "L3 + previous reply", 4: "L4 + previous user turn"}
    print(f"| {names[layer]} | " + " | ".join(f"{100*sum(by[k])/len(by[k]):.0f}%" if by[k] else "–" for k in ["all", "own", "fable", "dataclaw", "wildchat"]) + f" | {mism} |")
dist = collections.Counter(tgold.values())
print(f"\nConsensus act distribution: {dict(dist.most_common())}\n")

# ---------- 8. fold ----------
print("## 8. Incremental fold (Qwen, turn by turn) vs whole-session labelling\n")
fs = L.fold_sessions()
m = L.CHEAP[1]
by_len = collections.defaultdict(lambda: {"self": [], "gold": [], "whole_gold": []})
for s in fs:
    steps = L.run_fold.__wrapped__(m, s) if hasattr(L.run_fold, "__wrapped__") else None
    real = [t for t in s["turns"] if not t["injected"]]
    r = cached(m, L.SESSION_SYS, "SESSION:\n\n" + L.turn_text(real[0], 1))
    rec = (r or {}).get("labels"); ok = rec is not None
    for i, t in enumerate(real[1:], 2):
        if not ok: break
        rr = cached(m, L.FOLD_SYS, f"CURRENT RECORD:\n{json.dumps(rec)}\n\nNEW TURNS:\n{L.turn_text(t, i)}")
        if rr is None: ok = False; break
        if rr.get("labels"): rec = rr["labels"]
    if not ok: continue
    whole = sess(m, s["id"], "C3")
    if not (whole and whole.get("labels")): continue
    k = "6–10 turns" if len(real) <= 10 else "11–25 turns"
    for f in FIELDS:
        by_len[k]["self"].append(norm(rec.get(f)) == norm(whole["labels"].get(f)))
        if s["id"] in gold[f]:
            by_len[k]["gold"].append(norm(rec.get(f)) == gold[f][s["id"]])
            by_len[k]["whole_gold"].append(norm(whole["labels"].get(f)) == gold[f][s["id"]])
print("| session length | fold = whole-session (same model) | fold vs consensus | whole-session vs consensus |\n|---|---|---|---|")
for k in ("6–10 turns", "11–25 turns"):
    g = by_len[k]
    if g["self"]:
        print(f"| {k} | {100*sum(g['self'])/len(g['self']):.0f}% | {100*sum(g['gold'])/max(1,len(g['gold'])):.0f}% | {100*sum(g['whole_gold'])/max(1,len(g['whole_gold'])):.0f}% |")
print()

# ---------- cost ----------
print(f"Total spent on this study: ${llm.spent():.3f}")
json.dump(res, open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "results.json"), "w"), indent=1, default=str)
