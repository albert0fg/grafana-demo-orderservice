# Demo Script — Grafana Cloud N+1 Bug

**Duration:** ~15 min | **Audience:** Technical / DevOps / SRE

---

## Before You Start

```bash
./demo-check.sh
```

All 4 checks must pass (pods running, bug enabled, order-6 >800ms, alert Firing).
If the alert is not yet Firing, wait 1–2 minutes — the load generator sends 50%
of traffic to order-6 (10 items, ~1s) so it fires quickly.

---

## Act 1 — The Alert (2 min)

- Open Grafana Cloud → Alerting. Show the **"frontend-api checkout latency alta"**
  alert in **Firing** state.
- Mention: *"This alert fired on its own — p99 checkout latency crossed 300ms.
  Let's hand this to Grafana Assistant."*
- Open Grafana Assistant.

---

## Act 2 — Root cause with Assistant (8 min)

Use the prompts in `GRAFANA_ASSISTANT_PROMPTS.md` in order:

**Prompt 1** — Point Assistant at the firing alert. It queries Prometheus span
metrics and confirms `frontend-api` p99 is ~1s.

**Prompt 2** — Service map. Assistant identifies the call chain
`frontend-api → order-service → inventory-service` and notes that
`inventory-service` has disproportionately high span count.

**Prompt 3** — Traces. Assistant finds requests where `order-service` fans out
into 10 sequential `GET /items/{id}` calls. Show the waterfall — each call waits
for the previous one. Point out that `inventory-service` has a `/items/batch`
endpoint that does this in a single round-trip.

---

## Act 3 — Fix via GitHub MCP (3 min)

**Prompt 4** — Ask Grafana Assistant to open a PR via GitHub MCP.

- It creates a branch `fix/order-service-n-plus-one` and opens a PR against
  `albert0fg/grafana-demo-orderservice` setting `BUG_ENABLED=false` in
  `k8s/order-service.yaml`.
- Show the PR in GitHub.
- Merge it live — the `deploy-on-merge.yml` workflow triggers automatically
  (~30s) and kubectl-patches `order-service` with `BUG_ENABLED=false` and
  `SERVICE_VERSION=<sha>-fix`.

---

## Act 4 — Confirm the improvement (2 min)

**Prompt 5** — Compare latency before and after. Assistant queries span metrics
and shows the drop:

- **Before** (`service.version=e856bee`): p99 ~1000ms
- **After** (`service.version=e856bee-fix`): p99 ~100ms

10x improvement. The service map also collapses — `inventory-service` span count
drops from N per order to 1.

---

## Reset for Next Run

```bash
./deploy.sh --reset   # re-enables bug, ~5 seconds
./demo-check.sh       # verify ready
```
