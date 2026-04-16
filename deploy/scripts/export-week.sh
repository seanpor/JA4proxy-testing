#!/usr/bin/env bash
# 12-A: Weekly export of honeypot research data.
#
# Produces /opt/ja4proxy-export/<YYYY-WW>/ containing:
#   - prometheus-snapshot/ (TSDB snapshot via admin API)
#   - loki-logs.jsonl (last 7d via Loki query)
#   - binary-provenance.yml (from JA4proxy config)
#   - manifest.yml (sha256 of every file)
#
# Triggered by ja4proxy-export.timer (weekly) or manually via
# `systemctl start ja4proxy-export.service`.

set -euo pipefail

WEEK="$(date -u +%G-W%V)"
EXPORT_DIR="/opt/ja4proxy-export/${WEEK}"
MANIFEST="${EXPORT_DIR}/manifest.yml"

if [ -d "${EXPORT_DIR}" ]; then
    echo "Export directory already exists: ${EXPORT_DIR}"
    echo "Skipping to avoid overwriting a previous export."
    exit 0
fi

mkdir -p "${EXPORT_DIR}"
chmod 0700 "${EXPORT_DIR}"

log() { echo "[$(date -u +%H:%M:%S)] $*"; }

# ── Prometheus TSDB snapshot ────────────────────────────────
log "Creating Prometheus TSDB snapshot"
SNAP_RESP=$(curl -sf -XPOST 'http://127.0.0.1:9090/api/v1/admin/tsdb/snapshot' 2>&1) || {
    echo "WARNING: Prometheus snapshot failed (is --web.enable-admin-api set?)"
    echo "  Response: ${SNAP_RESP}"
    SNAP_RESP=""
}

if [ -n "${SNAP_RESP}" ]; then
    SNAP_NAME=$(echo "${SNAP_RESP}" | python3 -c "import sys,json; print(json.load(sys.stdin)['data']['name'])" 2>/dev/null || true)
    if [ -n "${SNAP_NAME}" ]; then
        # Prometheus runs in Docker — the snapshot lives inside the
        # container's volume, not on the host filesystem. Use docker cp.
        docker cp "ja4proxy-prometheus:/prometheus/snapshots/${SNAP_NAME}" \
            "${EXPORT_DIR}/prometheus-snapshot" 2>/dev/null || \
            log "WARNING: could not copy snapshot from container"
    fi
fi

# ── Loki logs (last 7 days) ────────────────────────────────
# NOTE: limit=100000 may truncate on busy honeypots. The query
# returns a best-effort sample, not a complete dump. For full
# coverage, increase the limit or paginate with start/end windows.
log "Querying Loki for last 7 days (limit=100000)"
END=$(date -u +%s)
START=$((END - 7*86400))
curl -sf "http://127.0.0.1:3100/loki/api/v1/query_range" \
    --data-urlencode "query={job=~\".+\"}" \
    --data-urlencode "start=${START}" \
    --data-urlencode "end=${END}" \
    --data-urlencode "limit=100000" \
    -o "${EXPORT_DIR}/loki-logs.jsonl" 2>/dev/null || {
    log "WARNING: Loki query failed; writing empty file"
    echo '{}' > "${EXPORT_DIR}/loki-logs.jsonl"
}

# ── Binary provenance ──────────────────────────────────────
log "Copying binary provenance"
if [ -f /opt/ja4proxy/config/binary-provenance.yml ]; then
    cp /opt/ja4proxy/config/binary-provenance.yml "${EXPORT_DIR}/"
fi

# ── Manifest ───────────────────────────────────────────────
log "Building manifest"
{
    echo "# Export manifest — ${WEEK}"
    echo "# Generated: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
    echo "files:"
    find "${EXPORT_DIR}" -type f ! -name manifest.yml -print0 \
        | sort -z \
        | while IFS= read -r -d '' f; do
            REL="${f#${EXPORT_DIR}/}"
            SHA=$(sha256sum "$f" | awk '{print $1}')
            echo "  - path: \"${REL}\""
            echo "    sha256: \"${SHA}\""
        done
} > "${MANIFEST}"

# ── Cleanup old exports (>90 days) ─────────────────────────
log "Cleaning exports older than 90 days"
find /opt/ja4proxy-export -maxdepth 1 -mindepth 1 -type d -mtime +90 \
    -exec rm -rf {} + 2>/dev/null || true

log "Export complete: ${EXPORT_DIR}"
log "Manifest: ${MANIFEST}"
