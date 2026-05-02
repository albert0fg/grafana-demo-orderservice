# Grafana Cloud Demo — Order Service N+1 Bug

High-impact demo: Grafana Assistant receives a firing alert, investigates an
N+1 query bug across 3 microservices, and opens a GitHub PR to fix it —
entirely inside Grafana Cloud.

## The Scenario

`order-service` has an N+1 bug: each checkout makes **N individual HTTP calls**
to `inventory-service` (one per item) instead of a single batch call.

| Order | Items | Buggy latency | Fixed latency |
|-------|-------|--------------|---------------|
| order-1 | 3 | ~270ms | ~90ms |
| order-4 | 5 | ~480ms | ~90ms |
| order-6 | 10 | ~1000ms | ~100ms |

A Grafana alert fires when `frontend-api` p99 checkout latency > 300ms.
Grafana Assistant diagnoses the root cause from traces and opens the fix PR.

## Quick Start

```bash
# 0. Pre-demo readiness check (pods, bug flag, latency, alert state)
./demo-check.sh

# 1. Deploy (first time)
./deploy.sh

# 2. After demo — reset for next run (5 seconds, no rebuild)
./deploy.sh --reset

# 3. Teardown
./deploy.sh --teardown
```

## Demo Guide

See [`demo/DEMO_SCRIPT.md`](demo/DEMO_SCRIPT.md) for the full step-by-step.  
See [`demo/GRAFANA_ASSISTANT_PROMPTS.md`](demo/GRAFANA_ASSISTANT_PROMPTS.md) for copy-paste prompts.

## Architecture

```
load-generator (3 RPS, 50% to order-6)
      │
      ▼
frontend-api  ──────────────────────────────┐
      │                                     │
      ▼                                     │
order-service  ──(N calls, buggy)──▶  inventory-service
                ──(1 batch, fixed)──▶  inventory-service

Each service exports OTLP traces + metrics via gRPC → Alloy → Grafana Cloud
```

## Services

| Service | Role | Bug |
|---------|------|-----|
| `frontend-api` | Gateway, exposes `/checkout/{order_id}` | — |
| `order-service` | Fetches order + items; `BUG_ENABLED` env var controls N+1 | ✓ |
| `inventory-service` | Item catalog; has `/items/{id}` (slow) and `/items/batch` (fast) | — |
| `load-generator` | Generates 3 RPS; 50% traffic to order-6 (10 items) | — |

## The Bug

```python
# BUG (BUG_ENABLED=true): N calls × ~80ms = N×80ms
for item_id in order["item_ids"]:
    r = await client.get(f"{INVENTORY_URL}/items/{item_id}")

# FIX (BUG_ENABLED=false): 1 call × ~80ms = ~80ms regardless of N
r = await client.get(f"{INVENTORY_URL}/items/batch?ids={','.join(item_ids)}")
```

## Telemetry

| Signal | What it shows |
|--------|--------------|
| Prometheus | p99 latency spike on `frontend-api`; alert fires after 1 min |
| Tempo | Waterfall of N sequential `GET /items/{id}` spans per request |
| App Observability | Service map: frontend-api → order-service → inventory-service |
| `service.version` | Short git SHA (`e856bee`) before fix; `e856bee-fix` after |

## Alert

Rule: **frontend-api checkout latency alta** (folder: Order Service Demo)  
Condition: p99 of `GET /checkout/{order_id}` > 300ms for 1 minute  
Notification: `alberto@grafana.com`

## Resetting After a Demo Run

The `deploy-on-merge.yml` workflow auto-deploys the fix when the PR is merged.
To run the demo again:

```bash
./deploy.sh --reset   # patches BUG_ENABLED=true back, ~5 seconds
```
