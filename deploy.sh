#!/usr/bin/env bash
# deploy.sh — Grafana Cloud demo deployment helper
#
# Usage:
#   ./deploy.sh             Deploy everything with BUG_ENABLED=true
#   ./deploy.sh --fix       Patch order-service to BUG_ENABLED=false (deploy the fix)
#   ./deploy.sh --teardown  Delete the grafana-demo namespace

set -euo pipefail

NAMESPACE="grafana-demo"
K8S_DIR="$(cd "$(dirname "$0")/k8s" && pwd)"

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
    echo "All services running. N+1 bug is ENABLED (BUG_ENABLED=true)."
    echo "Run './deploy.sh --fix' to patch order-service and deploy the fix."
    ;;

  *)
    echo "Unknown argument: ${1}"
    echo "Usage: $0 [--fix|--teardown]"
    exit 1
    ;;
esac
