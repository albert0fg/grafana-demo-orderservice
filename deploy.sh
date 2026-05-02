#!/usr/bin/env bash
# deploy.sh — Grafana Cloud demo deployment helper
#
# Usage:
#   ./deploy.sh             Deploy everything with BUG_ENABLED=true
#   ./deploy.sh --fix       Patch order-service to BUG_ENABLED=false (deploy the fix)
#   ./deploy.sh --reset     Re-enable N+1 bug for next demo run
#   ./deploy.sh --teardown  Delete the grafana-demo namespace

set -euo pipefail

NAMESPACE="grafana-demo"
K8S_DIR="$(cd "$(dirname "$0")/k8s" && pwd)"
GRAFANA_DIR="$(cd "$(dirname "$0")/grafana" && pwd)"
DASHBOARD_UID="order-service-n-plus-one-demo"

# Post a Grafana annotation to the demo dashboard (requires gcx; silent on failure)
post_annotation() {
  local text="$1" tags="$2"
  command -v gcx &>/dev/null || return 0
  local f
  f=$(mktemp /tmp/gcx-anno-XXXXXX.yaml)
  cat > "$f" <<YAML
apiVersion: annotations.grafana.app/v1
kind: Annotation
metadata:
  name: "demo-$(date +%s)"
spec:
  dashboardUID: ${DASHBOARD_UID}
  tags: [${tags}]
  text: "${text}"
  time: $(date +%s)000
YAML
  gcx annotations create -f "$f" 2>/dev/null && echo "Grafana annotation posted." || true
  rm -f "$f"
}

case "${1:-}" in
  --fix)
    echo "Patching order-service: setting BUG_ENABLED=false..."
    kubectl patch deployment order-service \
      -n "$NAMESPACE" \
      --type=strategic \
      -p='{"spec":{"template":{"spec":{"containers":[{"name":"order-service","env":[{"name":"BUG_ENABLED","value":"false"}]}]}}}}'
    echo "Done. Waiting for rollout..."
    kubectl rollout status deployment/order-service -n "$NAMESPACE"
    echo "N+1 bug is now FIXED."
    post_annotation "Fix deployed manually — BUG_ENABLED=false" "demo, fix"
    ;;

  --reset)
    echo "Resetting demo: re-enabling N+1 bug (BUG_ENABLED=true)..."
    SHORT_SHA="$(git -C "$(dirname "$0")" rev-parse --short HEAD)"
    kubectl patch deployment order-service \
      -n "$NAMESPACE" \
      --type=strategic \
      -p="{\"spec\":{\"template\":{\"spec\":{\"containers\":[{\"name\":\"order-service\",\"env\":[{\"name\":\"BUG_ENABLED\",\"value\":\"true\"},{\"name\":\"SERVICE_VERSION\",\"value\":\"${SHORT_SHA}\"}]}]}}}}"
    kubectl rollout status deployment/order-service -n "$NAMESPACE"
    echo "Done. BUG_ENABLED=true, SERVICE_VERSION=${SHORT_SHA} — ready for next demo run."
    post_annotation "Demo reset — BUG_ENABLED=true, version=${SHORT_SHA}" "demo, reset"
    ;;

  --teardown)
    echo "Deleting namespace $NAMESPACE..."
    kubectl delete namespace "$NAMESPACE" --ignore-not-found
    echo "Teardown complete."
    ;;

  "")
    echo "Deploying Grafana demo to namespace: $NAMESPACE"
    kubectl apply -f "$K8S_DIR/namespace.yaml"
    kubectl apply -f "$K8S_DIR/inventory-service.yaml"
    kubectl apply -f "$K8S_DIR/order-service.yaml"
    kubectl apply -f "$K8S_DIR/frontend-api.yaml"
    kubectl apply -f "$K8S_DIR/load-generator.yaml"

    echo ""
    echo "Waiting for deployments to be ready..."
    for svc in inventory-service order-service frontend-api load-generator; do
      kubectl rollout status deployment/"$svc" -n "$NAMESPACE"
    done

    echo ""
    echo "Provisioning Grafana dashboard..."
    if command -v gcx &>/dev/null; then
      gcx dashboards create -f "$GRAFANA_DIR/dashboard-order-service.json" \
        --folder-name "Order Service Demo" --upsert 2>/dev/null && \
        echo "Dashboard provisioned in folder 'Order Service Demo'." || \
        echo "Warning: dashboard provisioning failed (gcx not configured?) — skipping."
    else
      echo "Warning: gcx not found — skipping dashboard provisioning."
    fi

    echo ""
    echo "All services running. N+1 bug is ENABLED (BUG_ENABLED=true)."
    echo "Run './deploy.sh --fix' to patch order-service and deploy the fix."
    ;;

  *)
    echo "Unknown argument: ${1}"
    echo "Usage: $0 [--fix|--reset|--teardown]"
    exit 1
    ;;
esac
