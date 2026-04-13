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

.PHONY: deploy check cloud digests docker validate harden secrets status destroy

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
secrets:
	@bash deploy/scripts/generate-secrets.sh

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
