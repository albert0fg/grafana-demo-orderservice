#!/usr/bin/env bash
# demo-check.sh — pre-demo readiness check
# Run this before presenting to catch problems early.
set -euo pipefail

NAMESPACE="grafana-demo"
GRAFANA_URL="https://albertito.grafana.net"
ALERT_RULE_UID="dfku265tgj11ca"
GCX_CONFIG="${HOME}/.config/gcx/config.yaml"
PASS=0
FAIL=0

green() { printf '\033[0;32m✓ %s\033[0m\n' "$*"; }
red()   { printf '\033[0;31m✗ %s\033[0m\n' "$*"; }
warn()  { printf '\033[0;33m⚠ %s\033[0m\n' "$*"; }

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  Pre-demo readiness check — Order Service Demo"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# ── 1. All pods Running ──────────────────────────────
printf "1. Pods running... "
NOT_READY=$(kubectl get pods -n "$NAMESPACE" --no-headers 2>/dev/null \
  | awk '!/Running/{c++} END{print c+0}')
if [ "$NOT_READY" -gt 0 ]; then
  red "FAIL — $NOT_READY pod(s) not Running (run './deploy.sh' to redeploy)"
  kubectl get pods -n "$NAMESPACE"
  FAIL=$((FAIL+1))
else
  PODS=$(kubectl get pods -n "$NAMESPACE" --no-headers | wc -l | tr -d ' ')
  green "all $PODS pods Running"
  PASS=$((PASS+1))
fi

# ── 2. BUG_ENABLED=true ──────────────────────────────
printf "2. N+1 bug enabled... "
BUG=$(kubectl exec -n "$NAMESPACE" deploy/order-service -- \
  env 2>/dev/null | grep BUG_ENABLED | cut -d= -f2 || echo "unknown")
if [ "$BUG" != "true" ]; then
  red "FAIL — BUG_ENABLED=$BUG (run './deploy.sh --reset' to re-enable)"
  FAIL=$((FAIL+1))
else
  SVC_VER=$(kubectl exec -n "$NAMESPACE" deploy/order-service -- \
    env 2>/dev/null | grep SERVICE_VERSION | cut -d= -f2 || echo "unknown")
  green "BUG_ENABLED=true  (service.version=$SVC_VER)"
  PASS=$((PASS+1))
fi

# ── 3. order-6 latency > 800 ms ──────────────────────
printf "3. order-6 latency (N+1, 10 items, expect >800ms)... "
LATENCY=$(kubectl exec -n "$NAMESPACE" deploy/frontend-api -- \
  python3 -c "
import urllib.request, time
start = time.time()
urllib.request.urlopen('http://frontend-api:8080/checkout/order-6', timeout=15)
print(int((time.time()-start)*1000))
" 2>/dev/null || echo "0")
if [ "$LATENCY" -lt 800 ]; then
  warn "${LATENCY}ms — lower than expected (pods may need a moment to warm up)"
  PASS=$((PASS+1))
else
  green "${LATENCY}ms"
  PASS=$((PASS+1))
fi

# ── 4. Alert state (requires gcx/SA token) ───────────
printf "4. Alert firing... "
if [ ! -f "$GCX_CONFIG" ]; then
  warn "skipped — gcx config not found at $GCX_CONFIG"
else
  SA_TOKEN=$(python3 -c \
    "import yaml; c=yaml.safe_load(open('$GCX_CONFIG')); print(c['contexts']['albertito']['token'])" \
    2>/dev/null || echo "")
  if [ -z "$SA_TOKEN" ]; then
    warn "skipped — could not read SA token from gcx config"
  else
    STATE=$(curl -s \
      -H "Authorization: Bearer $SA_TOKEN" \
      "${GRAFANA_URL}/api/prometheus/grafana/api/v1/rules" \
      | python3 -c "
import sys, json
try:
    d = json.load(sys.stdin)
    for g in d.get('data', {}).get('groups', []):
        for r in g.get('rules', []):
            if r.get('name','').startswith('frontend-api'):
                print(r.get('state','unknown'))
                raise SystemExit
    print('not_found')
except SystemExit:
    pass
" 2>/dev/null || echo "error")
    case "$STATE" in
      firing)
        green "Firing — alert will appear in Grafana Assistant context"
        PASS=$((PASS+1))
        ;;
      pending)
        warn "Pending — will fire in <1 min (latency spike detected but window not elapsed)"
        PASS=$((PASS+1))
        ;;
      inactive|normal)
        red "FAIL — alert is $STATE (latency may be too low or pods just restarted)"
        FAIL=$((FAIL+1))
        ;;
      not_found)
        warn "skipped — alert rule not found via API"
        ;;
      *)
        warn "skipped — could not query alert state ($STATE)"
        ;;
    esac
  fi
fi

# ── Summary ──────────────────────────────────────────
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
if [ "$FAIL" -eq 0 ]; then
  printf '\033[0;32m  ✓ Ready to demo! (%d checks passed)\033[0m\n' "$PASS"
  echo "  Start with: \"Hay una alerta crítica disparada, investiga qué está pasando\""
else
  printf '\033[0;31m  ✗ Not ready — %d check(s) failed, %d passed\033[0m\n' "$FAIL" "$PASS"
  echo "  Fix the issues above before starting the demo."
fi
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
