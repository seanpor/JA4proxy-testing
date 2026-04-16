#!/usr/bin/env bash
# 12-C: Pull the latest weekly export from the VM to the control machine.
#
# Usage: export-pull.sh <VM_IP>
#
# Rsyncs the newest /opt/ja4proxy-export/<YYYY-WW>/ to
# ./exports/<VM>-<YYYY-WW>/ locally, then verifies every sha256
# in manifest.yml. Refuses to overwrite an existing local directory.

set -euo pipefail

VM_IP="${1:?Usage: export-pull.sh <VM_IP>}"
EXPORT_BASE="./exports"

log() { echo "[export-pull] $*"; }

# Find the newest export directory on the VM.
REMOTE_DIR=$(ssh "root@${VM_IP}" \
    'ls -1d /opt/ja4proxy-export/????-W?? 2>/dev/null | sort | tail -1')

if [ -z "${REMOTE_DIR}" ]; then
    log "ERROR: no export directory found on ${VM_IP}:/opt/ja4proxy-export/"
    exit 1
fi

WEEK=$(basename "${REMOTE_DIR}")
LOCAL_DIR="${EXPORT_BASE}/${VM_IP}-${WEEK}"

if [ -d "${LOCAL_DIR}" ]; then
    log "ERROR: local directory already exists: ${LOCAL_DIR}"
    log "Remove it first if you want to re-pull."
    exit 1
fi

mkdir -p "${LOCAL_DIR}"

log "Pulling ${VM_IP}:${REMOTE_DIR}/ → ${LOCAL_DIR}/"
rsync -avz --progress "root@${VM_IP}:${REMOTE_DIR}/" "${LOCAL_DIR}/"

# Verify manifest sha256s.
MANIFEST="${LOCAL_DIR}/manifest.yml"
if [ ! -f "${MANIFEST}" ]; then
    log "WARNING: no manifest.yml found — cannot verify integrity"
    exit 0
fi

log "Verifying sha256 checksums from manifest"
ERRORS=0
while IFS= read -r line; do
    # Parse "    sha256: "<hash>"" and "    path: "<relpath>""
    if [[ "${line}" =~ path:\ \"(.+)\" ]]; then
        CURRENT_PATH="${BASH_REMATCH[1]}"
    fi
    if [[ "${line}" =~ sha256:\ \"([0-9a-f]+)\" ]]; then
        EXPECTED="${BASH_REMATCH[1]}"
        ACTUAL=$(sha256sum "${LOCAL_DIR}/${CURRENT_PATH}" | awk '{print $1}')
        if [ "${EXPECTED}" != "${ACTUAL}" ]; then
            log "MISMATCH: ${CURRENT_PATH}"
            log "  expected: ${EXPECTED}"
            log "  actual:   ${ACTUAL}"
            ERRORS=$((ERRORS + 1))
        fi
    fi
done < "${MANIFEST}"

if [ "${ERRORS}" -gt 0 ]; then
    log "ERROR: ${ERRORS} file(s) failed sha256 verification"
    exit 1
fi

log "All files verified. Export at: ${LOCAL_DIR}"
