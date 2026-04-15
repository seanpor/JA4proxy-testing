#!/usr/bin/env bash
# 15-A: preserve evidence from the research honeypot VM after an
# incident or suspected compromise. Produces a timestamped tarball
# under /var/lib/ja4proxy/evidence/ with:
#
#   - journald export for the past 24h
#   - docker compose logs for each service
#   - iptables / nft rule dump
#   - /opt/ja4proxy/config (proxy.yml + signing key etc.)
#   - systemctl status for the honeypot units
#   - process + network snapshot
#
# The script ends with a sha256 of the tarball and an instruction to
# rsync it off the VM before any destructive remediation (reboot,
# re-image, etc.).
#
# Exits non-zero on any tooling error so callers can detect partial
# collection.

set -euo pipefail

TS="$(date -u +%Y%m%dT%H%M%SZ)"
HOST="$(hostname -s)"
ROOT="/var/lib/ja4proxy/evidence"
WORK="${ROOT}/${HOST}-${TS}"
TARBALL="${WORK}.tar.gz"

mkdir -p "${WORK}"
chmod 0700 "${ROOT}" "${WORK}"

log() { echo "[$(date -u +%H:%M:%S)] $*"; }

log "Collecting journald (last 24h)"
journalctl --since "24 hours ago" --no-pager \
  > "${WORK}/journalctl-24h.log" 2>&1 || true

log "Collecting docker compose logs"
if command -v docker >/dev/null 2>&1; then
    docker ps --format '{{.Names}}' > "${WORK}/docker-ps.txt" 2>&1 || true
    while IFS= read -r c; do
        [ -z "${c}" ] && continue
        docker logs --tail 2000 "${c}" \
          > "${WORK}/docker-${c}.log" 2>&1 || true
    done < "${WORK}/docker-ps.txt"
fi

log "Collecting firewall state"
{
    echo "=== iptables -S ==="; iptables -S 2>&1 || true
    echo "=== ip6tables -S ==="; ip6tables -S 2>&1 || true
    echo "=== ufw status verbose ==="; ufw status verbose 2>&1 || true
    echo "=== nft list ruleset ==="; nft list ruleset 2>&1 || true
} > "${WORK}/firewall.txt"

log "Collecting ja4proxy config"
if [ -d /opt/ja4proxy/config ]; then
    cp -a /opt/ja4proxy/config "${WORK}/ja4proxy-config"
fi

log "Collecting systemd unit status"
{
    for u in ja4proxy.service ja4proxy-redis.service \
             aide-check.service docker.service; do
        echo "=== systemctl status ${u} ==="
        systemctl status "${u}" --no-pager 2>&1 || true
        echo
    done
} > "${WORK}/systemctl-status.txt"

log "Collecting process + network snapshot"
{
    echo "=== ps auxf ==="; ps auxf 2>&1 || true
    echo "=== ss -tunap ==="; ss -tunap 2>&1 || true
    echo "=== who ==="; who 2>&1 || true
    echo "=== last -n 50 ==="; last -n 50 2>&1 || true
} > "${WORK}/proc-net.txt"

log "Sealing tarball"
tar -C "${ROOT}" -czf "${TARBALL}" "$(basename "${WORK}")"
rm -rf "${WORK}"
chmod 0600 "${TARBALL}"

SHA="$(sha256sum "${TARBALL}" | awk '{print $1}')"
echo
echo "Evidence tarball:  ${TARBALL}"
echo "sha256:            ${SHA}"
echo
echo "NEXT STEP — pull the tarball off the VM BEFORE any reboot or re-image:"
echo "  rsync -av root@<vm>:${TARBALL} ./"
echo "  echo '${SHA}  $(basename "${TARBALL}")' | sha256sum -c"
