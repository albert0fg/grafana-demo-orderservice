# Demo Script: From Alert to PR with Grafana Cloud + Grafana Assistant

**Duration**: ~15 minutes  
**Audience**: Engineering leaders, developers, platform engineers  
**Grafana Cloud URL**: https://albertito.grafana.net

---

## The Story

> "A new spike in customer complaints: checkout pages are slow. The engineering team 
> gets an alert. Instead of hours of manual digging, they open Grafana Cloud and let 
> Grafana Assistant guide the entire investigation — from first symptom to merged PR."

---

## Pre-Demo Setup (10 min before the demo)

```bash
# 1. Clone and deploy (with bug enabled)
git clone https://github.com/albert0fg/grafana-demo-orderservice
cd grafana-demo-orderservice
./deploy.sh

# 2. Wait ~5 minutes for metrics/traces to accumulate in Grafana Cloud
kubectl logs -n orderservice -l app=load-generator -f
# You should see: "GET /orders/1 -> 200 (1.823s)" — that's the bug in action

# 3. Open Grafana Cloud in browser: https://albertito.grafana.net
# 4. Optional: Pre-open the Explore tab with Grafana Assistant visible
```

---

## Act 1 — "Something is wrong" (2 min)

**[Screen: Grafana Cloud home page]**

> "Our SRE team just received an alert. The orderservice latency is way above threshold.  
> Let's open Grafana Cloud and start the investigation."

1. Navigate to **Explore → Grafana Assistant** (or the AI panel)
2. Show the **Kubernetes Monitoring** dashboard — point to:
   - High CPU/memory on orderservice pods
   - The pod is healthy but slow

**Talking point:**  
> "Everything looks green from a health perspective — pods are running, no crashes.  
> But customers are waiting 2 seconds for an order page that should load in 200ms."

---

## Act 2 — Grafana Assistant Investigates Metrics (3 min)

**[Screen: Grafana Assistant chat panel]**

Paste **Prompt 1** (from `GRAFANA_ASSISTANT_PROMPTS.md`):

> *"The orderservice in Kubernetes is showing high latency. Customers report checkout 
> is taking more than 2 seconds. Can you investigate using Prometheus metrics?  
> Show me the p95 latency and error rate for orderservice over the last 30 minutes."*

**What to expect from Grafana Assistant:**
- Runs PromQL: `histogram_quantile(0.95, rate(orderservice_request_duration_seconds_bucket[5m]))`
- Shows p95 ~1.8s vs expected <200ms
- Points out the `/orders` endpoint is the offender

**Talking point:**  
> "In seconds, Grafana Assistant wrote the PromQL, ran it, and confirmed exactly which  
> endpoint is slow. I didn't have to remember the metric names or query syntax."

---

## Act 3 — Tracing the Root Cause (4 min)

**[Screen: Grafana Assistant → switches to Tempo]**

Paste **Prompt 2** (from `GRAFANA_ASSISTANT_PROMPTS.md`):

> *"The p95 latency on /orders/{order_id} is ~1.8s. Can you look at the distributed 
> traces in Tempo for the orderservice and find the slowest recent traces?  
> I want to see what operations are happening inside each request."*

**What to expect:**
- Assistant queries Tempo for traces from `orderservice` with high duration
- Shows the trace waterfall: 1 parent span + **8 sequential `db.query` child spans**
- Each DB span is ~200ms → 8 × 200ms = 1.6s total

**[Dramatic moment — show the trace waterfall visually]**

> "Look at this. Every single order request is making **8 separate database calls**,  
> one after the other. This is the classic N+1 query problem."

Paste **Prompt 3** (from `GRAFANA_ASSISTANT_PROMPTS.md`):

> *"In the traces I can see 8 sequential db.query spans. Can you check the Loki logs  
> for the orderservice to confirm the pattern? Look for logs with event=fetch_item  
> in the last 15 minutes."*

**What to expect:**
- Logs show: `"Fetching item 1 of 8"`, `"Fetching item 2 of 8"` ... `"Fetching item 8 of 8"`
- Clear confirmation: the code loops over items one-by-one

**Talking point:**  
> "Metrics told us WHERE. Traces told us WHAT. Logs told us HOW.  
> All three signals point to the same root cause — and it took under 5 minutes."

---

## Act 4 — Grafana Assistant Generates the Fix (4 min)

**[Screen: Grafana Assistant — the magic moment]**

Paste **Prompt 4** (from `GRAFANA_ASSISTANT_PROMPTS.md`):

> *"Based on the investigation: p95 latency ~1.8s, traces showing 8 sequential db.query  
> spans, and logs confirming a per-item loop in the code. The root cause is an N+1  
> query bug. The fix is to replace the per-item loop with a single batch query using  
> db_query_items_batch(). Can you generate a GitHub pull request on  
> https://github.com/albert0fg/grafana-demo-orderservice that applies this fix  
> in app/main.py?"*

**What to expect:**
- Grafana Assistant generates a diff that:
  - Removes the `for idx, item_id in enumerate(item_ids):` loop
  - Replaces it with `items = await db_query_items_batch(item_ids)`
- Creates a GitHub PR with the fix

**Talking point:**  
> "From alert to pull request in under 10 minutes. No manual digging through  
> dashboards, no war room, no 'have you tried turning it off and on again.'  
> Grafana Assistant connected all the signals and proposed the exact code change."

---

## Act 5 — Validate the Fix (2 min)

**[Screen: Terminal + Grafana Cloud]**

```bash
# Apply the fix to the cluster (simulates PR merge + deploy)
./deploy.sh --fix
```

Wait 2-3 minutes, then go back to Grafana Assistant:

Paste **Prompt 5** (from `GRAFANA_ASSISTANT_PROMPTS.md`):

> *"We just deployed the fix (BUG_ENABLED=false). Can you check the current p95 latency  
> on orderservice and compare it to the previous 30 minutes?"*

**What to expect:**
- Latency drops from ~1.8s → ~0.25s  
- Error rate back to 0%
- DB queries: from `db_queries_total{query_type="single"}` to `{query_type="batch"}`

**Talking point:**  
> "This is the full loop: detect, investigate, fix, validate — all inside Grafana Cloud.  
> The developer never left the tool."

---

## Closing (1 min)

> "What you just saw is what we call **AI-assisted observability**. Grafana Assistant  
> doesn't replace your engineers — it makes them 10x faster. It knows your services,  
> your traces, your logs, and now it can suggest code fixes and open PRs.  
> This isn't the future. This is Grafana Cloud today."

---

## Teardown

```bash
./deploy.sh --teardown
```

---

## Backup: If Grafana Assistant is unavailable

Run manual queries in Explore:

```promql
# p95 latency
histogram_quantile(0.95, sum(rate(orderservice_request_duration_seconds_bucket[5m])) by (le, endpoint))

# Error rate
sum(rate(orderservice_requests_total{status_code=~"5.."}[5m])) by (endpoint)

# DB query count per type
sum(rate(orderservice_db_queries_total[5m])) by (query_type)
```

```logql
# Show N+1 log pattern
{namespace="orderservice"} | json | event="fetch_item"
```
