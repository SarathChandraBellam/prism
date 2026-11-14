---
name: weekly-sales-report
description: Produce the weekly sales report with the shop's own metric definitions. Use for any weekly or period sales, revenue or top-product summary.
---
# Weekly sales report

Definitions (these differ from a naive sum, so always use them):
- A week runs **Monday to Sunday**, by `orders.order_date`.
- **Net revenue** = sum of `orders.total` where status is NOT `cancelled` and NOT `refunded`.
- **Orders** = count of those same orders. **AOV** = net revenue / orders.
- **Top products** = top 3 by units sold (`order_items.qty`) on those same orders.

Steps:
1. Work out the Monday and Sunday of the week asked for ("last week" is the most recent complete week).
2. Query with `shop__run_sql`.
3. Reply in this format:

```
## Weekly sales report: <monday> to <sunday>
Net revenue: <amount with 2 decimals>
Orders: <n>
AOV: <amount with 2 decimals>
Top products: <sku> (<units>), <sku> (<units>), <sku> (<units>)
```
4. If asked to save or file the report, write it with `filesystem__write_file` to `out/sales-<monday>.md`.
