"""Shared paths and imports for the cross-platform study. Standard library only."""
import json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
AS = os.path.join(os.path.dirname(HERE), "agent-study")
sys.path.insert(0, AS)
D = os.path.join(HERE, "data")
CACHE = os.path.join(HERE, "cache")
RUN = os.path.join(HERE, "run")
for p in (D, CACHE, RUN): os.makedirs(p, exist_ok=True)
PLATFORMS = ["atlas", "beacon", "chatly"]
PRICE = {"atlas": 30, "beacon": 20, "chatly": 20}
A = lambda s: s["attributes"]


def jl(path):
    return [json.loads(l) for l in open(path)]


def scenarios():
    return {s["session_id"]: s for s in json.load(open(os.path.join(AS, "data", "scenarios.json")))}
