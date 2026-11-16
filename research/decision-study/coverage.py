"""Coverage: can each decision in the catalogue be computed from each platform's traces?

    python3 coverage.py         # writes data/coverage.json and data/coverage.md

For every decision in catalogue.json and every platform, each 'needs' entry is checked against the spans in
data/lake_otel.jsonl: the share of spans of the needed type that carry the attribute with a non-empty value. External
inputs are taken as the catalogue states them. A fixed rule turns the shares into a verdict per decision and platform.
A need marked "when": "ok" is measured only on spans that did not fail. The verdicts are computed a second time as if
content (opt-in in the conventions) were not recorded. The last part reads data/conformance.json and lists what the
transformer could not carry, per platform, and which decisions each gap touches. Standard library only. No model. No ground truth is read here.
"""
import collections, json, os
import base

READY, ABSENT = 0.99, 0.01            # a need is met at >= 99% of spans, absent below 1%
RULE = [f"`ready`: every non-optional need is on at least {READY:.0%} of its spans and every external input is available.",
        f"`blocked`: a non-optional need is absent (below {ABSENT:.0%} of its spans, or the platform has no spans of that type), "
        "or a required external input is not available.",
        "`partial`: anything else, i.e. a non-optional need is on 1% to 99% of its spans, or an optional need is absent.",
        "An optional need that is on some spans does not lower the verdict: it belongs only where it applies (an error type only on a failed call).",
        "An optional need on a platform with no spans of its type is not applicable and does not count.",
        "A need marked `when: ok` is measured only on spans that did not fail: a failed model call has no tokens and a failed turn has no reply."]
CONTENT = {"gen_ai.input.messages", "gen_ai.output.messages", "gen_ai.tool.call.arguments", "gen_ai.tool.call.result",
           "gen_ai.system_instructions", "gen_ai.tool.definitions"}           # opt-in in the conventions


def empty(v): return v is None or v == "" or v == [] or v == {}


def spans_of(spans, p, where):
    """The spans a need is read from: spans of one operation, or all spans for 'resource' and 'event'."""
    return [s for s in spans if base.platform(s) == p and (where in ("resource", "event") or base.op(s) == where)]


def carries(s, where, name):
    if where == "resource": return not empty(s.get("resource", {}).get(name))
    if where == "event": return any(e.get("name") == name for e in s.get("events") or [])    # no events in this data
    return not empty(base.A(s).get(name))


def check(spans, p, need, content=True):
    """Share of the need's spans that carry it. With when=ok, the share used is over spans that did not fail; the share
    over all spans is kept too. With content=False, content attributes count as absent."""
    alls = spans_of(spans, p, need["where"])
    has = lambda s: (content or need["name"] not in CONTENT) and carries(s, need["where"], need["name"])
    xs = [s for s in alls if not base.failed(s)] if need.get("when") == "ok" else alls
    k = sum(map(has, xs))
    if not xs: status = "n/a" if need.get("optional") else "no such spans"
    else: status = "met" if k / len(xs) >= READY else "absent" if k / len(xs) < ABSENT else "partial"
    return {"k": k, "n": len(xs), "share": round(k / len(xs), 4) if xs else None, "status": status,
            "k_all": sum(map(has, alls)), "n_all": len(alls), "when": need.get("when", "all")}


def verdict(needs, checks, external):
    req = [c for nd, c in zip(needs, checks) if not nd.get("optional")]
    opt = [c for nd, c in zip(needs, checks) if nd.get("optional")]
    if any(c["status"] in ("absent", "no such spans") for c in req) or not all(e["available"] for e in external): return "blocked"
    if any(c["status"] == "partial" for c in req) or any(c["status"] == "absent" for c in opt): return "partial"
    return "ready"


def fmt(k, n): return (f"{100 * k / n:.0f}%" if k in (0, n) else f"{100 * k / n:.1f}%") + f" ({k}/{n})"


def cell(c):
    if c["n"] == 0: return "no such spans"
    s = fmt(c["k"], c["n"]) + (" small n" if c["n"] < 5 else "")
    return s + f" [all spans: {fmt(c['k_all'], c['n_all'])}]" if c["when"] == "ok" and c["n_all"] != c["n"] else s


# ---------------------------------------------------------------- 1. coverage per decision and platform

def coverage(spans, cat, content=True):
    out = {}
    for d in cat["decisions"]:
        row = {}
        for p in base.PLATFORMS:
            checks = [check(spans, p, nd, content) for nd in d["needs"]]
            missing = [f"{nd['where']} `{nd['name']}`{' (optional)' if nd.get('optional') else ''}: "
                       f"{c['status'] if c['n'] else 'no ' + nd['where'] + ' spans on this platform'}"
                       + (f" {cell(c)}" if c["status"] in ("partial", "absent") else "")
                       for nd, c in zip(d["needs"], checks) if c["status"] not in ("met", "n/a")]
            missing += [f"external: {e['name']} not available" for e in d["external"] if not e["available"]]
            row[p] = {"verdict": verdict(d["needs"], checks, d["external"]), "missing": missing,
                      "needs": [{"where": nd["where"], "name": nd["name"], "optional": bool(nd.get("optional")), **c}
                                for nd, c in zip(d["needs"], checks)]}
        out[d["id"]] = row
    return out


# ---------------------------------------------------------------- 2. what the schema could not carry, and whom it hurts

def gaps(conf, cat):
    """One row per item the transformer changed or could not fill. 'decisions' come from the catalogue where an item
    names an attribute a decision reads; the rest are this script's judgment, marked as such."""
    ds = cat["decisions"]
    reads = lambda name, opt=True: [d["id"] for d in ds if any(nd["name"] == name and (opt or not nd.get("optional")) for nd in d["needs"])]
    by_session = [d["id"] for d in ds if d["unit"] == "session" or any(nd["name"] == "gen_ai.conversation.id" for nd in d["needs"])]
    judged = {
        "gen_ai.usage.cost": (reads("gen_ai.usage.input_tokens"), "cost is recomputed from tokens and a price table (base.cost), so it is a shadow cost, not a bill"),
        "mcp.server.name": (reads("gen_ai.tool.name", opt=False), "the server is read back from the `server__tool` prefix (base.server_of); D4 groups missing capabilities by it"),
        "session.turn_index": (by_session, "derivable: order of the root spans of one conversation by start time"),
        "http.status_code": ([], "error.type carries the failure class"),
        "gen_ai.provider.name": ([], "none of the six decisions reads the provider; the model name is enough for price"),
        "finish_reason of the output message": ([], "no decision reads the finish reason; only the text and tool calls are read"),
        "mcp.method.name from the tool-name prefix": ([], "no decision reads the MCP method"),
    }
    rows = []
    for action in ("renamed", "restructured", "inferred", "dropped", "moved_to_resource"):
        for item, n in sorted(conf.get(action, {}).items()):
            key = item.split(" -> ")[-1].split(" from ")[0].split(" (")[0].split()[-1]
            if item in judged or key in judged:
                ids, why = judged.get(item) or judged[key]; basis = "judgment"
            else:
                ids = reads(key); basis = "catalogue"
                why = "decisions that read this attribute" if ids else "no decision reads this attribute"
            rows.append({"action": action, "item": item, "spans": {p: n.get(p, 0) for p in base.PLATFORMS}, "decisions": ids, "basis": basis, "note": why})
    miss = collections.defaultdict(dict)
    for pk, m in sorted(conf.get("required_missing", {}).items()):
        p, o = pk.split(" ", 1)
        for name, n in m.items(): miss[(name, o)][p] = (n, conf["spans_by_platform_and_type"].get(pk))
    for (name, o), by in sorted(miss.items()):
        ids, why = judged.get(name) or (reads(name), "decisions that read this attribute")
        rows.append({"action": "required missing", "item": f"{name} on {o} spans", "spans": {p: by.get(p, (0, None))[0] for p in base.PLATFORMS},
                     "of_spans": {p: by[p][1] for p in by}, "decisions": ids, "basis": "judgment" if name in judged else "catalogue", "note": why})
    return rows


def content_loss(d):
    """What a decision loses without content, from the 'for' text of its content needs."""
    return "; ".join(nd["for"].split(". ")[0].split(" (")[0] + (" (optional)" if nd.get("optional") else "")
                     for nd in d["needs"] if nd["name"] in CONTENT) or "nothing"


# ---------------------------------------------------------------- markdown

def table(head, rows): return "\n".join(["| " + " | ".join(head) + " |", "|" + "---|" * len(head)] + ["| " + " | ".join(map(str, r)) + " |" for r in rows])


def gcell(g, p):
    n = g["spans"][p]
    if not n: return ""
    return f"{n} of {g['of_spans'][p]}" if "of_spans" in g else str(n)


def markdown(cov, off, cat, gp, spans):
    P = base.PLATFORMS; ds = {d["id"]: d for d in cat["decisions"]}
    V = collections.Counter(cov[d][p]["verdict"] for d in cov for p in P)
    L = ["# Coverage: which decisions the traces can answer", "",
         f"Computed from {len(spans)} spans in `data/lake_otel.jsonl` and `catalogue.json` by `coverage.py`. Shares are the spans of the needed type "
         "that carry the attribute with a non-empty value. No ground truth is used.", "", "Verdict rule:", ""] + [f"- {r}" for r in RULE] + [""]

    L += ["## Verdict per decision and platform", "",
          table(["Decision", "Unit", "Basis"] + [base.NAME[p] for p in P] + ["What is missing"],
                [[f"{d} {ds[d]['decision']}", ds[d]["unit"], ds[d]["basis"]] + [cov[d][p]["verdict"] for p in P] +
                 ["<br>".join(sorted({f"{base.NAME[p]}: {m}" if not m.startswith("external") else m for p in P for m in cov[d][p]["missing"]},
                                     key=lambda m: (not m.startswith("external"), m))) or "nothing"] for d in cov]), "",
          "What the evidence must show before a card may say \"act\" (the bar):", ""] + [f"- {d}: {ds[d]['bar']}" for d in cov] + [""]
    ready = [f"{d} on {base.NAME[p]}" for d in cov for p in P if cov[d][p]["verdict"] == "ready"]
    ext = [d for d in cov if any(not e["available"] for e in ds[d]["external"])]
    L += [f"- {V['ready']} of {sum(V.values())} decision-platform cells are ready, {V['partial']} partial and {V['blocked']} blocked.",
          f"- Ready: {', '.join(ready) or 'none'}.",
          f"- {len(ext)} decisions ({', '.join(ext)}) are blocked on every platform by an input that is not in any trace: "
          + "; ".join(f"{d} needs {', '.join(e['name'] for e in ds[d]['external'] if not e['available'])}" for d in ext) + "."]
    nospan = sorted({(d, p) for d in cov for p in P for nd in cov[d][p]["needs"] if nd["n"] == 0 and not nd["optional"]})
    if nospan: L += [f"- {', '.join(f'{d} on {base.NAME[p]}' for d, p in nospan)}: blocked because the platform has no spans of a needed type. "
                     "This is a missing capability (no tools), not lost data."]
    part = sorted({(nd["where"], nd["name"], p, nd["k"], nd["n"]) for d in cov for p in P for nd in cov[d][p]["needs"] if nd["status"] == "partial" and not nd["optional"]})
    L += ["- Non-optional needs below 99%: " + ("; ".join(f"`{n}` on {k} of {m} {w} spans on {base.NAME[p]}" for w, n, p, k, m in part) or "none") + "."]
    opt = sorted({(d, p) for d in cov for p in P if cov[d][p]["verdict"] == "partial"
                  and all(nd["status"] in ("met", "n/a") for nd in cov[d][p]["needs"] if not nd["optional"])})
    if opt: L += [f"- {', '.join(f'{d} on {base.NAME[p]}' for d, p in opt)}: partial only because an optional need falls short."]
    L += [""]

    needs = collections.OrderedDict()
    for d in cat["decisions"]:
        for nd in d["needs"]: needs.setdefault((nd["where"], nd["name"], nd.get("when", "all")), []).append(d["id"] + ("*" if nd.get("optional") else ""))
    rows = []
    for (w, n, wh), ids in needs.items():
        cs = {p: next(nd for d in cov for nd in cov[d][p]["needs"] if (nd["where"], nd["name"], nd["when"]) == (w, n, wh)) for p in P}
        rows.append([w, f"`{n}`", "spans that did not fail" if wh == "ok" else "all spans", ", ".join(ids)] + [cell(cs[p]) for p in P])
    L += ["## Share of spans that carry each need", "",
          "For needs measured on spans that did not fail, the share over all spans is in brackets; the verdict uses the first figure.", "",
          table(["Where", "Attribute", "Measured on", "Read by (* optional)"] + [base.NAME[p] for p in P], rows), ""]
    full = sum(all(r[4 + i].startswith("100%") or r[4 + i] == "no such spans" for i in range(3)) for r in rows)
    noreply = [s for s in spans if base.op(s) == "invoke_agent" and empty(base.A(s).get("gen_ai.output.messages"))]
    notok = [s for s in spans if base.op(s) == "chat" and empty(base.A(s).get("gen_ai.usage.input_tokens"))]
    L += [f"- {full} of {len(rows)} needs are on 100% of their spans wherever the span type exists.",
          f"- {len(noreply)} turns have no reply, and {sum(base.failed(s) for s in noreply)} of them are failed turns. "
          f"{sum(base.failed(s) for s in notok)} of the {len(notok)} chat spans without tokens are failed requests. "
          "A failed request may still be billed, so cost from tokens can be a little low.",
          "- `error.type` is set on " + ", ".join(f"{sum(carries(x, 'execute_tool', 'error.type') for x in ts if base.failed(x))} of {sum(map(base.failed, ts))} failed tool spans on {base.NAME[p]}"
                                                  for p in P for ts in [spans_of(spans, p, "execute_tool")] if ts)
          + ". It belongs only on failures, so its low share over all tool spans is not a gap; the same holds for `gen_ai.skill.name`, "
          "which belongs only on load_skill calls. A platform with no skill call at all (Beacon has no skills) has the need absent, and D4 is partial there.",
          "- `gen_ai.evaluation.result` is on 0 spans: the spans carry no events at all, so no checked outcome reaches the traces.",
          f"- Chatly has {len(spans_of(spans, 'chatly', 'execute_tool'))} tool spans, so tool and skill needs do not apply there; they are a capability it lacks.", ""]

    W = collections.Counter(off[d][p]["verdict"] for d in off for p in P)
    L += ["## What survives when content is off", "",
          "The same rule, as if the opt-in content attributes (" + ", ".join(f"`{c}`" for c in sorted(CONTENT)) + ") were absent on every platform.", "",
          table(["Decision"] + [f"{base.NAME[p]} (with content → without)" for p in P] + ["What is lost without content"],
                [[f"{d} {ds[d]['decision']}"] + [f"{cov[d][p]['verdict']} → {off[d][p]['verdict']}" for p in P] + [content_loss(ds[d])] for d in off]), ""]
    keep = [d for d in off if any(off[d][p]["verdict"] == "ready" for p in P)]
    lost = [d for d in off if all(off[d][p]["verdict"] == "blocked" for p in P) and not all(cov[d][p]["verdict"] == "blocked" for p in P)]
    L += [f"- Without content, {W['ready']} of {sum(W.values())} cells are ready, {W['partial']} partial and {W['blocked']} blocked (with content: {V['ready']}, {V['partial']}, {V['blocked']}).",
          f"- Still ready somewhere without content: {', '.join(keep) or 'none'}. Blocked everywhere only because content is off: {', '.join(lost) or 'none'}.",
          "- D1 needs content only to link a re-ask to its first session. Without it, task starts fall back to session starts, which counts a fallback as new use.",
          "- A company that will not record content can still count use per seat, but not say what the work was or why it failed.", ""]

    L += ["## What the schema could not carry", "",
          "From `data/conformance.json`. Counts are spans changed by the transformer.", "",
          table(["Action", "Item"] + [base.NAME[p] for p in P], [[g["action"], g["item"]] + [gcell(g, p) for p in P] for g in gp]), ""]
    tot = lambda g: sum(g["spans"].values())
    dropped = [g for g in gp if g["action"] == "dropped"]; miss = [g for g in gp if g["action"] == "required missing"]
    L += [f"- {len(dropped)} source attributes were dropped because the conventions have no name for them: " + ", ".join(f"`{g['item']}` ({tot(g)} spans)" for g in dropped) + ".",
          f"- {sum(tot(g) for g in gp if g['action'] == 'inferred')} values were inferred, not read: " + ", ".join(f"{g['item']} ({tot(g)})" for g in gp if g["action"] == "inferred") + ".",
          "- A Required attribute is missing on " + (", ".join(f"{gcell(g, p)} {base.NAME[p]} {g['item'].split(' on ')[1]}" for g in miss for p in P if g["spans"][p])
          or "no spans") + ". Where it is missing, the spans do not conform, whatever the analyses need.",
          f"- {sum(g['spans']['atlas'] for g in gp if g['action'] != 'moved_to_resource')} of the changes fall on Atlas, "
          f"{sum(g['spans']['beacon'] for g in gp if g['action'] != 'moved_to_resource')} on Beacon and "
          f"{sum(g['spans']['chatly'] for g in gp if g['action'] != 'moved_to_resource')} on Chatly (not counting the platform moved to the resource).", ""]
    merged = [{**g, "platforms": [base.NAME[p] for p in P if g["spans"][p]]} for g in gp]
    L += ["## Which decisions each gap affects", "",
          "'catalogue' means the decision lists the attribute in its needs. 'judgment' is this script's reading and should be checked.", "",
          table(["Item", "Action", "Platforms", "Decisions", "Basis", "Note"], [[g["item"], g["action"], ", ".join(g["platforms"]), ", ".join(g["decisions"]) or "none of the six",
                                                                   g["basis"], g["note"]] for g in merged]), ""]
    hit = [g for g in merged if g["decisions"] and g["action"] in ("dropped", "inferred", "required missing")]
    L += [f"- {len(hit)} dropped, inferred or missing items touch a decision: " + "; ".join(f"`{g['item']}` → {', '.join(g['decisions'])}" for g in hit) + ".",
          "- Each of those has a workaround from the spans: cost from tokens and a price table, the MCP server from the tool-name prefix, turn order from start times, the skill from the load_skill arguments.",
          "- The workarounds are conventions of this harness. Another vendor may name tools or skills differently, and then D3 cost and D4 lose them.", ""]
    return "\n".join(L)


def main():
    spans = base.jl(os.path.join(base.D, "lake_otel.jsonl"))
    cat, conf = json.load(open(os.path.join(base.HERE, "catalogue.json"))), base.load("conformance.json")
    assert len(spans) == conf["spans"], "conformance.json is stale against lake_otel.jsonl"
    assert {f"{base.platform(s)} {base.op(s)}" for s in spans} == set(conf["spans_by_platform_and_type"])
    cov, off, gp = coverage(spans, cat), coverage(spans, cat, content=False), gaps(conf, cat)
    base.save("coverage.json", {"rule": RULE, "thresholds": {"ready": READY, "absent": ABSENT}, "content_attributes": sorted(CONTENT),
                                "coverage": cov, "coverage_without_content": off, "gaps": gp,
                                "content_loss": {d["id"]: content_loss(d) for d in cat["decisions"]}})
    open(os.path.join(base.D, "coverage.md"), "w").write(markdown(cov, off, cat, gp, spans))
    for d in cov: print(d, "  ".join(f"{base.NAME[p]}: {cov[d][p]['verdict']} / no content {off[d][p]['verdict']}" for p in base.PLATFORMS))
    print(f"{len(gp)} schema gaps listed. Wrote data/coverage.json and data/coverage.md")


if __name__ == "__main__":
    main()
