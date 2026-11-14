---
name: ticket-triage
description: Triage support tickets by setting priority and category. Use when asked to triage, prioritise or sort open tickets.
---
# Ticket triage

Priority:
- **P1**: money taken wrongly (double charge, charged for a cancelled order) or a safety issue (burns, electrical, broken glass).
- **P2**: order not arrived more than 7 days after it shipped, or item arrived damaged or defective.
- **P3**: everything else (questions, address changes, return requests, advice).

Category: one of `billing`, `shipping`, `product`, `other`. Return and refund requests are `billing`.

Steps:
1. List tickets with `shop__search_tickets` (status `open`).
2. For every ticket in scope, call `shop__update_ticket` with `priority` and `category`. Triage is not done until the ticket is updated.
3. Reply with a table: ticket id, priority, category, one-line reason. List P1 first.
