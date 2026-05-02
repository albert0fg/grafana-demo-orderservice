# Grafana Assistant Demo Prompts

5 prompts in Spanish, one sentence each. Use them in order after running
`./demo-check.sh` and confirming the alert is Firing.

---

## Prompt 1

Hay una alerta crítica disparada en Grafana, analiza qué está pasando.

> **What happens:** Assistant reads the firing alert context, queries
> `traces_spanmetrics_latency_bucket` for `frontend-api`, and confirms p99
> checkout latency is ~1s — well above the 300ms threshold.

---

## Prompt 2

Muéstrame el service map de los últimos 10 minutos y dime qué servicio genera más spans.

> **What happens:** Assistant opens the Tempo service map, identifies the chain
> `frontend-api → order-service → inventory-service`, and flags that
> `inventory-service` has ~10× more spans than expected for the traffic volume —
> the N+1 signature.

---

## Prompt 3

Busca trazas de order-service donde haya más de 5 llamadas a inventory-service en un solo request.

> **What happens:** Assistant queries Tempo for traces where `order-service`
> fans out into many child spans. It surfaces order-6 (10 items, ~1s total) and
> shows the sequential waterfall — each `GET /items/{id}` blocks the next.
> Points out `/items/batch` as the fix.

---

## Prompt 4

Usa el MCP de GitHub para crear un PR en albert0fg/grafana-demo-orderservice que corrija el bug N+1 en order-service.

> **What happens:** Assistant uses GitHub MCP to create branch
> `fix/order-service-n-plus-one`, commits `k8s/order-service.yaml` with
> `BUG_ENABLED=false`, and opens a PR with a description linking the traces to
> the fix. **Merge the PR** — `deploy-on-merge.yml` auto-deploys in ~30s and
> stamps `SERVICE_VERSION=<sha>-fix`.

---

## Prompt 5

Compara la latencia p99 de order-service antes y después del fix usando service.version.

> **What happens:** Assistant queries span metrics grouped by `service_version`,
> showing two series:
> - `e856bee` (buggy): p99 ~1000ms
> - `e856bee-fix` (fixed): p99 ~100ms
>
> 10x improvement visible as a step-change on the graph.

---

## After the Demo

```bash
./deploy.sh --reset   # re-enable bug for next run (~5 seconds)
./demo-check.sh       # verify ready
```
