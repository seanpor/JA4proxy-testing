# Phase 16 — Lint coverage to 100%

Last reviewed: 2026-04-16

Adds static linting for every source-file type in the repo that was
previously uncovered. After this phase, `make lint` catches syntax and
style issues across Python, shell, JSON, and Markdown — not just
YAML/Ansible/Jinja2.

## 16-A — Python linting with ruff

Add `ruff` to `requirements-dev.txt`, configure in `pyproject.toml`,
wire into `make lint-python`. All 37 `.py` files must pass.

## 16-B — Shellcheck for all `.sh` files

Widen the shellcheck glob from `deploy/scripts/*.sh` to every `.sh`
file under `deploy/` (catches `deploy/files/scripts/health-check.sh`
and role-embedded copies).

## 16-C — JSON validation

Add a CI check that parses every `.json` file (14 Grafana dashboards)
and fails on syntax errors.

## 16-D — Markdown linting

Add a Python-based markdown linter (`pymarkdownlnt` or `mdformat`)
so all 42 `.md` files are style-checked without a Node.js dependency.
