"""Minimal cached OpenRouter client for the context study."""
import json, os, re, ssl, time, hashlib, urllib.request, threading

HERE = os.path.dirname(os.path.abspath(__file__))
CACHE = os.path.join(HERE, "cache"); os.makedirs(CACHE, exist_ok=True)
KEY = os.environ["OPEN_ROUTER_KEY"]
SSL_CTX = ssl.create_default_context(cafile="/etc/ssl/cert.pem")
BUDGET_USD = float(os.environ.get("BUDGET_USD", "3.0"))
_lock = threading.Lock()
_spent = None


def spent():
    global _spent
    with _lock:
        if _spent is None:
            tot = 0.0
            for f in os.listdir(CACHE):
                try: tot += float(json.load(open(os.path.join(CACHE, f))).get("usage", {}).get("cost") or 0)
                except Exception: pass
            _spent = tot
        return _spent


def _add(c):
    global _spent
    with _lock:
        _spent = (_spent or 0) + c


def parse_json(txt):
    m = re.search(r"\{[\s\S]*\}", txt or "")
    if not m: return None
    try: return json.loads(m.group(0))
    except Exception: return None


def call(model, system, user, max_tokens=2500, reasoning_off=True):
    key = hashlib.sha256(json.dumps([model, system, user, reasoning_off]).encode()).hexdigest()[:24]
    path = os.path.join(CACHE, key + ".json")
    if os.path.exists(path):
        return json.load(open(path))
    if spent() > BUDGET_USD:
        return {"model": model, "labels": None, "error": "budget", "usage": {}}
    body = {"model": model, "temperature": 0, "max_tokens": max_tokens,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
            "response_format": {"type": "json_object"},
            "usage": {"include": True}, "provider": {"data_collection": "deny"}}
    if reasoning_off:
        body["reasoning"] = {"effort": "none", "exclude": True}
    err = ""
    for attempt in range(4):
        try:
            req = urllib.request.Request("https://openrouter.ai/api/v1/chat/completions", data=json.dumps(body).encode(),
                                         headers={"Authorization": f"Bearer {KEY}", "Content-Type": "application/json"})
            r = json.load(urllib.request.urlopen(req, timeout=300, context=SSL_CTX))
            if "error" in r: raise RuntimeError(json.dumps(r["error"])[:400])
            txt = r["choices"][0]["message"].get("content") or ""
            out = {"model": model, "raw": txt, "labels": parse_json(txt), "usage": r.get("usage", {})}
            _add(float(out["usage"].get("cost") or 0))
            if out["labels"] is not None:
                json.dump(out, open(path, "w"))
            return out
        except Exception as e:
            err = str(e)
            if hasattr(e, "read"):
                try: err += " " + e.read().decode()[:400]
                except Exception: pass
            low = err.lower()
            if "reasoning" in low and "reasoning" in body: body.pop("reasoning")
            elif "response_format" in low and "response_format" in body: body.pop("response_format")
            elif "data_collection" in low or "no endpoints" in low: body["provider"] = {}
            time.sleep(2 * (attempt + 1))
    return {"model": model, "labels": None, "error": err, "usage": {}}
