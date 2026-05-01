# Grafana Assistant Prompts — OrderService Demo

Copy-paste these prompts in order during the live demo.
Each prompt builds on the previous findings to guide the investigation.

---

## Prompt 1 — Initial Metrics Investigation

```
The orderservice running in Kubernetes is showing high latency.
Customers are reporting that order pages take more than 2 seconds to load.

Can you investigate using the Prometheus datasource?
- Show me the p95 request latency for the orderservice over the last 30 minutes
- Show the request rate and error rate broken down by endpoint
- Identify which specific endpoint is the slowest

Use the metric: orderservice_request_duration_seconds_bucket
```

**Expected outcome**: Assistant shows p95 ~1.8s on `/orders` endpoint, near-zero errors.

---

## Prompt 2 — Trace Analysis

```
The p95 latency on the GET /orders/{order_id} endpoint is around 1.8 seconds,
which is 9x higher than the expected 200ms SLA.

Can you look at the distributed traces in Tempo for the orderservice?
- Find the slowest traces from the last 15 minutes
- Show me the span breakdown: what child operations are happening inside each request?
- Count how many db.query spans appear per parent trace

Service name is: orderservice
```

**Expected outcome**: Assistant shows waterfall with 1 parent + 8 sequential `db.query` spans at 200ms each.

---

## Prompt 3 — Log Correlation

```
The traces show that each GET /orders/{order_id} request contains
8 sequential db.query spans, each taking ~200ms.
This suggests the code may be querying the database one item at a time.

Can you check the Loki logs for the orderservice to confirm this?
- Filter logs from namespace=orderservice over the last 15 minutes
- Look for log entries with event="fetch_item" or messages about fetching items
- Show the pattern: how many "Fetching item X of N" messages appear per order request?

LogQL hint: {namespace="orderservice"} | json | event="fetch_item"
```

**Expected outcome**: Logs show `"Fetching item 1 of 8"`, `"Fetching item 2 of 8"` ... confirming the loop.

---

## Prompt 4 — Root Cause Analysis + PR Generation

```
Based on the full investigation of the orderservice:

FINDINGS:
- p95 latency: ~1.8s (SLA is 200ms) — 9x over budget
- Traces: every /orders/{order_id} request has 8 sequential db.query spans at ~200ms each
- Logs: confirm a per-item loop: "Fetching item 1 of 8", "Fetching item 2 of 8", etc.
- DB query metric orderservice_db_queries_total{query_type="single"} is firing 8x per request

ROOT CAUSE: Classic N+1 query problem.
The code in app/main.py fetches each order item with an individual database query
inside a for-loop, instead of using a single batch query.

THE FIX: Replace the per-item loop with a single call to db_query_items_batch(item_ids).
The function db_query_items_batch() already exists in the codebase and executes
a single SQL IN-clause query that returns all items at once.

In app/main.py, the buggy section is inside the `if BUG_ENABLED:` block:
- REMOVE: the for-loop that calls db_query_single_item(item_id) for each item
- REPLACE WITH: items = await db_query_items_batch(item_ids)

Can you create a GitHub pull request on https://github.com/albert0fg/grafana-demo-orderservice
with this fix? The PR should:
1. Change the BUG_ENABLED default to False in the code
2. Replace the N+1 loop with the batch query call
3. Add a clear PR description explaining the root cause and expected improvement
```

**Expected outcome**: Grafana Assistant creates a PR with the code fix.

---

## Prompt 5 — Post-Fix Validation

```
We just deployed the fix for the N+1 query bug to the orderservice.
The deployment changed BUG_ENABLED from true to false,
so the service now uses the batch query instead of the per-item loop.

Can you validate the improvement in Grafana Cloud?
- Compare p95 latency: last 15 minutes vs previous 30 minutes
- Show the DB query metric: orderservice_db_queries_total broken down by query_type
  (we should now see only "batch" queries, not "single" queries)
- Confirm error rate is back to baseline
- Calculate the latency improvement ratio (before vs after)
```

**Expected outcome**: p95 drops from ~1.8s to ~0.25s, batch queries replacing single queries.

---

## Bonus Prompt — Executive Summary

```
Can you generate an executive summary of the incident we just investigated?
Include:
- Service affected: orderservice
- Impact: latency degradation (p95 1.8s vs 200ms SLA)
- Root cause: N+1 query problem in the order items fetching logic
- Detection: Grafana Cloud metrics alert + Grafana Assistant investigation
- Time from alert to root cause identified: (calculate from the traces timestamps)
- Fix: replaced per-item DB queries with a single batch query
- Resolution: deployed fix, latency dropped to ~250ms (8x improvement)
- Tools used: Prometheus, Tempo, Loki, Grafana Assistant, GitHub PR

Format it as a 5-bullet incident summary suitable for a Slack post.
```
