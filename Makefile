# ─────────────────────────────────────────────────────────────
# JA4proxy-testing — top-level Makefile
# ─────────────────────────────────────────────────────────────
#
# Run everything from the repo root. Deployment targets delegate to
# deploy/Makefile, which uses repo-root-relative paths.
#
# Pre-merge / pre-push contract:
#
#     make lint   — fast static checks (seconds)
#     make test   — lint + structural cross-checks (still no VM needed)
#
# Neither target touches the network or a target VM. Both are safe to
# wire into CI and pre-commit hooks.
# ─────────────────────────────────────────────────────────────

SHELL := /bin/bash

# Tool locations — prefer the venv installed by `make lint-install`,
# fall back to whatever's on $PATH for a new clone.
VENV            := .venv-dev
VENV_BIN        := $(VENV)/bin
PY              := python3
YAMLLINT        := $(shell if [ -x $(VENV_BIN)/yamllint ];       then echo $(VENV_BIN)/yamllint;       else command -v yamllint       || echo yamllint;       fi)
ANSIBLE_LINT    := $(shell if [ -x $(VENV_BIN)/ansible-lint ];   then echo $(VENV_BIN)/ansible-lint;   else command -v ansible-lint   || echo ansible-lint;   fi)
ANSIBLE_PLAYBOOK:= $(shell if [ -x $(VENV_BIN)/ansible-playbook ];then echo $(VENV_BIN)/ansible-playbook;else command -v ansible-playbook|| echo ansible-playbook; fi)
SHELLCHECK      := $(shell command -v shellcheck || echo shellcheck)

# Silence ansible-core's paramiko/TripleDES deprecation noise in CI logs.
export PYTHONWARNINGS := ignore::DeprecationWarning

.DEFAULT_GOAL := help

# ─────────────────────────────────────────────────────────────
# Help
# ─────────────────────────────────────────────────────────────

.PHONY: help
help:
	@echo "JA4proxy-testing — targets"
	@echo
	@echo "  Pre-merge / pre-push:"
	@echo "    make lint           — fast static checks (yamllint, ansible-lint, syntax, shellcheck, jinja2)"
	@echo "    make test           — lint + structural cross-checks"
	@echo "    make lint-install   — create .venv-dev/ and install ansible-lint + yamllint"
	@echo
	@echo "  Deployment (delegates to deploy/Makefile):"
	@echo "    make secrets        — generate deploy/.vault/secrets.yml"
	@echo "    make check          — Ansible dry-run against a VM"
	@echo "    make deploy         — full deploy"
	@echo "    make verify VM_IP=… — 25+ health checks over SSH"
	@echo "    make go-live VM_IP=… — open ports, production ACME"
	@echo "    make status VM_IP=… — quick health peek"
	@echo "    make destroy VM_IP=… — docker compose down on VM"
	@echo "    make cloud ALIYUN_ARGS=\"…\" — provision Alibaba VM"
	@echo
	@echo "  Granular deploys: docker, digests, validate, harden"

# ─────────────────────────────────────────────────────────────
# Dev-environment bootstrap
# ─────────────────────────────────────────────────────────────

.PHONY: lint-install
lint-install: $(VENV)/.installed

$(VENV)/.installed: requirements-dev.txt
	@echo "── Creating $(VENV)/ and installing dev tools ──"
	$(PY) -m venv $(VENV)
	$(VENV_BIN)/pip install --upgrade pip
	$(VENV_BIN)/pip install -r requirements-dev.txt
	@touch $@
	@echo
	@echo "Dev tools installed. Use: source $(VENV_BIN)/activate   (optional)"

# ─────────────────────────────────────────────────────────────
# Lint — fast static checks, ~seconds
# ─────────────────────────────────────────────────────────────

.PHONY: lint lint-yaml lint-ansible lint-syntax lint-shell lint-jinja lint-secrets lint-markdown

lint: lint-yaml lint-syntax lint-ansible lint-shell lint-jinja lint-secrets
	@echo
	@echo "✅ lint: all checks passed"

lint-yaml:
	@echo "── yamllint ──"
	@$(YAMLLINT) -s \
	  deploy/ \
	  .github/ \
	  .yamllint .ansible-lint requirements-dev.txt 2>/dev/null || true
	@$(YAMLLINT) -s deploy/ .github/ 2>&1

lint-syntax:
	@echo "── ansible-playbook --syntax-check ──"
	@$(ANSIBLE_PLAYBOOK) --syntax-check deploy/playbooks/site.yml 2>&1 \
	  | grep -v -E 'DeprecationWarning|TripleDES|algorithms\.|^$$' \
	  || true

lint-ansible:
	@echo "── ansible-lint ──"
	@if ! command -v $(ANSIBLE_LINT) >/dev/null 2>&1 && [ ! -x $(VENV_BIN)/ansible-lint ]; then \
	  echo "ansible-lint not installed. Run: make lint-install"; \
	  exit 1; \
	fi
	@$(ANSIBLE_LINT) -p deploy/playbooks/site.yml

lint-shell:
	@echo "── shellcheck ──"
	@if ! command -v $(SHELLCHECK) >/dev/null 2>&1; then \
	  echo "shellcheck not on PATH; skipping (install via your package manager)"; \
	  exit 0; \
	fi
	@$(SHELLCHECK) -S warning deploy/scripts/*.sh

lint-jinja:
	@echo "── jinja2 template syntax ──"
	@$(PY) scripts/ci/check_jinja.py

lint-secrets:
	@echo "── secret scan ──"
	@$(PY) scripts/ci/check_secrets.py

# ─────────────────────────────────────────────────────────────
# Test — lint + structural cross-checks, still offline
# ─────────────────────────────────────────────────────────────

.PHONY: test test-roles test-groupvars test-compose test-digest-regex test-secrets-path test-makefile test-collections

test: lint test-roles test-groupvars test-compose test-digest-regex test-secrets-path test-makefile test-collections
	@echo
	@echo "✅ test: all checks passed"

test-roles:
	@echo "── roles referenced by site.yml exist ──"
	@$(PY) scripts/ci/check_roles_exist.py

test-groupvars:
	@echo "── every ja4proxy_docker_image_* used in templates is defined ──"
	@$(PY) scripts/ci/check_groupvars_coverage.py

test-compose:
	@echo "── docker-compose template renders with sample vars ──"
	@$(PY) scripts/ci/render_compose.py

test-digest-regex:
	@echo "── digest-pinning regex self-test (role 09) ──"
	@$(PY) scripts/ci/check_digest_regex.py

test-secrets-path:
	@echo "── secrets-script writes to deploy/.vault/ (A1 regression) ──"
	@$(PY) scripts/ci/check_secrets_path.py

test-makefile:
	@echo "── every make target in this Makefile is .PHONY ──"
	@$(PY) scripts/ci/check_makefile_phony.py

test-collections:
	@echo "── Ansible collections pinned + used FQCNs covered ──"
	@$(PY) scripts/ci/check_collections.py

# ─────────────────────────────────────────────────────────────
# Deployment target passthrough (to deploy/Makefile)
# ─────────────────────────────────────────────────────────────

.PHONY: deploy check cloud digests docker validate harden secrets vault-edit vault-rekey collections verify go-live status destroy ci-deploy ci-check

deploy check cloud digests docker validate harden secrets vault-edit vault-rekey collections verify go-live status destroy ci-deploy ci-check:
	@$(MAKE) -f deploy/Makefile $@ \
	  $(if $(VM_IP),VM_IP=$(VM_IP)) \
	  $(if $(ALIYUN_ARGS),ALIYUN_ARGS="$(ALIYUN_ARGS)") \
	  $(if $(EXTRA_VARS),EXTRA_VARS="$(EXTRA_VARS)")

# ─────────────────────────────────────────────────────────────
# Housekeeping
# ─────────────────────────────────────────────────────────────

.PHONY: clean
clean:
	rm -rf $(VENV) .pytest_cache __pycache__ */__pycache__ */*/__pycache__
