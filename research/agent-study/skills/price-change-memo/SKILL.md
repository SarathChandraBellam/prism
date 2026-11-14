---
name: price-change-memo
description: Write the one-page memo required before any product price change. Use when a price change is proposed.
---
# Price change memo

Write a memo with exactly these headings:
`## Proposal`, `## Evidence` (units and revenue for the last 28 days from the database), `## Risk`, `## Decision needed by`.
Keep it under 200 words. Save it with `filesystem__write_file` to `out/price-memo-<sku>.md`.
