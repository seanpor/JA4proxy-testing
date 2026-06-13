# Phase 22 — Docker-based Portability

**Author:** Gemini, 2026-06-11
**Context:** Local toolchain drift (different versions of `ansible-lint`, `ruff`, `shellcheck`, etc.) was causing "works on my machine" issues where a developer's local `make test` passed while CI failed. Phase 22 wraps the dev loop in a Docker container to ensure total parity between local development and CI.

## 22-A — Containerized Dev Loop

**Scope.**
- `.github/Dockerfile.lint` — a Debian-based container with all required linting and testing tools pre-installed.
- `scripts/ci/docker-lint.sh` — a wrapper script that builds/runs the container, mounting the project root and the Docker socket.
- `Makefile` — updated `lint`, `test`, and `scan-images` targets to automatically re-invoke themselves inside the container if Docker is available.

**Why.**
Ensuring that every developer runs exactly the same tool versions as CI eliminates a major source of friction and prevents "governance theatre" where broken local environments skip checks that CI then catches.

**Acceptance.**
- `make lint` / `make test` / `make scan-images` automatically run inside the container.
- Results are consistent between local and CI.
- Volume mounts preserve host-user ownership of generated files (like `.ruff_cache`).

**Files.**
- `.github/Dockerfile.lint`
- `scripts/ci/docker-lint.sh`
- `Makefile`
- `requirements-dev.txt` (bumped to match container)
- `deploy/requirements.yml` (bumped to match container)
