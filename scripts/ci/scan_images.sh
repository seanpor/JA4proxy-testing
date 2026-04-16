#!/usr/bin/env bash
# 18-B: Scan every image referenced by the rendered compose template
# for HIGH/CRITICAL vulnerabilities that have an available fix.
#
# Exit codes:
#   0 — all images clean (no fixable HIGH/CRITICAL)
#   1 — one or more images have fixable HIGH/CRITICAL vulns
#   2 — prerequisite missing (trivy or python3 not on PATH)
#
# Runnable locally (`make scan-images`) and from CI. Trivy DB is cached
# by the workflow via actions/cache; locally it's cached in Trivy's
# default cache dir under $HOME.

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

if ! command -v trivy >/dev/null 2>&1; then
  echo "trivy not installed. Install:" >&2
  echo "  curl -sfL https://raw.githubusercontent.com/aquasecurity/trivy/main/contrib/install.sh | sh -s -- -b /usr/local/bin" >&2
  exit 2
fi

if ! command -v python3 >/dev/null 2>&1; then
  echo "python3 not installed — required to render the compose template." >&2
  exit 2
fi

# NOTE: at CI time the rendered compose file carries TAGs, not digests
# — role 09 resolves digests at deploy time. Scanning by tag is still
# valuable: the pinned digest (once resolved) will be for that tag,
# and Trivy's advisory feed is tag-aware.
mapfile -t images < <(python3 "${ROOT}/scripts/ci/render_compose.py" --list-images)

if [[ ${#images[@]} -eq 0 ]]; then
  echo "no images to scan — render_compose.py --list-images returned empty" >&2
  exit 2
fi

echo "── Trivy image scan: ${#images[@]} images, HIGH/CRITICAL, fixed-only ──"

fail=0
for img in "${images[@]}"; do
  printf "\n── %s ──\n" "${img}"
  if ! trivy image \
      --severity HIGH,CRITICAL \
      --ignore-unfixed \
      --exit-code 1 \
      --no-progress \
      --scanners vuln \
      --timeout 5m \
      "${img}"; then
    fail=1
  fi
done

if [[ ${fail} -ne 0 ]]; then
  echo
  echo "❌ one or more images have fixable HIGH/CRITICAL vulnerabilities" >&2
  exit 1
fi

echo
echo "✓ all ${#images[@]} images clean (no fixable HIGH/CRITICAL vulns)"
