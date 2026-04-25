#!/usr/bin/env bash
# 18-B + 18-B-2: Scan every image referenced by the rendered compose
# template for fixable HIGH/CRITICAL vulnerabilities.
#
# Single blocking pass: HIGH and CRITICAL together, `--ignore-unfixed`
# (no point failing on a CVE that has no fix yet), `--exit-code 1`.
# Both severities honour `.trivyignore` — the repo-root allowlist with
# mandatory `# expires: YYYY-MM-DD` comments, enforced separately by
# scripts/ci/check_image_scan.py so that every entry is periodically
# re-decided.
#
# Exit codes:
#   0 — all images clean on HIGH + CRITICAL after allowlist
#   1 — one or more images have fixable, un-allowlisted HIGH/CRITICAL
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

echo "── Trivy: HIGH+CRITICAL blocking pass, ${#images[@]} images, fixed-only ──"

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
      "${ignore_args[@]}" \
      "${img}"; then
    fail=1
  fi
done

if [[ ${fail} -ne 0 ]]; then
  echo
  echo "❌ one or more images have fixable, un-allowlisted HIGH/CRITICAL vulnerabilities" >&2
  exit 1
fi

echo
echo "✓ all ${#images[@]} images clean on HIGH+CRITICAL (after .trivyignore allowlist)"

# 21-E: the same SBOM role 02 ships must be scanned by the same severity
# + allowlist rules — otherwise the SBOM is audit theatre. Runs here so
# `make scan-images` is in parity with ci.yml's image-scan job, and the
# local `make lint-all` contract doesn't silently skip a CI gate.
SBOM="/tmp/compose.cdx.json"
echo
echo "── Rendering compose SBOM → ${SBOM} ──"
python3 "${ROOT}/scripts/ci/render_compose.py" --sbom "${SBOM}"

echo
echo "── Trivy sbom: HIGH+CRITICAL blocking pass over compose SBOM ──"
trivy sbom \
    --severity HIGH,CRITICAL \
    --ignore-unfixed \
    --exit-code 1 \
    --no-progress \
    "${ignore_args[@]}" \
    "${SBOM}"

echo
echo "✓ compose SBOM clean on HIGH+CRITICAL (after .trivyignore allowlist)"
