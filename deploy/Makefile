# ─────────────────────────────────────────────────────────────
# JA4proxy — Ansible Deployment Makefile
# ─────────────────────────────────────────────────────────────
#
# Prerequisites:
#   - Ansible 2.14+ installed on control machine
#   - Go toolchain (if building from source)
#   - SSH access to target VM
#
# Usage:
#   make deploy          — Full deployment
#   make check           — Dry run (check mode)
#   make cloud           — Provision Alibaba Cloud VM
#   make digests         — Pin Docker image SHA-256 digests
#   make docker          — Docker Compose only (Phase 4)
#   make validate        — Smoke tests only (Phase 7)
#   make harden          — Security hardening only (Phase 8)
#   make secrets         — Generate/review secrets
#   make status          — SSH in and check health
#   make destroy         — Stop all Docker containers
# ─────────────────────────────────────────────────────────────

INVENTORY   := -i deploy/inventory/hosts.ini
PLAYBOOK    := deploy/playbooks/site.yml
EXTRA_VARS  ?=
ANSIBLE     := ansible-playbook $(INVENTORY) $(PLAYBOOK)

# Alibaba Cloud provision args (pass through from command line)
# Usage: make cloud ALIYUN_ARGS="--region eu-central-1 --ssh-key-name mykey --admin-ip 1.2.3.4"
ALIYUN_ARGS ?=

.PHONY: deploy check cloud digests docker validate harden secrets vault-edit vault-rekey collections status destroy idempotency

deploy:
	@echo "╔══════════════════════════════════════════════════════╗"
	@echo "║   JA4proxy — Full Deployment                        ║"
	@echo "╚══════════════════════════════════════════════════════╝"
	$(ANSIBLE) $(EXTRA_VARS)

check:
	@echo "Running in check mode (dry run)..."
	$(ANSIBLE) --check --diff $(EXTRA_VARS)

# ── Cloud Provisioning ──────────────────────────────────────
cloud:
	@echo "╔══════════════════════════════════════════════════════╗"
	@echo "║   JA4proxy — Alibaba Cloud VM Provisioning           ║"
	@echo "╚══════════════════════════════════════════════════════╝"
	@bash deploy/scripts/provision-alibaba-cloud.sh $(ALIYUN_ARGS)

# ── Partial Deployments ─────────────────────────────────────
digests:
	$(ANSIBLE) --tags "digests,phase9" $(EXTRA_VARS)

docker:
	$(ANSIBLE) --tags "docker,phase4" $(EXTRA_VARS)

validate:
	$(ANSIBLE) --tags "validation,phase7" $(EXTRA_VARS)

harden:
	$(ANSIBLE) --tags "hardening,phase8" $(EXTRA_VARS)

# ── Operations ──────────────────────────────────────────────
# Install pinned Ansible collections from deploy/requirements.yml.
collections:
	@ansible-galaxy collection install -r deploy/requirements.yml

# Generate missing secrets and (re-)encrypt the vault file at rest.
secrets:
	@bash deploy/scripts/generate-secrets.sh

# Edit the encrypted secrets file in $EDITOR.
vault-edit:
	@test -s deploy/.vault/.vault-pass || { \
	  echo "No vault password file. Run: make secrets"; exit 1; }
	@ansible-vault edit \
	  --vault-password-file deploy/.vault/.vault-pass \
	  deploy/.vault/secrets.yml

# Rotate the vault password (prompts for the new one).
vault-rekey:
	@test -s deploy/.vault/.vault-pass || { \
	  echo "No vault password file. Run: make secrets"; exit 1; }
	@ansible-vault rekey \
	  --vault-password-file deploy/.vault/.vault-pass \
	  deploy/.vault/secrets.yml

# 14-D: idempotency check — re-runs the playbook and asserts the
# second run is a no-op. Cheap insurance against silent drift.
idempotency:
ifndef VM_IP
	$(error VM_IP is required. Usage: make idempotency VM_IP=1.2.3.4)
endif
	@VM_IP=$(VM_IP) bash deploy/scripts/check-idempotency.sh

# Verify all services locally via SSH (no public ports needed)
verify:
ifndef VM_IP
	$(error VM_IP is required. Usage: make verify VM_IP=47.254.123.45)
endif
	@echo "Running local verification on $(VM_IP)..."
	@ssh root@$(VM_IP) 'bash -s' < deploy/scripts/verify-local.sh

# Go-live: open ports to public and switch to production ACME
go-live:
ifndef VM_IP
	$(error VM_IP is required. Usage: make go-live VM_IP=47.254.123.45)
endif
	@echo "╔══════════════════════════════════════════════════════╗"
	@echo "║   JA4proxy — Going Live (opening to public)          ║"
	@echo "╚══════════════════════════════════════════════════════╝"
	$(ANSIBLE) --tags "go-live,phase10" -e ja4proxy_go_live_confirm=true $(EXTRA_VARS)

status:
ifndef VM_IP
	$(error VM_IP is required. Usage: make status VM_IP=47.254.123.45)
endif
	@echo "Connecting to $(VM_IP) for health check..."
	@ssh root@$(VM_IP) \
	  "echo '── Services ──' && systemctl is-active ja4proxy && docker compose -f /opt/ja4proxy-docker/docker-compose.yml ps && echo '' && echo '── JA4proxy Health ──' && curl -s http://127.0.0.1:9090/health"

destroy:
ifndef VM_IP
	$(error VM_IP is required. Usage: make destroy VM_IP=47.254.123.45)
endif
	@echo "Stopping all Docker containers on $(VM_IP)..."
	@ssh root@$(VM_IP) "cd /opt/ja4proxy-docker && docker compose down"

# ── CI/CD Friendly ──────────────────────────────────────────
# All vars can be passed via environment or EXTRA_VARS:
#   make deploy EXTRA_VARS="-e ja4proxy_domain=x -e ja4proxy_vm_host=y ..."
ci-deploy:
	$(ANSIBLE) --extra-vars "$(EXTRA_VARS)"

ci-check:
	$(ANSIBLE) --check --diff --extra-vars "$(EXTRA_VARS)"
