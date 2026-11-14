"""Scripted sessions for the agent study: 32 sessions, 100 user turns, 3 people.

Every session carries the labels it was *designed* to have (domain, task type, the
skill and MCP servers a good agent would use) and every turn carries the act it was
written as. Those are the ground truth for the Prism part of the study. Where an
answer can be verified, the turn also carries checks against the database.

    python3 scenarios.py        # print a summary and write data/scenarios.json
"""
import datetime as dt, json, math, os, sqlite3, tempfile
import shop_mcp

HERE = os.path.dirname(os.path.abspath(__file__))
TODAY = shop_mcp.TODAY

USERS = {
    "maya": "Maya, support lead",
    "arjun": "Arjun, operations",
    "lena": "Lena, founder",
}

# ---------------------------------------------------------------- ground truth from the database

_tmp = os.path.join(tempfile.mkdtemp(), "truth.db")
shop_mcp.build(_tmp)
_db = sqlite3.connect(_tmp)


def q1(sql, *a):
    return _db.execute(sql, a).fetchone()


LIVE = "status NOT IN ('cancelled','refunded')"


def period(a, b):
    net, n = q1(f"SELECT round(sum(total),2), count(*) FROM orders WHERE order_date BETWEEN ? AND ? AND {LIVE}", a, b)
    return {"net": net, "orders": n, "aov": round(net / n, 2)}


def week(monday):
    return period(monday, str(dt.date.fromisoformat(monday) + dt.timedelta(days=6)))


W_LAST, W_PREV, W_OCT19, W_OCT12 = week("2026-11-02"), week("2026-10-26"), week("2026-10-19"), week("2026-10-12")
OCT = period("2026-10-01", "2026-10-31")
OCT_ALL = q1("SELECT count(*) FROM orders WHERE order_date BETWEEN '2026-10-01' AND '2026-10-31'")[0]
OCT_CANC = q1("SELECT count(*) FROM orders WHERE order_date BETWEEN '2026-10-01' AND '2026-10-31' AND status='cancelled'")[0]
OCT_REF = q1("SELECT count(*) FROM orders WHERE order_date BETWEEN '2026-10-01' AND '2026-10-31' AND status='refunded'")[0]
OCT_REF_RATE = round(100 * OCT_REF / (OCT_ALL - OCT_CANC), 1)
OCT_BAD_SHARE = round(100 * (OCT_CANC + OCT_REF) / OCT_ALL, 1)


def reorder():
    a, b = str(TODAY - dt.timedelta(days=28)), str(TODAY - dt.timedelta(days=1))
    out = {}
    for sku, stock, lead, units in _db.execute(
            "SELECT p.sku, p.stock, p.lead_time_days, coalesce(sum(i.qty),0) FROM products p "
            "LEFT JOIN order_items i ON i.product_id=p.id AND i.order_id IN "
            "(SELECT id FROM orders WHERE order_date BETWEEN ? AND ? AND status!='cancelled') GROUP BY p.id", (a, b)):
        avg = units / 28
        rop = avg * lead + avg * 7
        if stock <= rop:
            out[sku] = {"stock": stock, "rop": round(rop, 1), "qty": int(math.ceil(avg * 28 / 6) * 6)}
    return out


REORDER = reorder()
TOP_UNITS = q1(f"SELECT p.sku FROM order_items i JOIN products p ON p.id=i.product_id JOIN orders o ON o.id=i.order_id "
               f"WHERE {LIVE} GROUP BY p.sku ORDER BY sum(i.qty) DESC LIMIT 1")[0]
TOP_REV = q1(f"SELECT p.sku, p.name FROM order_items i JOIN products p ON p.id=i.product_id JOIN orders o ON o.id=i.order_id "
             f"WHERE {LIVE} GROUP BY p.sku ORDER BY sum(i.qty*i.unit_price) DESC LIMIT 1")
CITY_CUST = q1("SELECT city FROM customers GROUP BY city ORDER BY count(*) DESC LIMIT 1")[0]
CITY_REV = q1(f"SELECT c.city FROM orders o JOIN customers c ON c.id=o.customer_id WHERE {LIVE} GROUP BY c.city ORDER BY sum(total) DESC LIMIT 1")[0]
TOP_CUST = q1(f"SELECT c.name, c.email FROM orders o JOIN customers c ON c.id=o.customer_id WHERE {LIVE} GROUP BY c.id ORDER BY sum(total) DESC LIMIT 1")
HAND_28 = q1("SELECT sum(i.qty) FROM order_items i JOIN orders o ON o.id=i.order_id JOIN products p ON p.id=i.product_id "
             "WHERE p.sku='GRD-HAND' AND o.status!='cancelled' AND o.order_date BETWEEN ? AND ?",
             str(TODAY - dt.timedelta(days=28)), str(TODAY - dt.timedelta(days=1)))[0]
HAND_28_ALL = q1("SELECT sum(i.qty) FROM order_items i JOIN orders o ON o.id=i.order_id JOIN products p ON p.id=i.product_id "
                 "WHERE p.sku='GRD-HAND' AND o.order_date BETWEEN ?  AND ?",
                 str(TODAY - dt.timedelta(days=28)), str(TODAY - dt.timedelta(days=1)))[0]   # the turn does not say whether cancelled orders count
EMAIL_31 = q1("SELECT email FROM customers WHERE id=31")[0]
TRIAGE = {t[0]: {"priority": t[6], "category": t[7]} for t in shop_mcp.PLANTED_TICKETS}

SIGN = ("has", ["Kettle & Crumb Support"])
NO_UNF = ("not", ["unfortunately"])

# ---------------------------------------------------------------- sessions
# session: (id, user, date, hour, domain, task_type, skill, servers, turns)
# turn:    (act, text, [checks])
# acts:    request | refinement | correction | feedback_relay | question | reexplain
# checks:  ("num", x) reply holds a number within 0.5% of x (or of any value in a list)     ("has", [..]) all substrings present
#          ("any", [..]) at least one present                    ("not", [..]) none present
#          ("ticket", id, {field: value}) database state         ("tickets", {id: {..}}, min_ok) bulk database state
#          ("note", id) ticket has a note                        ("file", path) file exists in the workspace

S = [
 ("M01", "maya", "2026-11-02", 9, "support", "decide", "refund-eligibility", ["shop"], [
    ("request", "Customer on order 5001 wants to send the hand grinder back. Can we refund it?", [("has", ["APPROVE"])]),
    ("request", "Draft the reply to them.", [SIGN, NO_UNF]),
    ("refinement", "Shorter. Two sentences at most before the sign-off.", [SIGN])]),
 ("M02", "maya", "2026-11-02", 11, "support", "decide", "refund-eligibility", ["shop"], [
    ("request", "Can order 5002 be refunded? The customer says the dripper is unused.", [("has", ["DENY"])]),
    ("question", "Why do we count 30 days from delivery and not from the order date?", []),
    ("request", "And 5003?", [("has", ["DENY"])]),
    ("request", "Write a reply for 5003 that explains it kindly.", [SIGN, NO_UNF])]),
 ("M03", "maya", "2026-11-03", 10, "support", "decide", "refund-eligibility", ["shop"], [
    ("request", "Refund check on order 5004 please. The grinder arrived with a cracked hopper.", [("has", ["ESCALATE"])]),
    ("correction", "No, don't approve or deny that one yourself. Anything over 150 comes to me. Just tell me what the rule says for this order.", [("has", ["ESCALATE"])]),
    ("request", "OK. Add a note on ticket 9005 that it is escalated to me.", [("note", 9005)])]),
 ("M04", "maya", "2026-11-04", 9, "support", "triage", "ticket-triage", ["shop"], [
    ("request", "Triage the open tickets.", [("tickets", TRIAGE, 6)]),
    ("question", "Which ones are P1 and why?", [("has", ["9002", "9003"])]),
    ("refinement", "Give me that as a short list I can paste into the team chat.", []),
    ("request", "Draft a reply for the double charge one.", [SIGN, NO_UNF])]),
 ("M05", "maya", "2026-11-04", 14, "support", "lookup", None, ["shop", "filesystem"], [
    ("request", "What's the status of order 5006?", [("has", ["shipped"])]),
    ("request", "When was it placed and what's in it?", [("any", ["KET-ELEC", "Electric Pour-Over Kettle"]), ("any", ["2026-11-01", "1 November", "November 1", "Nov 1"])]),
    ("question", "Is that late by our own shipping rules? They are in docs/shipping.md.", [("any", ["late", "yes"])]),
    ("request", "Draft a reply to the customer on ticket 9001.", [SIGN, NO_UNF])]),
 ("M06", "maya", "2026-11-05", 10, "support", "draft", "customer-reply", ["shop"], [
    ("request", "Order 5005: the customer asks for a refund on the brew scale.", [("any", ["DENY", "already", "refunded"])]),
    ("feedback_relay", "The customer replied: 'I never got the money back, my bank shows nothing.' What do we do?", []),
    ("reexplain", "As I said, this is order 5005, the brew scale, already marked refunded on our side. I need wording for the customer, not another eligibility check.", [SIGN, NO_UNF])]),
 ("M07", "maya", "2026-11-05", 15, "support", "lookup", "customer-reply", ["filesystem", "shop"], [
    ("request", "Do we ship to Ireland, and what does it cost?", [("has", ["9.50"])]),
    ("request", "Reply to ticket 9006 with that.", [SIGN]),
    ("request", "Close the ticket after.", [("ticket", 9006, {"status": "closed"})])]),
 ("M08", "maya", "2026-11-06", 9, "support", "lookup", None, ["shop"], [
    ("request", "How many open tickets do we have right now?", [("num", 8)])]),
 ("M09", "maya", "2026-11-09", 10, "support", "decide", "refund-eligibility", ["shop"], [
    ("request", "Is order 5008 refundable? They want to return the kettle only.", [("has", ["APPROVE"])]),
    ("correction", "You're mixing it up with another order. 5008 is the gooseneck kettle plus a dripper, delivered 5 days ago. Check again.", [("any", ["APPROVE", "refundable", "eligible"])]),
    ("request", "Good. Draft the reply.", [SIGN, NO_UNF])]),
 ("M10", "maya", "2026-11-10", 11, "support", "lookup", "customer-reply", ["shop"], [
    ("request", "Ticket 9008 asks for an address change on order 5007. Can we still do that?", [("has", ["processing"])]),
    ("request", "Set the ticket to P3, shipping, and add the new address as a note.", [("ticket", 9008, {"priority": "P3", "category": "shipping"}), ("note", 9008)]),
    ("request", "Reply to the customer confirming the change.", [SIGN])]),
 ("M11", "maya", "2026-11-10", 16, "writing", "draft", None, [], [
    ("request", "I keep writing the same 'where is my order' reply. Give me 3 template variants I can reuse.", []),
    ("refinement", "Make the second one less formal.", []),
    ("question", "Which one would you pick for a customer who has already written twice?", [])]),
 ("M12", "maya", "2026-11-11", 9, "support", "lookup", None, ["shop"], [
    ("request", "Find the ticket about the hot kettle handle and give me the customer's email.", [("has", [EMAIL_31])]),
    ("request", "Mark it P1, product.", [("ticket", 9003, {"priority": "P1", "category": "product"})])]),
 ("M13", "maya", "2026-11-12", 14, "support", "triage", "ticket-triage", ["shop"], [
    ("request", "Triage ticket 9007.", [("ticket", 9007, {"priority": "P3", "category": "billing"})]),
    ("feedback_relay", "The customer wrote back: 'the dripper box is unopened, why can't I return it?' Check whether order 5002 is eligible.", [("has", ["DENY"])]),
    ("request", "Draft the reply.", [SIGN, NO_UNF])]),

 ("A01", "arjun", "2026-11-09", 8, "operations", "report", "weekly-sales-report", ["shop", "filesystem"], [
    ("request", "Weekly sales report for last week please.", [("num", W_LAST["net"])]),
    ("request", "Save it.", [("file", "out/sales-2026-11-02.md")]),
    ("question", "How does that compare with the week before?", [("num", W_PREV["net"])])]),
 ("A02", "arjun", "2026-11-02", 8, "operations", "report", "weekly-sales-report", ["shop", "filesystem"], [
    ("request", "What was revenue the week of 26 October?", [("num", W_PREV["net"])]),
    ("correction", "That doesn't look like our net figure. Cancelled and refunded orders must be excluded. Redo it.", [("num", W_PREV["net"])]),
    ("refinement", "Add AOV and the top 3 products.", [("num", W_PREV["aov"])]),
    ("request", "File it in out/.", [("file", "out/sales-2026-10-26.md")])]),
 ("A03", "arjun", "2026-11-03", 15, "operations", "analysis", "inventory-reorder", ["shop", "filesystem"], [
    ("request", "What do we need to reorder this week?", [("has", sorted(REORDER))]),
    ("question", "Why is DRP-V60 on the list when we have 14 in stock?", []),
    ("refinement", "Group them by supplier. The supplier list is in docs/suppliers.md.", [("any", ["Fellow", "Hario", "Timemore"])]),
    ("request", "Draft the order email to Fellow Wholesale.", [])]),
 ("A04", "arjun", "2026-11-04", 16, "operations", "analysis", None, ["shop"], [
    ("request", "How many orders were cancelled in October?", [("num", OCT_CANC)]),
    ("request", "And refunded?", [("num", OCT_REF)]),
    ("request", "What share of October orders is that together?", [("num", OCT_BAD_SHARE)]),
    ("feedback_relay", "Lena says the refund count looks high to her. Show me the refunded October orders by product so we can check.", [])]),
 ("A05", "arjun", "2026-11-05", 17, "operations", "analysis", None, ["shop"], [
    ("request", "Give me a SQL query I can paste into our BI tool for daily net revenue for the last 14 days.", [("any", ["SELECT", "select"])]),
    ("feedback_relay", "It fails with: 'no such column: order_total'. Fix it.", [("any", ["SELECT", "select"])]),
    ("feedback_relay", "Now it runs, but the BI tool says 'ambiguous column name: id'.", []),
    ("request", "Thanks. Run it here and tell me the best day.", [])]),
 ("A06", "arjun", "2026-11-06", 15, "operations", "analysis", None, ["shop"], [
    ("request", "Which city has the most customers?", [("has", [CITY_CUST])]),
    ("request", "And by revenue?", [("has", [CITY_REV])]),
    ("request", "Top 5 customers by lifetime spend, with emails.", [("has", [TOP_CUST[1]])])]),
 ("A07", "arjun", "2026-11-10", 15, "operations", "analysis", "inventory-reorder", ["memory", "shop"], [
    ("request", "Remember this: Timemore told us today that the GRD-ELEC lead time is now 42 days, not 35.", []),
    ("request", "What do we have stored about suppliers?", [("has", ["42"])]),
    ("question", "Does that change the reorder point for GRD-ELEC?", [])]),
 ("A08", "arjun", "2026-11-11", 16, "operations", "report", "weekly-sales-report", ["shop", "filesystem"], [
    ("request", "Sales summary for October: net revenue, orders and AOV.", [("num", OCT["net"])]),
    ("refinement", "Break it down by week.", []),
    ("refinement", "Only Monday-to-Sunday weeks that fall fully inside October.", [("num", W_OCT19["net"])]),
    ("request", "Save that as out/october.md", [("file", "out/october.md")])]),
 ("A09", "arjun", "2026-11-12", 15, "operations", "lookup", None, ["shop"], [
    ("request", "What's the current stock of GRD-HAND and SCL-BREW?", [("num", 6), ("num", 8), ("has", ["GRD-HAND", "SCL-BREW"])])]),
 ("A10", "arjun", "2026-11-12", 17, "operations", "analysis", "inventory-reorder", ["shop"], [
    ("request", "Reorder check for grinders only.", [("has", [s for s in sorted(REORDER) if s.startswith("GRD")])]),
    ("reexplain", "Again: we use 7 days of safety stock on top of lead time, and the 28-day average. Please use our formula, not a generic one.", []),
    ("request", "What quantity for GRD-HAND then?", [("num", REORDER.get("GRD-HAND", {}).get("qty", -1))])]),
 ("A11", "arjun", "2026-11-13", 8, "operations", "report", "weekly-sales-report", ["shop", "filesystem"], [
    ("request", "Weekly sales report for the week of 19 October.", [("num", W_OCT19["net"])]),
    ("request", "Save it.", [("file", "out/sales-2026-10-19.md")]),
    ("request", "Same for the week of 12 October.", [("num", W_OCT12["net"])])]),

 ("L01", "lena", "2026-11-03", 21, "strategy", "advise", "price-change-memo", ["shop", "filesystem"], [
    ("question", "I'm thinking of raising the hand grinder from 89 to 95. What should I look at first?", []),
    ("request", "Pull the last 28 days of units and revenue for it.", [("num", [HAND_28, HAND_28_ALL])]),
    ("request", "Write the price change memo.", [("file", "out/price-memo-GRD-HAND.md")]),
    ("refinement", "Tighten the risk section to two sentences.", [])]),
 ("L02", "lena", "2026-11-05", 22, "strategy", "advise", None, [], [
    ("question", "Should we offer free shipping to Ireland? Talk me through how to think about it.", []),
    ("question", "What would you want to know before deciding?", []),
    ("request", "How many orders did we send to Ireland last month?", [("any", ["no country", "not record", "doesn't", "does not", "cannot", "can't", "no way", "not stored", "not available", "unable", "zero", "none", "no orders"])]),
    ("question", "OK, so what's the cheapest experiment to find out?", [])]),
 ("L03", "lena", "2026-11-08", 20, "operations", "lookup", "weekly-sales-report", ["shop"], [
    ("request", "What did we make last week?", [("num", W_LAST["net"])])]),
 ("L04", "lena", "2026-11-08", 21, "writing", "draft", None, ["filesystem"], [
    ("request", "Rewrite the product description for the Gooseneck Kettle 0.9L. Two sentences, in our brand voice (docs/brand-voice.md).", [("not", ["!"])]),
    ("refinement", "Less salesy.", [("not", ["!"])]),
    ("refinement", "British spelling, and drop the exclamation mark if there is one.", [("not", ["!"])])]),
 ("L05", "lena", "2026-11-09", 21, "strategy", "report", "weekly-sales-report", ["shop"], [
    ("request", "I need three numbers for the investor update: October net revenue, number of orders, and refund rate.", [("num", OCT["net"])]),
    ("question", "How are you defining refund rate?", []),
    ("correction", "No. Refund rate should be refunded orders divided by all non-cancelled orders, not by all orders.", [("num", OCT_REF_RATE)]),
    ("request", "Write it as one paragraph.", [("num", OCT["net"])])]),
 ("L06", "lena", "2026-11-11", 20, "strategy", "analysis", None, ["shop"], [
    ("request", "What are our best sellers?", [("has", [TOP_UNITS])]),
    ("refinement", "By revenue, not units.", [("any", [TOP_REV[0], TOP_REV[1]])]),
    ("question", "Anything surprising in there?", [])]),
 ("L07", "lena", "2026-11-12", 22, "strategy", "advise", None, ["shop"], [
    ("question", "We're three people. What should I automate first: triage, the weekly report or reordering?", []),
    ("request", "How many tickets did we get in the last week?", [("num", 8)]),
    ("request", "Fine. Draft a one-week plan for trying the triage automation.", []),
    ("refinement", "Make it a checklist.", [])]),
 ("L08", "lena", "2026-11-13", 20, "writing", "draft", "customer-reply", ["shop"], [
    ("request", "Who are our top 3 customers by spend?", [("has", [TOP_CUST[0]])]),
    ("request", "Draft a thank-you note to the first one.", [SIGN])]),
]


def sessions():
    out = []
    for sid, user, date, hour, domain, task, skill, servers, turns in S:
        acts = [t[0] for t in turns]
        out.append({"session_id": sid, "user": user, "role": USERS[user],
                    "sim_start": f"{date}T{hour:02d}:{(int(sid[1:]) * 7) % 50:02d}:00",
                    "designed": {"domain": domain, "task_type": task, "skill": skill, "servers": servers,
                                 "corrections": acts.count("correction"), "feedback_relays": acts.count("feedback_relay"),
                                 "refinements": acts.count("refinement"), "questions": acts.count("question"),
                                 "reexplained_turns": [i + 1 for i, a in enumerate(acts) if a == "reexplain"]},
                    "turns": [{"act": a, "text": t, "checks": c} for a, t, c in turns]})
    return out


if __name__ == "__main__":
    ss = sessions()
    os.makedirs(os.path.join(HERE, "data"), exist_ok=True)
    json.dump(ss, open(os.path.join(HERE, "data", "scenarios.json"), "w"), indent=1)
    print(len(ss), "sessions,", sum(len(s["turns"]) for s in ss), "turns,",
          sum(1 for s in ss for t in s["turns"] if t["checks"]), "turns with checks")
    print("last week", W_LAST, "| prev", W_PREV, "| oct", OCT, "refund rate", OCT_REF_RATE, "bad share", OCT_BAD_SHARE)
    print("reorder", REORDER)
    print("top units", TOP_UNITS, "top rev", TOP_REV, "cities", CITY_CUST, CITY_REV, "top cust", TOP_CUST, "hand28", HAND_28)
