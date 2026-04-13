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
#   make provision       — VM provisioning only (Phase 1)
#   make docker          — Docker Compose only (Phase 4)
#   make validate        — Smoke tests only (Phase 7)
#   make harden          — Security hardening only (Phase 8)
#   make secrets         — Generate/review secrets
#   make status          — SSH in and check health
#   make destroy         — Stop all Docker containers
# ─────────────────────────────────────────────────────────────

INVENTORY   := -i deploy/inventory/hosts.ini
PLAYBOOK    := deploy/playbooks/site.yml
ANSIBLE     := ansible-playbook $(INVENTORY)

.PHONY: deploy check provision docker validate harden secrets status destroy

deploy:
	@echo "╔══════════════════════════════════════════════════════╗"
	@echo "║   JA4proxy — Full Deployment                        ║"
	@echo "╚══════════════════════════════════════════════════════╝"
	$(ANSIBLE) $(PLAYBOOK)

check:
	@echo "Running in check mode (dry run)..."
	$(ANSIBLE) $(PLAYBOOK) --check --diff

provision:
	$(ANSIBLE) $(PLAYBOOK) --tags "provisioning"

docker:
	$(ANSIBLE) $(PLAYBOOK) --tags "docker"

validate:
	$(ANSIBLE) $(PLAYBOOK) --tags "validation"

harden:
	$(ANSIBLE) $(PLAYBOOK) --tags "hardening"

secrets:
	@bash deploy/scripts/generate-secrets.sh

status:
	@echo "Connecting to VM for health check..."
	ssh root@$$(grep -oP '^\S+' deploy/inventory/hosts.ini | head -1) \
	  "systemctl is-active ja4proxy && docker compose -f /opt/ja4proxy-docker/docker-compose.yml ps"

destroy:
	@echo "Stopping all Docker containers..."
	ssh root@$$(grep -oP '^\S+' deploy/inventory/hosts.ini | head -1) \
	  "cd /opt/ja4proxy-docker && docker compose down"
