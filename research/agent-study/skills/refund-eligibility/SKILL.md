---
name: refund-eligibility
description: Decide whether an order can be refunded. Use whenever someone asks if an order or item can be returned or refunded.
---
# Refund eligibility

1. Fetch the order with `shop__get_order`.
2. Apply the rules in this order and stop at the first that matches:
   - Order status is `refunded` or `cancelled`: **DENY** (nothing left to refund).
   - Order status is not `delivered`: **DENY** (ask the customer to wait for delivery, or cancel instead).
   - Any item has `final_sale` = 1 (coffee is final sale): **DENY**.
   - More than 30 days between `delivered_date` and today: **DENY**.
   - Order total is over 150.00: **ESCALATE** to the support lead, even when otherwise eligible.
   - Otherwise: **APPROVE**.
3. Reply with the first line exactly `DECISION: APPROVE`, `DECISION: DENY` or `DECISION: ESCALATE`,
   then one sentence with the rule that decided it and the dates or amounts used.

Never issue the refund yourself. This skill only decides.
