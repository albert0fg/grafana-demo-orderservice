# Grafana Cloud Demo — OrderService

High-impact demo: Grafana Assistant investigates a production performance bug
and generates a GitHub PR to fix it — end to end, inside Grafana Cloud.

## The Scenario

The `orderservice` has an N+1 query bug: each request for an order makes 8
individual database calls instead of 1 batch query. This causes:
- p95 latency of ~1.8s (SLA is 200ms)
- Full observability signal across metrics, traces, and logs

Grafana Assistant identifies the root cause from the telemetry and opens a PR.

## Quick Start

```bash
# Deploy with bug enabled
./deploy.sh

# After the demo — apply the fix
./deploy.sh --fix

# Teardown
./deploy.sh --teardown
```

## Demo Guide

See [`demo/DEMO_SCRIPT.md`](demo/DEMO_SCRIPT.md) for the full step-by-step demo.  
See [`demo/GRAFANA_ASSISTANT_PROMPTS.md`](demo/GRAFANA_ASSISTANT_PROMPTS.md) for copy-paste prompts.

## Architecture

```
load-generator → orderservice → (simulated PostgreSQL with sleep())
                      ↓
              OTLP (gRPC :4317)
                      ↓
           Grafana Alloy Receiver
                 ↙    ↓    ↘
            Tempo  Loki  Prometheus
                 ↘    ↓    ↙
              Grafana Cloud
              albertito.grafana.net
```

## The Bug

```python
# BUG: N+1 — 8 queries × 200ms = 1.6s
for item_id in order["item_ids"]:
    item = await db_query_single_item(item_id)   # 200ms each

# FIX: 1 batch query × 200ms = 200ms
items = await db_query_items_batch(order["item_ids"])
```

## Telemetry

| Signal | What it shows |
|--------|--------------|
| Prometheus | p95 latency spike, DB query count by type |
| Tempo | Waterfall of 8 sequential db.query spans per request |
| Loki | "Fetching item 1 of 8" ... "Fetching item 8 of 8" log pattern |
