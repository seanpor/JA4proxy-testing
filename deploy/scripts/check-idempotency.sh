#!/usr/bin/env bash
# 14-D: idempotency check. Re-runs the full playbook and fails if the
# second run reports any `changed=N > 0` in the final PLAY RECAP. Runs
# during the VM smoke test after the first deploy has succeeded.
#
# Usage:
#     VM_IP=1.2.3.4 bash deploy/scripts/check-idempotency.sh
# or (from repo root):
#     make idempotency VM_IP=1.2.3.4
#
# Non-zero exit = at least one task is not idempotent. Fix it before
# merging: wrap bare commands with `changed_when: false` / `creates:`,
# or replace shell-outs with dedicated Ansible modules.

set -euo pipefail

: "${VM_IP:?VM_IP is required}"

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$REPO_ROOT"

LOG="$(mktemp -t ja4proxy-idempotency.XXXXXX.log)"
trap 'rm -f "$LOG"' EXIT

echo "── idempotency: re-running site.yml against $VM_IP ──"

JA4PROXY_VM_HOST="$VM_IP" \
  ansible-playbook \
  -i deploy/inventory/hosts.ini \
  deploy/playbooks/site.yml \
  --extra-vars "ja4proxy_vm_host=$VM_IP" \
  2>&1 | tee "$LOG"

echo
echo "── parsing PLAY RECAP ──"

# Extract the final PLAY RECAP block and sum `changed=N` across hosts.
# A non-idempotent task shows up as changed>0 on the second run.
recap="$(awk '/^PLAY RECAP/{flag=1} flag' "$LOG")"
if [[ -z "$recap" ]]; then
  echo "FAIL: no PLAY RECAP found in output" >&2
  exit 2
fi

# Lines look like: "host : ok=30 changed=2 unreachable=0 failed=0 ..."
# We want to fail if any `changed=` is non-zero.
offenders="$(echo "$recap" | grep -oE 'changed=[0-9]+' | grep -v 'changed=0' || true)"
if [[ -n "$offenders" ]]; then
  echo "FAIL: second run was not idempotent:" >&2
  echo "$recap" >&2
  exit 1
fi

echo "✓ idempotent: second run reports changed=0 for all hosts"
