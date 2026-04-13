# JA4proxy Deploy — Operational Reference

> **Start here**: See the [project root README](../README.md) for the full guide, architecture, and quick start.

This directory contains the complete Ansible deployment system. This file is a quick operational reference for common tasks.

---

## Quick Commands

```bash
# Full workflow (new VM)
make cloud ALIYUN_ARGS="..."     # Provision Alibaba Cloud VM
make secrets                      # Generate passwords (once)
make deploy                       # Deploy (locked down)
make verify VM_IP=<ip>            # 25+ health checks via SSH
make go-live VM_IP=<ip>           # Open to public
```

## Makefile Targets

| Target | Description |
|--------|-------------|
| `make deploy` | Full deployment (all 10 phases) |
| `make check` | Dry run — see what would change |
| `make cloud` | Provision Alibaba Cloud VM |
| `make secrets` | Generate/review secrets |
| `make verify` | Run 25+ local health checks |
| `make go-live` | Open ports to public internet |
| `make digests` | Pin Docker image SHA-256 digests |
| `make docker` | Docker Compose only |
| `make validate` | Smoke tests only |
| `make harden` | Security hardening only |
| `make status` | Quick health check |
| `make destroy` | Stop all Docker containers |
| `make ci-deploy` | CI/CD deployment (env vars) |

## Directory Structure

```
deploy/
├── Makefile                          # All operational commands
├── ansible.cfg                       # Ansible defaults
├── inventory/
│   ├── hosts.ini                     # Dynamic inventory
│   └── group_vars/all.yml            # 137 configurable variables
├── playbooks/
│   └── site.yml                      # Master playbook (10 roles)
├── roles/
│   ├── 01-vm-provisioning/           # SSH, UFW, Fail2ban, Docker
│   ├── 02-artifact-build/            # Build binary, deploy configs
│   ├── 03-ja4proxy-deploy/           # systemd, health checks
│   ├── 04-supporting-services/       # Docker Compose (7 containers)
│   ├── 05-data-collection/           # Grafana, journald
│   ├── 06-operational-security/      # Scripts, cron, alerting
│   ├── 07-validation/                # Smoke tests
│   ├── 08-hardening/                 # sysctl, AppArmor, AIDE
│   ├── 09-image-digests/             # SHA-256 pinning
│   └── 10-go-live/                   # Open ports, production TLS
├── scripts/
│   ├── generate-secrets.sh
│   ├── provision-alibaba-cloud.sh
│   ├── health-check.sh
│   └── verify-local.sh
├── templates/                        # 21 Jinja2 templates
└── files/                            # Grafana dashboards
```

## Secrets

- Generated once: `make secrets`
- Stored in: `deploy/.vault/secrets.yml` (gitignored)
- Never committed to git

## CI/CD

```bash
JA4PROXY_DOMAIN=x \
JA4PROXY_VM_HOST=y \
JA4PROXY_ADMIN_IP=z \
JA4PROXY_SSH_PUBLIC_KEY="..." \
JA4PROXY_BUILD_MACHINE_GO_PATH=/path \
make ci-deploy
```

## Troubleshooting

Full troubleshooting guide: [../README.md#troubleshooting](../README.md#troubleshooting)

Rollback procedures: [../docs/phases/RUNBOOK.md](../docs/phases/RUNBOOK.md)
