#!/usr/bin/env bash
# 18-B: Scan every image referenced by the rendered compose template
# for fixable HIGH/CRITICAL vulnerabilities.
#
# Two passes:
#   1. CRITICAL  — blocking. Honours `.trivyignore` (allowlist with
#                  mandatory `# expires: YYYY-MM-DD` comments, enforced
#                  separately by scripts/ci/check_image_scan.py).
#   2. HIGH      — informational for now (exit 0 regardless). Chunk
#                  18-B-2 will flip this to blocking once base-image
#                  refresh lands.
#
# Exit codes:
#   0 — all images clean on CRITICAL (HIGH may still be present)
#   1 — one or more images have fixable, un-allowlisted CRITICAL vulns
#   2 — prerequisite missing (trivy or python3 not on PATH)
#
# Runnable locally (`make scan-images`) and from CI. Trivy DB is cached
# by the workflow via actions/cache; locally it's cached in Trivy's
# default cache dir under $HOME.

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
IGNOREFILE="${ROOT}/.trivyignore"

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

ignore_args=()
if [[ -f "${IGNOREFILE}" ]]; then
  ignore_args=(--ignorefile "${IGNOREFILE}")
  echo "── using allowlist: ${IGNOREFILE#"${ROOT}/"} ──"
fi

echo "── Trivy pass 1/2: CRITICAL (blocking), ${#images[@]} images, fixed-only ──"

fail=0
for img in "${images[@]}"; do
  printf "\n── CRITICAL: %s ──\n" "${img}"
  if ! trivy image \
      --severity CRITICAL \
      --ignore-unfixed \
      --exit-code 1 \
      --no-progress \
      --scanners vuln \
      --timeout 5m \
      "${ignore_args[@]}" \
      "${img}"; then
    fail=1
  fi
done

echo
echo "── Trivy pass 2/2: HIGH (informational), ${#images[@]} images, fixed-only ──"

for img in "${images[@]}"; do
  printf "\n── HIGH: %s ──\n" "${img}"
  # --exit-code 0: HIGH findings are reported but do not fail the scan.
  # 18-B-2 will tighten this.
  trivy image \
      --severity HIGH \
      --ignore-unfixed \
      --exit-code 0 \
      --no-progress \
      --scanners vuln \
      --timeout 5m \
      "${img}" || true
done

if [[ ${fail} -ne 0 ]]; then
  echo
  echo "❌ one or more images have fixable, un-allowlisted CRITICAL vulnerabilities" >&2
  exit 1
fi

echo
echo "✓ all ${#images[@]} images clean on CRITICAL (HIGH is informational until 18-B-2)"
