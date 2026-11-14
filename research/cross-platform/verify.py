"""Sanity checks on the generated data. Exits non-zero on the first failure.

    python3 verify.py
"""
import collections, re
from common import *

truth = json.load(open(os.path.join(D, "truth.json")))
lake = jl(os.path.join(D, "lake.jsonl"))
scs = scenarios()
ok = lambda c, m: print(("ok   " if c else "FAIL ") + m) or (c or exit(1))

tasks, sess = truth["tasks"], [s for t in truth["tasks"] for s in t["sessions"]]
ok(truth["scope"]["tasks_drawn"] == 64, f"64 task instances drawn; {len(tasks)} in scope ({len(truth['scope']['scripts'])} of 32 scripts recorded on all platforms)")
roots = [s for s in lake if s["parent_span_id"] is None]
lake_ses = {A(s)["gen_ai.conversation.id"] for s in roots}
ok(lake_ses == {s["lake_session_id"] for s in sess}, f"lake sessions equal truth sessions ({len(lake_ses)})")
for p in PLATFORMS:
    ok(len({i for i in lake_ses if i.startswith(p + ":")}) == sum(s["platform"] == p for s in sess), f"sessions on {p} reconcile")
ok(sum(s["is_switch"] for s in sess) == len(sess) - len(tasks) == sum(t["n_switches"] for t in tasks), f"switch sessions {sum(s['is_switch'] for s in sess)} = sessions - tasks = sum of switches")
ok(all(not t["sessions"][0]["is_switch"] and all(s["is_switch"] for s in t["sessions"][1:]) for t in tasks), "only the first session of a task is not a switch")
ok(len(roots) == sum(s["turns_played"] for s in sess), f"lake turns equal turns played ({len(roots)})")
ok(all(len({s["platform"] for s in t["sessions"]}) == len(t["sessions"]) for t in tasks), "no platform used twice within one task")
ok(len(truth["tasks"]) == len({t["task_id"] for t in tasks}), "task ids unique")
# paraphrases keep entities and differ from the original
para = json.load(open(os.path.join(D, "paraphrases.json")))
ent = lambda s: set(re.findall(r"\b[59]\d{3}\b|\b[A-Z]{3}-[A-Z]{3,5}\b", s))
ok(all(ent(para[k]) == ent(scs[k]["turns"][0]["text"]) for k in para), "paraphrases keep order numbers, ticket numbers and SKUs")
ok(all(para[k] != scs[k]["turns"][0]["text"] for k in para), "no paraphrase equals its original")
first = {A(s)["gen_ai.conversation.id"]: A(s)["gen_ai.input.text"] for s in roots if A(s)["session.turn_index"] == 1}
byid = {s["lake_session_id"]: (t["script"], s) for t in tasks for s in t["sessions"]}
ok(all((first[i] == para[sc]) == s["is_switch"] for i, (sc, s) in byid.items()), "first message is the paraphrase exactly in the switch sessions")
# leaks and secrets
# structural leaks only: the word "designed" can occur in a model reply ("a skill designed for weekly reports"), a key or attribute cannot
bad = ["eval.", '"designed', '"prism.', 'prism.', "ground_truth", '"truth', '"is_switch"', '"task_type"', '"paraphras', '"script"', "Bearer", "sk-or", "OPEN_ROUTER", "proxy-injected"]
for f in ("export_atlas.jsonl", "export_beacon.jsonl", "export_chatly.jsonl", "lake.jsonl", "directory.json", "seats.json"):
    txt = open(os.path.join(D, f)).read().lower()
    hits = [b for b in bad if b.lower() in txt]
    ok(not hits, f"{f}: no ground truth or secret strings" + (f" (found {hits})" if hits else ""))
size = sum(os.path.getsize(os.path.join(D, f)) for f in os.listdir(D))
ok(size < 5e6, f"data directory is {size / 1e6:.2f} MB")
ok(all(A(s)["platform"] in PLATFORMS for s in lake if "platform" in A(s)), "every span has a platform")
ok(all(A(s).get("user.id") for s in roots), "every turn has a resolved user")
# turn structure survives the adapters, session by session
nt = collections.Counter(A(s)["gen_ai.conversation.id"] for s in roots)
ok(all(nt[s["lake_session_id"]] == s["turns_played"] for s in sess), "turns per session equal in lake and truth")
ans = collections.defaultdict(dict)
for s in roots: ans[A(s)["gen_ai.conversation.id"]][A(s)["session.turn_index"]] = bool((A(s)["gen_ai.output.text"] or "").strip())
ok(all([ans[s["lake_session_id"]][i + 1] for i in range(s["turns_played"])] == s["turn_answered"] for s in sess), "answered flags equal in lake and truth")
