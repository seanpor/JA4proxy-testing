#!/usr/bin/env bash
set -euo pipefail

IMAGE_NAME="ja4proxy-lint:latest"
DOCKERFILE=".github/Dockerfile.lint"

# Build if missing
if [[ "$(docker images -q ${IMAGE_NAME} 2> /dev/null)" == "" ]]; then
  echo "── Building lint container (${IMAGE_NAME}) ──"
  docker build -t "${IMAGE_NAME}" -f "${DOCKERFILE}" .
fi

# Run the command inside the container
# We mount the current directory and pass the command through
# We mount docker.sock so trivy can scan images if needed
# We run as the host user to prevent root-owned files (e.g. .ruff_cache) from being created
docker run --rm \
  --user "$(id -u):$(id -g)" \
  -e HOME=/tmp \
  -v "$(pwd):/work" \
  -v "/var/run/docker.sock:/var/run/docker.sock" \
  -e GH_TOKEN="${GH_TOKEN:-}" \
  "${IMAGE_NAME}" -c "$*"
