# Grafana Assistant Demo Prompts

These 5 prompts are designed to walk through the N+1 bug scenario using Grafana Assistant.
Each prompt is a single short sentence (~10-15 words) in Spanish.

---

## Prompt 1

El frontend-api está lento. Analiza la latencia p95 con Prometheus de los últimos 15 minutos.

> **What Grafana Assistant should do:** Query `http_server_duration_milliseconds` (or the OTEL-equivalent
> histogram) filtered by `service_name="frontend-api"`, compute the p95, and show a time-series graph
> highlighting that latency spikes above normal. This surfaces the symptom before root-cause analysis.

---

## Prompt 2

Muéstrame el service map de los últimos 10 minutos y dime qué servicio genera más spans.

> **What Grafana Assistant should do:** Open the Tempo/Grafana service map, identify the call chain
> frontend-api → order-service → inventory-service, and highlight that inventory-service has the
> highest span count due to the N+1 bug producing one span per item per order.

---

## Prompt 3

Busca trazas de order-service donde haya más de 3 llamadas a inventory-service en un solo request.

> **What Grafana Assistant should do:** Query Tempo for traces where `service.name="order-service"` and
> count child spans to `inventory-service`. Surface an example trace that shows 3-5 sequential HTTP
> calls to `/items/{id}` that should have been a single `/items/batch` call.

---

## Prompt 4

Usa el MCP de GitHub para crear un PR en albert0fg/grafana-demo-orderservice que corrija el bug N+1 en order-service/main.py.

> **What Grafana Assistant should do:** Use the GitHub MCP tool to open a pull request against
> `albert0fg/grafana-demo-orderservice`. The PR should change `BUG_ENABLED` default to `"false"` in
> `k8s/order-service.yaml` (or patch `order-service/main.py`) with a clear description linking
> the observed traces to the fix.

---

## Prompt 5

Compara la latencia p95 de order-service antes y después del fix desplegado hace 5 minutos.

> **What Grafana Assistant should do:** Use `kubectl` or Prometheus to confirm when `BUG_ENABLED=false`
> was rolled out, then compare the p95 latency histogram before and after that timestamp.
> The graph should show a clear drop from ~N*RTT ms down to ~1*RTT ms per request.
