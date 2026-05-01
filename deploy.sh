#!/usr/bin/env bash
# deploy.sh — One-command deploy for Grafana Cloud demo
# Usage:
#   ./deploy.sh              # Deploy with bug enabled (default for demo)
#   ./deploy.sh --fix        # Deploy the fix (set BUG_ENABLED=false)
#   ./deploy.sh --teardown   # Remove everything

set -euo pipefail

NAMESPACE="orderservice"
IMAGE="ghcr.io/albert0fg/grafana-demo-orderservice:latest"
BUG_ENABLED="true"
TEARDOWN=false

# Parse args
for arg in "$@"; do
  case $arg in
    --fix)      BUG_ENABLED="false" ;;
    --teardown) TEARDOWN=true ;;
  esac
done

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log()  { echo -e "${BLUE}[demo]${NC} $*"; }
ok()   { echo -e "${GREEN}[ok]${NC}   $*"; }
warn() { echo -e "${YELLOW}[warn]${NC} $*"; }
err()  { echo -e "${RED}[err]${NC}  $*"; exit 1; }

if $TEARDOWN; then
  log "Tearing down orderservice demo..."
  kubectl delete namespace $NAMESPACE --ignore-not-found
  kubectl delete podmonitor orderservice -n monitoring --ignore-not-found
  ok "Teardown complete."
  exit 0
fi

log "========================================="
log "   Grafana Cloud Demo — OrderService"
log "========================================="
log "BUG_ENABLED = $BUG_ENABLED"
echo

# Pre-flight checks
command -v kubectl &>/dev/null || err "kubectl not found"
kubectl cluster-info &>/dev/null || err "kubectl not connected to a cluster"

log "Deploying namespace and K8s resources..."
kubectl apply -f k8s/namespace.yaml

# Patch deployment with the correct BUG_ENABLED value
kubectl apply -f k8s/service.yaml

# Use kubectl with inline env override instead of separate patch
cat k8s/deployment.yaml \
  | sed "s/value: \"true\"   # <-- Toggle/value: \"${BUG_ENABLED}\"   # <-- Toggle/" \
  | kubectl apply -f -

# Apply PodMonitor (if Prometheus Operator CRD exists)
if kubectl get crd podmonitors.monitoring.coreos.com &>/dev/null; then
  kubectl apply -f k8s/podmonitor.yaml
  ok "PodMonitor created for Prometheus scraping"
else
  warn "PodMonitor CRD not found — metrics via annotations instead"
fi

log "Waiting for orderservice to be ready..."
kubectl rollout status deployment/orderservice -n $NAMESPACE --timeout=120s
ok "orderservice is running"

log "Waiting for load-generator to start..."
kubectl rollout status deployment/load-generator -n $NAMESPACE --timeout=60s || true
ok "load-generator is running"

echo
log "========================================="
ok "Demo deployed successfully!"
log "========================================="
echo
log "Grafana Cloud: https://albertito.grafana.net"
log "Bug status:    BUG_ENABLED=$BUG_ENABLED"
echo
log "Useful commands:"
echo "  kubectl logs -n $NAMESPACE -l app=orderservice -f"
echo "  kubectl logs -n $NAMESPACE -l app=load-generator -f"
echo "  kubectl get pods -n $NAMESPACE"
echo
if [ "$BUG_ENABLED" = "true" ]; then
  warn "N+1 bug is ACTIVE — latency will be ~1.8s per request"
  log "Run './deploy.sh --fix' after the demo to apply the fix"
else
  ok "Fix is ACTIVE — latency should drop to ~0.3s per request"
fi
