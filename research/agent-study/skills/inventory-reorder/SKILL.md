---
name: inventory-reorder
description: Work out which products need reordering and how many. Use for stock, reorder or supplier-order questions.
---
# Inventory reorder

For each product:
- `avg_daily` = units sold in the last 28 days / 28 (orders that are not cancelled; the 28 days end yesterday).
- `reorder_point` = avg_daily × lead_time_days + avg_daily × 7 (seven days of safety stock).
- Reorder when `stock` <= `reorder_point`.
- `order_qty` = 28 days of sales (avg_daily × 28), rounded up to the next multiple of 6.

Steps:
1. Get sales and stock with `shop__run_sql` (join `order_items`, `orders`, `products`).
2. Reply with a table: sku, stock, avg_daily, reorder_point, order_qty. List only products that need reordering, lowest cover first.
