"""Shop database for the agent study, and a no-auth MCP server (stdio) over it.

Standard library only.

    python3 shop_mcp.py build shop.db     # write the deterministic demo database
    python3 shop_mcp.py serve shop.db     # speak MCP (JSON-RPC over stdio)

The data is synthetic. "Today" in the study is fixed to TODAY so that every
ground-truth answer is reproducible.
"""
import datetime as dt, json, os, random, sqlite3, sys

TODAY = dt.date(2026, 11, 13)

PRODUCTS = [  # sku, name, category, price, stock, lead_time_days, final_sale
    ("KET-GOOSE", "Gooseneck Kettle 0.9L", "kettles", 64.0, 9, 21, 0),
    ("KET-ELEC", "Electric Pour-Over Kettle", "kettles", 129.0, 30, 28, 0),
    ("GRD-HAND", "Hand Grinder Steel Burr", "grinders", 89.0, 6, 14, 0),
    ("GRD-ELEC", "Electric Burr Grinder", "grinders", 219.0, 22, 35, 0),
    ("DRP-V60", "Ceramic Dripper 02", "brewers", 28.0, 14, 10, 0),
    ("DRP-FLAT", "Flat-Bottom Dripper", "brewers", 34.0, 60, 10, 0),
    ("PRS-FRENCH", "French Press 600ml", "brewers", 39.0, 45, 14, 0),
    ("SCL-BREW", "Brew Scale with Timer", "accessories", 49.0, 8, 21, 0),
    ("FLT-V60", "Paper Filters 02 (100)", "consumables", 9.0, 40, 7, 0),
    ("FLT-FLAT", "Flat Filters (100)", "consumables", 10.0, 300, 7, 0),
    ("MUG-CER", "Ceramic Mug 300ml", "accessories", 18.0, 120, 14, 0),
    ("BEAN-SAMP", "Sample Roast Trio", "coffee", 24.0, 80, 5, 1),
    ("BEAN-ESP", "House Espresso 1kg", "coffee", 32.0, 26, 5, 1),
    ("SRV-GLASS", "Glass Server 600ml", "accessories", 26.0, 35, 14, 0),
]
# relative demand weights, same order as PRODUCTS
WEIGHTS = [9, 3, 8, 2, 10, 3, 4, 7, 14, 4, 6, 5, 9, 3]

FIRST = ["Ana", "Ben", "Chloe", "Dara", "Eli", "Farah", "Gus", "Hana", "Ivo", "Jun", "Kira", "Leo", "Mina", "Noor",
         "Omar", "Pia", "Quinn", "Rosa", "Sam", "Tara", "Uma", "Vik", "Wren", "Xena", "Yara", "Zed"]
LAST = ["Abel", "Brandt", "Costa", "Dunn", "Evers", "Falk", "Grau", "Holt", "Iyer", "Jansen", "Klein", "Lund"]
CITIES = ["Leeds", "Bristol", "Glasgow", "Cardiff", "York", "Bath", "Derby", "Hull"]

# Planted records that the scenarios refer to. Dates are relative to TODAY.
#   id, customer_id, days since order, status, days since delivery (or None), [(sku, qty)]
PLANTED_ORDERS = [
    (5001, 3, 16, "delivered", 12, [("GRD-HAND", 1)]),                    # refund: APPROVE
    (5002, 7, 52, "delivered", 45, [("DRP-V60", 1), ("FLT-V60", 2)]),     # refund: DENY, outside 30 days
    (5003, 11, 10, "delivered", 6, [("BEAN-ESP", 2)]),                    # refund: DENY, final sale
    (5004, 15, 14, "delivered", 9, [("GRD-ELEC", 1)]),                    # refund: ESCALATE, over 150
    (5005, 19, 20, "refunded", 15, [("SCL-BREW", 1)]),                    # refund: DENY, already refunded
    (5006, 23, 12, "shipped", None, [("KET-ELEC", 1)]),                   # late shipment
    (5007, 27, 3, "processing", None, [("PRS-FRENCH", 1), ("MUG-CER", 2)]),
    (5008, 31, 8, "delivered", 5, [("KET-GOOSE", 1), ("DRP-V60", 1)]),    # refund: APPROVE
    (5009, 35, 5, "cancelled", None, [("GRD-ELEC", 1)]),
]
#   id, customer_id, order_id, days ago, subject, body, expected priority, expected category
PLANTED_TICKETS = [
    (9001, 23, 5006, 1, "Where is my kettle?", "Order 5006 was shipped 12 days ago and still has not arrived. Tracking has not moved.", "P2", "shipping"),
    (9002, 3, 5001, 1, "Charged twice", "My card shows two payments of 89.00 for order 5001. Please refund one.", "P1", "billing"),
    (9003, 31, 5008, 2, "Kettle handle gets very hot", "The handle of the gooseneck kettle burned my hand slightly. Is this normal?", "P1", "product"),
    (9004, 11, 5003, 2, "Can I change my roast?", "I ordered the house espresso but would prefer a lighter roast next time. Any suggestions?", "P3", "product"),
    (9005, 15, 5004, 0, "Grinder arrived with cracked hopper", "The electric grinder from order 5004 arrived with a cracked hopper lid. Photos attached.", "P2", "product"),
    (9006, 40, None, 3, "Do you ship to Ireland?", "Hi, do you deliver to Dublin and what does it cost?", "P3", "shipping"),
    (9007, 7, 5002, 0, "Refund for dripper", "I would like to return the ceramic dripper from order 5002, I never used it.", "P3", "billing"),
    (9008, 27, 5007, 0, "Update delivery address", "Please change the address on order 5007 before it ships. New address: 4 Mill Lane, York.", "P3", "shipping"),
]

SCHEMA = """
CREATE TABLE customers(id INTEGER PRIMARY KEY, name TEXT, email TEXT, city TEXT, joined TEXT);
CREATE TABLE products(id INTEGER PRIMARY KEY, sku TEXT, name TEXT, category TEXT, price REAL, stock INTEGER,
                      lead_time_days INTEGER, final_sale INTEGER);
CREATE TABLE orders(id INTEGER PRIMARY KEY, customer_id INTEGER, order_date TEXT, status TEXT, delivered_date TEXT, total REAL);
CREATE TABLE order_items(order_id INTEGER, product_id INTEGER, qty INTEGER, unit_price REAL);
CREATE TABLE tickets(id INTEGER PRIMARY KEY, customer_id INTEGER, order_id INTEGER, created TEXT, subject TEXT, body TEXT,
                     status TEXT, priority TEXT, category TEXT, note TEXT);
"""


def build(path):
    if os.path.exists(path):
        os.remove(path)
    rnd = random.Random(7)
    db = sqlite3.connect(path)
    db.executescript(SCHEMA)
    for i in range(1, 61):
        f, l = rnd.choice(FIRST), rnd.choice(LAST)
        db.execute("INSERT INTO customers VALUES(?,?,?,?,?)",
                   (i, f"{f} {l}", f"{f}.{l}{i}@example.com".lower(), rnd.choice(CITIES),
                    str(TODAY - dt.timedelta(days=rnd.randint(30, 700)))))
    for i, p in enumerate(PRODUCTS, 1):
        db.execute("INSERT INTO products VALUES(?,?,?,?,?,?,?,?)", (i,) + p)
    sku_id = {p[0]: i for i, p in enumerate(PRODUCTS, 1)}
    price = {i: p[3] for i, p in enumerate(PRODUCTS, 1)}

    def add_order(oid, cid, days_ago, status, deliv_ago, items):
        total = round(sum(price[pid] * q for pid, q in items), 2)
        db.execute("INSERT INTO orders VALUES(?,?,?,?,?,?)",
                   (oid, cid, str(TODAY - dt.timedelta(days=days_ago)), status,
                    str(TODAY - dt.timedelta(days=deliv_ago)) if deliv_ago is not None else None, total))
        for pid, q in items:
            db.execute("INSERT INTO order_items VALUES(?,?,?,?)", (oid, pid, q, price[pid]))

    oid = 1000
    for days_ago in range(74, 0, -1):          # 1 Sep .. 12 Nov
        day = TODAY - dt.timedelta(days=days_ago)
        n = rnd.randint(3, 7) + (2 if day.weekday() >= 5 else 0)
        for _ in range(n):
            oid += 1
            items = {}
            for _ in range(rnd.choice([1, 1, 1, 2, 2, 3])):
                pid = rnd.choices(range(1, len(PRODUCTS) + 1), WEIGHTS)[0]
                items[pid] = items.get(pid, 0) + rnd.choice([1, 1, 1, 2])
            r = rnd.random()
            if days_ago <= 2: status, deliv = "processing", None
            elif days_ago <= 5: status, deliv = "shipped", None
            elif r < 0.05: status, deliv = "cancelled", None
            elif r < 0.11: status, deliv = "refunded", days_ago - 4
            else: status, deliv = "delivered", max(days_ago - rnd.randint(3, 5), 0)
            add_order(oid, rnd.randint(1, 60), days_ago, status, deliv, sorted(items.items()))
    for o in PLANTED_ORDERS:
        add_order(o[0], o[1], o[2], o[3], o[4], [(sku_id[s], q) for s, q in o[5]])
    for t in PLANTED_TICKETS:
        db.execute("INSERT INTO tickets VALUES(?,?,?,?,?,?,'open',NULL,NULL,NULL)",
                   (t[0], t[1], t[2], str(TODAY - dt.timedelta(days=t[3])), t[4], t[5]))
    db.commit(); db.close()


# ---------------------------------------------------------------- MCP server

def _obj(props, required=()):
    return {"type": "object", "properties": props, "required": list(required)}


TOOLS = [
    {"name": "list_tables", "description": "List the tables in the shop database with their columns.",
     "inputSchema": _obj({})},
    {"name": "run_sql", "description": "Run one read-only SQLite SELECT statement on the shop database. Returns up to 50 rows as JSON.",
     "inputSchema": _obj({"query": {"type": "string", "description": "A single SELECT statement"}}, ["query"])},
    {"name": "get_order", "description": "Get one order with its customer, line items and delivery dates.",
     "inputSchema": _obj({"order_id": {"type": "integer"}}, ["order_id"])},
    {"name": "search_tickets", "description": "List support tickets, optionally filtered by status (open, pending, closed) and a text query.",
     "inputSchema": _obj({"status": {"type": "string"}, "query": {"type": "string"}})},
    {"name": "update_ticket", "description": "Set the priority (P1, P2, P3), category (billing, shipping, product, other), status or an internal note on a ticket.",
     "inputSchema": _obj({"ticket_id": {"type": "integer"}, "priority": {"type": "string"}, "category": {"type": "string"},
                          "status": {"type": "string"}, "note": {"type": "string"}}, ["ticket_id"])},
]


def _rows(cur):
    cols = [c[0] for c in cur.description]
    return [dict(zip(cols, r)) for r in cur.fetchmany(50)]


def call_tool(db, name, a):
    if name == "list_tables":
        out = {}
        for (t,) in db.execute("SELECT name FROM sqlite_master WHERE type='table'"):
            out[t] = [r[1] for r in db.execute(f"PRAGMA table_info({t})")]
        return out
    if name == "run_sql":
        q = (a.get("query") or "").strip().rstrip(";")
        if not q.lower().startswith(("select", "with")) or ";" in q:
            raise ValueError("only a single SELECT statement is allowed")
        return _rows(db.execute(q))
    if name == "get_order":
        o = _rows(db.execute("SELECT o.*, c.name AS customer_name, c.email AS customer_email FROM orders o "
                             "JOIN customers c ON c.id=o.customer_id WHERE o.id=?", (int(a["order_id"]),)))
        if not o: raise ValueError(f"order {a['order_id']} not found")
        o[0]["items"] = _rows(db.execute(
            "SELECT p.sku, p.name, p.category, p.final_sale, i.qty, i.unit_price FROM order_items i "
            "JOIN products p ON p.id=i.product_id WHERE i.order_id=?", (int(a["order_id"]),)))
        return o[0]
    if name == "search_tickets":
        q, args = "SELECT * FROM tickets WHERE 1=1", []
        if a.get("status"): q += " AND status=?"; args.append(a["status"])
        if a.get("query"): q += " AND (subject LIKE ? OR body LIKE ?)"; args += [f"%{a['query']}%"] * 2
        return _rows(db.execute(q + " ORDER BY id", args))
    if name == "update_ticket":
        tid = int(a["ticket_id"])
        if not db.execute("SELECT 1 FROM tickets WHERE id=?", (tid,)).fetchone():
            raise ValueError(f"ticket {tid} not found")
        if a.get("priority") and a["priority"] not in ("P1", "P2", "P3"):
            raise ValueError("priority must be P1, P2 or P3")
        if a.get("category") and a["category"] not in ("billing", "shipping", "product", "other"):
            raise ValueError("category must be billing, shipping, product or other")
        for f in ("priority", "category", "status", "note"):
            if a.get(f): db.execute(f"UPDATE tickets SET {f}=? WHERE id=?", (a[f], tid))
        db.commit()
        return _rows(db.execute("SELECT id, status, priority, category, note FROM tickets WHERE id=?", (tid,)))[0]
    raise ValueError(f"unknown tool {name}")


def serve(path):
    db = sqlite3.connect(path)
    for line in sys.stdin:
        line = line.strip()
        if not line: continue
        msg = json.loads(line)
        if "id" not in msg: continue                      # notification
        m, res, err = msg.get("method"), None, None
        if m == "initialize":
            res = {"protocolVersion": msg["params"].get("protocolVersion", "2025-06-18"),
                   "capabilities": {"tools": {}}, "serverInfo": {"name": "shop", "version": "0.1"}}
        elif m == "tools/list":
            res = {"tools": TOOLS}
        elif m == "tools/call":
            try:
                out = call_tool(db, msg["params"]["name"], msg["params"].get("arguments") or {})
                res = {"content": [{"type": "text", "text": json.dumps(out, default=str)}], "isError": False}
            except Exception as e:
                res = {"content": [{"type": "text", "text": f"Error: {e}"}], "isError": True}
        elif m == "ping":
            res = {}
        else:
            err = {"code": -32601, "message": f"method not found: {m}"}
        out = {"jsonrpc": "2.0", "id": msg["id"]}
        out.update({"error": err} if err else {"result": res})
        sys.stdout.write(json.dumps(out) + "\n"); sys.stdout.flush()


if __name__ == "__main__":
    {"build": build, "serve": serve}[sys.argv[1]](sys.argv[2])
