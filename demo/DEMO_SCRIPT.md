# Demo Script — Grafana Cloud N+1 Bug

**Duration:** ~20 min | **Audience:** Technical / DevOps

---

## Act 1 — Deploy the demo (2 min)

- Run `./deploy.sh` to apply all manifests to the `grafana-demo` namespace.
- Verify all 4 pods are Running: `kubectl get pods -n grafana-demo`.
- The load generator immediately starts hitting `frontend-api` at 3 RPS with `BUG_ENABLED=true`.

---

## Act 2 — Observe the symptom (4 min)

- Open Grafana Cloud → Application Observability (or Explore → Tempo).
- Use **Prompt 1** in Grafana Assistant: ask for p95 latency on `frontend-api`.
- Show the latency is elevated — each checkout triggers multiple serial HTTP calls.

---

## Act 3 — Root-cause with traces (6 min)

- Use **Prompt 2** to pull up the service map: frontend-api → order-service → inventory-service.
- Use **Prompt 3** to find traces where order-service fans out into 3-5 sequential calls to inventory-service.
- Drill into one trace: show the waterfall — each `GET /items/{id}` waits for the previous one.

---

## Act 4 — Fix via GitHub MCP (4 min)

- Use **Prompt 4**: ask Grafana Assistant to create a PR via GitHub MCP.
- Show the PR created in `albert0fg/grafana-demo-orderservice` with the `BUG_ENABLED=false` change.
- Apply the fix live: `./deploy.sh --fix` — watch the rollout complete in seconds.

---

## Act 5 — Confirm the improvement (4 min)

- Use **Prompt 5**: compare p95 latency before and after the fix timestamp.
- Show the graph drop: from N×RTT to 1×RTT per request.
- Teardown when done: `./deploy.sh --teardown`.
