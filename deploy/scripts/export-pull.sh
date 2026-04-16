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
# Use python3 + PyYAML for robust YAML parsing instead of fragile
# bash regex that breaks if the manifest format drifts.
python3 -c "
import sys, hashlib, yaml
from pathlib import Path

manifest = yaml.safe_load(Path('${MANIFEST}').read_text())
errors = 0
for entry in manifest.get('files', []):
    p = Path('${LOCAL_DIR}') / entry['path']
    if not p.exists():
        print(f'  MISSING: {entry[\"path\"]}')
        errors += 1
        continue
    actual = hashlib.sha256(p.read_bytes()).hexdigest()
    if actual != entry['sha256']:
        print(f'  MISMATCH: {entry[\"path\"]}')
        print(f'    expected: {entry[\"sha256\"]}')
        print(f'    actual:   {actual}')
        errors += 1
    else:
        print(f'  OK: {entry[\"path\"]}')
if errors:
    print(f'{errors} file(s) failed verification')
    sys.exit(1)
"

log "All files verified. Export at: ${LOCAL_DIR}"
