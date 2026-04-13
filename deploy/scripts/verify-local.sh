#!/bin/bash
# ─────────────────────────────────────────────────────────────
# JA4proxy Local Verification Script
# ─────────────────────────────────────────────────────────────
#
# Runs ON the target VM (via SSH) to verify all services are
# healthy WITHOUT exposing any ports to the public internet.
#
# Usage:
#   ssh root@<VM_IP> 'bash -s' < deploy/scripts/verify-local.sh
#   # or
#   make verify VM_IP=<ip>
# ─────────────────────────────────────────────────────────────

set -euo pipefail

PASS=0
FAIL=0
WARN=0

check() {
    local name="$1"
    local cmd="$2"
    local expected="$3"

    if result=$(eval "$cmd" 2>&1); then
        if [[ "$result" == *"$expected"* ]]; then
            echo "  ✅ $name"
            ((PASS++))
        else
            echo "  ❌ $name — unexpected output: $result"
            ((FAIL++))
        fi
    else
        echo "  ❌ $name — command failed: $result"
        ((FAIL++))
    fi
}

warn() {
    local name="$1"
    local msg="$2"
    echo "  ⚠️  $name — $msg"
    ((WARN++))
}

echo "╔══════════════════════════════════════════════════════╗"
echo "║   JA4proxy — Local Service Verification              ║"
echo "║   (running on $(hostname), all checks via 127.0.0.1) ║"
echo "╚══════════════════════════════════════════════════════╝"
echo ""

# ── System Checks ──────────────────────────────────────────
echo "── System ─────────────────────────────────────────────"
check "UFW active" "ufw status verbose | head -1" "Status: active"
check "Fail2ban active" "fail2ban-client status sshd | head -1" "Status for the jail: sshd"

# ── JA4proxy ───────────────────────────────────────────────
echo ""
echo "── JA4proxy ────────────────────────────────────────────"
check "systemd active" "systemctl is-active ja4proxy" "active"
check "/health endpoint" "curl -s http://127.0.0.1:9090/health" "healthy"
check "/health/deep endpoint" "curl -s http://127.0.0.1:9090/health/deep" "healthy"
check "/metrics endpoint" "curl -s http://127.0.0.1:9090/metrics | head -1" "#"

# Check dial is 0 (monitor-only)
DIAL=$(curl -s http://127.0.0.1:9090/metrics 2>/dev/null | grep "ja4proxy_dial_current" | awk '{print $2}' || echo "unknown")
if [[ "$DIAL" == "0" ]]; then
    echo "  ✅ dial=0 (monitor-only)"
    ((PASS++))
else
    warn "dial=$DIAL" "Expected 0 for monitor-only mode"
fi

# ── Docker Compose Stack ───────────────────────────────────
echo ""
echo "── Docker Services ─────────────────────────────────────"
cd /opt/ja4proxy-docker || { echo "  ❌ Docker compose directory not found"; exit 1; }

check "Redis running" "docker exec ja4proxy-redis redis-cli -a \"\$(grep REDIS_PASSWORD .env | cut -d= -f2)\" ping" "PONG"
check "HAProxy running" "docker inspect ja4proxy-haproxy --format '{{.State.Status}}'" "running"
check "Caddy running" "docker inspect ja4proxy-honeypot --format '{{.State.Status}}'" "running"
check "Prometheus running" "docker inspect ja4proxy-prometheus --format '{{.State.Status}}'" "running"
check "Grafana running" "docker inspect ja4proxy-grafana --format '{{.State.Status}}'" "running"
check "Loki running" "docker inspect ja4proxy-loki --format '{{.State.Status}}'" "running"
check "Promtail running" "docker inspect ja4proxy-promtail --format '{{.State.Status}}'" "running"

# ── Service Health ─────────────────────────────────────────
echo ""
echo "── Service Health ──────────────────────────────────────"
check "Prometheus healthy" "curl -s http://127.0.0.1:9091/-/healthy" "Prometheus Server is Healthy"

GRAFANA_PASS=$(grep GRAFANA_ADMIN_PASSWORD .env | cut -d= -f2)
check "Grafana healthy" "curl -s -u admin:${GRAFANA_PASS} http://127.0.0.1:3000/api/health" '"database":"ok"'
check "Loki ready" "curl -s http://127.0.0.1:3100/ready" "ready"

# ── Integration Test ───────────────────────────────────────
echo ""
echo "── Integration Test ────────────────────────────────────"
check "Full pipeline (curl :443)" "curl -sk https://127.0.0.1:443/ 2>/dev/null | grep -o 'RESEARCH HONEYPOT'" "RESEARCH HONEYPOT"
check "Caddy direct (localhost)" "curl -sk http://127.0.0.1:8081/ 2>/dev/null | grep -o 'RESEARCH HONEYPOT'" "RESEARCH HONEYPOT"

# ── Network Isolation ──────────────────────────────────────
echo ""
echo "── Network Isolation ───────────────────────────────────"
if docker exec ja4proxy-redis wget -T3 http://example.com 2>/dev/null; then
    warn "Redis" "CAN reach internet — internal network isolation broken"
else
    echo "  ✅ Redis isolated (cannot reach internet)"
    ((PASS++))
fi

if docker exec ja4proxy-loki curl -s --max-time 3 http://example.com 2>/dev/null; then
    warn "Loki" "CAN reach internet — monitoring network isolation broken"
else
    echo "  ✅ Loki isolated (cannot reach internet)"
    ((PASS++))
fi

# ── Security Checks ────────────────────────────────────────
echo ""
echo "── Security ────────────────────────────────────────────"
STAGE=$(grep ja4proxy_deployment_stage /opt/ja4proxy-docker/.env 2>/dev/null | cut -d= -f2 || echo "unknown")
if [[ -z "$STAGE" ]]; then
    # Check from ansible facts if available
    if [[ -f /opt/ja4proxy/config/stage ]]; then
        STAGE=$(cat /opt/ja4proxy/config/stage)
    else
        STAGE="unknown"
    fi
fi
echo "  ℹ️  Deployment stage: $STAGE"

# Check Docker port bindings
echo ""
echo "── Port Bindings (docker ps) ───────────────────────────"
docker ps --format "table {{.Names}}\t{{.Ports}}" 2>/dev/null | grep -E "127.0.0.1|0.0.0.0" || true

# Summary
echo ""
echo "╔══════════════════════════════════════════════════════╗"
echo "║                  VERIFICATION SUMMARY                  ║"
echo "╚══════════════════════════════════════════════════════╝"
echo ""
echo "  Passed:   $PASS"
echo "  Failed:   $FAIL"
echo "  Warnings: $WARN"
echo ""

if [[ $FAIL -eq 0 ]]; then
    echo "  ✅ All checks passed."
    if [[ $WARN -eq 0 ]]; then
        echo ""
        echo "  Ready for go-live:"
        echo "    1. Set ja4proxy_deployment_stage to 'live' in group_vars/all.yml"
        echo "    2. Run: make go-live VM_IP=<ip>"
        echo "    3. Monitor: make status VM_IP=<ip>"
    else
        echo "  ⚠️  $WARN warning(s) — review before going live."
    fi
    exit 0
else
    echo "  ❌ $FAIL check(s) failed — DO NOT go live."
    echo "     Fix issues and re-run: make verify VM_IP=<ip>"
    exit 1
fi
