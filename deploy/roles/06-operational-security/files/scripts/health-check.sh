#!/bin/bash
# ─────────────────────────────────────────────────────────────
# JA4proxy Daily Health Check
# Run via cron: 0 6 * * * /opt/ja4proxy/scripts/health-check.sh
# ─────────────────────────────────────────────────────────────

set -euo pipefail

echo "=== JA4proxy Daily Health Check ==="
echo "Timestamp: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
echo "Hostname: $(hostname)"
echo ""

# System overview
echo "── System ────────────────────────────────────────────────"
uptime
echo ""
echo "Memory: $(free -h | grep '^Mem:' | awk '{print $3 "/" $2}')"
echo "Disk: $(df -h / | tail -1 | awk '{print $3 "/" $2 " (" $5 " used)"}')"
echo ""

# Service status
echo "── Services ──────────────────────────────────────────────"
echo "JA4proxy: $(systemctl is-active ja4proxy 2>/dev/null || echo 'INACTIVE')"

DOCKER_COMPOSE="/opt/ja4proxy-docker/docker-compose.yml"
if [ -f "$DOCKER_COMPOSE" ]; then
    cd /opt/ja4proxy-docker
    echo ""
    echo "Docker containers:"
    docker compose ps --format "table {{.Name}}\t{{.Status}}" 2>/dev/null || echo "  Docker compose not available"
else
    echo "Docker Compose: not found"
fi
echo ""

# Connection rate
echo "── Connections (last hour) ───────────────────────────────"
curl -s http://127.0.0.1:9090/metrics 2>/dev/null \
  | grep "ja4proxy_connections_total" \
  | awk '{print "Total:", $2}' \
  || echo "  Metrics endpoint unavailable"
echo ""

# Recent errors
echo "── Recent Errors (last 6 hours) ──────────────────────────"
ERRORS=$(sudo journalctl -u ja4proxy.service --since "6 hours ago" -p err --no-pager 2>/dev/null | tail -10)
if [ -n "$ERRORS" ]; then
    echo "$ERRORS"
else
    echo "  No errors found"
fi
echo ""

# Log sizes
echo "── Log Sizes ─────────────────────────────────────────────"
echo "Journal: $(journalctl --disk-usage 2>/dev/null | head -1 || echo 'N/A')"
if [ -d /opt/ja4proxy/logs ]; then
    echo "JA4proxy logs: $(du -sh /opt/ja4proxy/logs/ 2>/dev/null | awk '{print $1}')"
fi
echo ""

echo "=== Health Check Complete ==="
