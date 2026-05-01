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

## Prompt 4 — Root Cause Analysis + PR via GitHub MCP

```
Based on the full investigation of the orderservice:

FINDINGS:
- p95 latency: ~1.8s (SLA is 200ms) — 9x over budget
- Traces: every /orders/{order_id} request has 8 sequential db.query spans at ~200ms each
- Logs: confirm a per-item loop: "Fetching item 1 of 8", "Fetching item 2 of 8", etc.
- DB query metric orderservice_db_queries_total{query_type="single"} is firing 8x per request

ROOT CAUSE: Classic N+1 query problem.
The code in app/main.py fetches each order item with an individual database query
inside a for-loop, instead of a single batch query.

Please use your GitHub MCP tool to create a pull request with the fix.
Follow these steps exactly:

STEP 1 — Create branch:
  repo owner: albert0fg
  repo name:  grafana-demo-orderservice
  new branch: fix/n-plus-one-query
  from branch: main

STEP 2 — Get the current file to obtain its SHA:
  path: app/main.py

STEP 3 — Update the file on the new branch with these two changes:

  CHANGE A — Fix the default value on line 16:
    FROM: BUG_ENABLED = os.getenv("BUG_ENABLED", "true").lower() == "true"
    TO:   BUG_ENABLED = os.getenv("BUG_ENABLED", "false").lower() == "true"

  CHANGE B — Replace the entire if/else block inside get_order() (lines 138–166):
    REMOVE this block:
        if BUG_ENABLED:
            # BUG: N+1 query problem — one DB call per item
            logger.info(json.dumps({
                "event": "fetch_order_start",
                "order_id": order_id,
                "item_count": len(item_ids),
                "query_mode": "n+1",
                "msg": f"Fetching order {order_id} — will execute {len(item_ids)} individual DB queries"
            }))
            for idx, item_id in enumerate(item_ids):
                logger.info(json.dumps({
                    "event": "fetch_item",
                    "order_id": order_id,
                    "item_id": item_id,
                    "progress": f"{idx + 1}/{len(item_ids)}",
                    "msg": f"Fetching item {idx + 1} of {len(item_ids)}: item_id={item_id}"
                }))
                item = await db_query_single_item(item_id)
                items.append(item)
        else:
            # FIX: single batch query
            logger.info(json.dumps({
                "event": "fetch_order_start",
                "order_id": order_id,
                "item_count": len(item_ids),
                "query_mode": "batch",
                "msg": f"Fetching order {order_id} — executing 1 batch DB query for {len(item_ids)} items"
            }))
            items = await db_query_items_batch(item_ids)

    REPLACE WITH:
        logger.info(json.dumps({
            "event": "fetch_order_start",
            "order_id": order_id,
            "item_count": len(item_ids),
            "query_mode": "batch",
            "msg": f"Fetching order {order_id} — executing 1 batch DB query for {len(item_ids)} items"
        }))
        items = await db_query_items_batch(item_ids)

  Commit message: "fix: replace N+1 item queries with single batch query"

STEP 4 — Create pull request:
  title: "fix(orderservice): replace N+1 queries with batch query — 8x latency improvement"
  base branch: main
  head branch: fix/n-plus-one-query
  body:
    ## Root Cause
    Grafana Assistant identified an N+1 query problem via distributed tracing.
    Each GET /orders/{id} request executed **8 individual SELECT queries** (one per item),
    causing p95 latency of ~1.8s against a 200ms SLA.

    ## Evidence from Grafana Cloud
    - **Prometheus**: `orderservice_request_duration_seconds` p95 = 1.8s
    - **Tempo**: 8 sequential `db.query` spans per trace, each ~200ms
    - **Loki**: logs confirming loop pattern — "Fetching item 1 of 8", "Fetching item 2 of 8"...

    ## Fix
    Replaced the per-item for-loop with a single `db_query_items_batch()` call
    that executes one `SELECT ... WHERE id IN (...)` query for all items at once.

    ## Expected Impact
    - p95 latency: 1.8s → ~250ms (8x improvement)
    - DB queries per request: 8 → 1
    - `orderservice_db_queries_total{query_type="single"}` drops to 0
```

**Expected outcome**: Grafana Assistant uses the GitHub MCP to create branch → commit → PR live.  
**PR URL**: https://github.com/albert0fg/grafana-demo-orderservice/pulls

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
