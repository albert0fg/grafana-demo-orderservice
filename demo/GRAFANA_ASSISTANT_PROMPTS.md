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

Usa el MCP de GitHub para crear un PR en albert0fg/grafana-demo-orderservice que corrija el bug N+1 en order-service. El fix debe ser únicamente cambiar el valor de BUG_ENABLED a "false" en el fichero k8s/order-service.yaml. No toques el código Python.

> **What happens:** Assistant uses GitHub MCP to create branch
> `fix/order-service-n-plus-one`, commits **only** `k8s/order-service.yaml`
> changing `BUG_ENABLED` from `"true"` to `"false"`, and opens a PR linking
> the traces to the fix. **Merge the PR** — `deploy-on-merge.yml` auto-deploys
> in ~30s and stamps `SERVICE_VERSION=<sha>-fix`.

---

## Prompt 5

Usando las span metrics de Prometheus, muestra la latencia p99 de order-service agrupada por service_version para comparar antes y después del fix.

> **What happens:** Assistant queries:
> ```promql
> histogram_quantile(0.99, sum by (le, service_version) (
>   rate(traces_spanmetrics_latency_bucket{
>     service="order-service",
>     span_name="GET /orders/{order_id}"
>   }[5m])
> )) * 1000
> ```
> `service_version` is a confirmed label on these metrics. Two series appear:
> - `<sha>` (buggy): p99 ~950ms
> - `<sha>-fix` (fixed): p99 ~90ms
>
> 10x improvement as a visible step-change. Also open the
> **Order Service Demo** dashboard in Grafana for the full visual.

---

## After the Demo

```bash
./deploy.sh --reset   # re-enable bug for next run (~5 seconds)
./demo-check.sh       # verify ready
```
