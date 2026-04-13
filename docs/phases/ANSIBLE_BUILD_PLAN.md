# Ansible Build Plan — Converting Phase 01-08 Docs into Automated Deployment

## Overview

The 9 phase documents (PHASE_00 through PHASE_08) are a comprehensive manual runbook for deploying JA4proxy from scratch on an internet-facing Ubuntu VM. This document decomposes that manual process into **29 junior-engineer-ready sub-tasks** that, when completed, produce a fully automated Ansible playbook requiring only **5 inputs** from the operator.

---

## Six-Lens Critical Review

### 2a. Security Review

1. **SSH key handling** — Phase 1 assumes the operator has an SSH key and manually adds it. Ansible needs to either accept the operator's public key as a variable or generate a new one. The key must be installed on first contact — if the target is a fresh VM with no keys, Ansible can't SSH in. **Chicken-and-egg problem.**
2. **Secret generation** — Phase 2 generates Redis passwords, Grafana admin passwords, and Redis signing keys via `openssl rand` on the build machine. Ansible should generate these on the control plane and inject them, but they must persist across playbook re-runs (idempotency).
3. **GeoIP database download** — Requires a separate manual download step with licensing. Ansible can automate the download but the URL changes and IP2Location LITE sometimes requires registration.
4. **Image digest pinning (Phase 8)** — Requires running `docker inspect` on a trusted machine. Ansible can do this but only once per deployment cycle.
5. **AppArmor profile (Phase 8)** — Needs the `apparmor` package installed and the profile loaded before JA4proxy starts. Dependency ordering concern.

### 2b. DevOps Review

1. **Build step delegation** — Phase 2 requires building the Go binary locally. Ansible can `delegate_to: localhost` but the operator needs Go toolchain installed.
2. **Tarball vs direct deploy** — The manual process creates a tarball, SCPs it, extracts it, copies files. Ansible can skip the tarball and use `copy`/`template` modules directly.
3. **Rollback strategy** — If the playbook fails mid-run, the VM is in a partially configured state.
4. **Tagged execution** — Critical for operational use: `--tags "provisioning"` or `--tags "docker"` independently.

### 2c. SRE Review

1. **Health check gates** — Between phases, the manual docs have verification checklists. Ansible needs `assert` blocks that validate each stage before proceeding.
2. **Observability of the deployment** — The playbook itself should emit structured output: what was changed, what failed, what needs manual attention.
3. **Idempotent secret management** — Passwords generated on first run must be reused on subsequent runs.
4. **Retry logic** — Docker pulls, package installs, and GeoIP downloads can fail transiently.

### 2d. Architecture Review

1. **Phase dependencies are strict** — Phase 4 cannot start until Phase 3, which requires Phase 2, which requires Phase 1.
2. **Single inventory model** — Deploy to a single VM, but the playbook should support a "control plane" group (localhost) and a "target" group (the VM).
3. **Variable precedence** — Some variables from prompts, some from auto-generation, some from defaults.

### 2e. Testing Review

1. **Verification checklists in each phase doc** — Map directly to Ansible `assert` blocks or a `validate` role.
2. **End-to-end test (Phase 7)** — `curl -vk https://127.0.0.1:443/` is a perfect post-deployment smoke test.
3. **Component health checks** — Each Docker container has a health check. Ansible can verify all containers are `running`.

### 2f. Documentation Review

1. **Phase docs are excellent but not SMART** — Acceptance criteria are checklists of commands, not measurable outcomes.
2. **No manifest.yaml exists** — Should be created for tracking phase status.

---

## Risk Summary

| # | Finding | Severity | Lens | Recommendation |
|---|---------|----------|------|----------------|
| 1 | SSH key bootstrap — fresh VM has no keys, Ansible can't connect | CRITICAL | Security | Use cloud-init or provider API to inject initial key, or use password auth for first connection only |
| 2 | Secret idempotency — passwords regenerated on re-run | HIGH | Security | Use `lookup('password', 'file=.vault/secrets')` or Ansible Vault to persist |
| 3 | GeoIP download requires manual step / licensing | MEDIUM | Security | Make it optional with a `when` conditional; prompt for file path if available |
| 4 | Partial failure leaves VM in inconsistent state | HIGH | DevOps | Add `--check` mode support; use tags for stage-by-stage execution |
| 5 | Docker image digest pinning is time-sensitive | MEDIUM | DevOps | Separate "pin digests" task from "use digests" task |
| 6 | No rollback mechanism | HIGH | DevOps | Document manual rollback per stage; use Ansible check mode for dry-run |
| 7 | Health checks not enforced between stages | MEDIUM | SRE | Add assert blocks after each role to verify prerequisites for next role |
| 8 | Phase docs don't define testable acceptance criteria | LOW | Testing | Define concrete pass/fail criteria for the playbook |

---

## Sub-Task Decomposition

### Group 1: Scaffolding — Repo Structure, Inventory, and Config Framework

| Task | Title | Size | Depends On |
|------|-------|------|------------|
| 1.1 | Create directory structure | XS (0.5h) | none |
| 1.2 | Create inventory and group_vars | S (1h) | 1.1 |
| 1.3 | Create vars_prompt playbook skeleton | S (1h) | 1.1 |
| 1.4 | Create secrets management | S (1.5h) | 1.1 |
| 1.5 | Create template files for all configs | S (2h) | 1.1 |

### Group 2: Core Logic — Ansible Roles (PHASE_01 through PHASE_08)

| Task | Title | Size | Depends On |
|------|-------|------|------------|
| 2.1 | 01-vm-provisioning: system update, packages, users | S (2h) | 1.2, 1.3 |
| 2.2 | 01-vm-provisioning: SSH hardening | XS (1h) | 2.1 |
| 2.3 | 01-vm-provisioning: UFW firewall | XS (1h) | 2.1 |
| 2.4 | 01-vm-provisioning: Fail2ban | XS (0.5h) | 2.1 |
| 2.5 | 01-vm-provisioning: Docker installation | S (1.5h) | 2.1 |
| 2.6 | 01-vm-provisioning: directory structure and limits | XS (0.5h) | 2.5 |
| 2.7 | 02-artifact-build: Build JA4proxy binary | S (2h) | 1.3 |
| 2.8 | 02-artifact-build: Deploy all configs via templates | S (2h) | 1.5, 2.6 |
| 2.9 | 02-artifact-build: GeoIP database | S (1.5h) | 2.6 |
| 2.10 | 03-ja4proxy-deploy: systemd service | S (1.5h) | 2.7, 2.8 |
| 2.11 | 03-ja4proxy-deploy: Health checks | XS (1h) | 2.10 |
| 2.12 | 04-supporting-services: Docker Compose deployment | S (2h) | 2.10 |
| 2.13 | 04-supporting-services: Container health verification | XS (0.5h) | 2.12 |
| 2.14 | 05-data-collection: Grafana dashboard provisioning | S (2h) | 2.12 |
| 2.15 | 05-data-collection: journald retention config | XS (0.5h) | 2.1 |
| 2.16 | 06-operational-security: Alerting and monitoring scripts | S (2h) | 2.10, 2.12 |
| 2.17 | 07-validation: Smoke tests | S (1.5h) | 2.12, 2.13 |
| 2.18 | 08-hardening: sysctl, AppArmor, AIDE | S (3h) | 2.10, 2.12 |

### Group 3: Wiring — Makefile, Validation, and Post-Deployment

| Task | Title | Size | Depends On |
|------|-------|------|------------|
| 3.1 | Create Makefile for common operations | XS (1h) | 1.3 |
| 3.2 | Create post-deployment summary | XS (0.5h) | 3.1 |
| 3.3 | Create README for the deploy directory | XS (0.5h) | 1.1 |

### Group 4: Testing and Validation

| Task | Title | Size | Depends On |
|------|-------|------|------------|
| 4.1 | Test playbook against fresh Ubuntu 22.04 VM | S (4h) | All above |
| 4.2 | Test idempotency (re-run playbook) | XS (1h) | 4.1 |
| 4.3 | Test partial runs (tagged execution) | XS (1h) | 4.1 |

---

## Summary

| Group | Sub-task Count | Estimated Hours |
|-------|---------------|----------------|
| **1. Scaffolding** | 5 tasks (1.1–1.5) | 7 hours |
| **2. Core Logic** | 18 tasks (2.1–2.18) | 28 hours |
| **3. Wiring** | 3 tasks (3.1–3.3) | 2 hours |
| **4. Testing** | 3 tasks (4.1–4.3) | 6 hours |
| **Total** | **29 sub-tasks** | **~43 hours** |

### Critical Blockers Before Any Implementation

1. **SSH key bootstrap strategy** — Decide: cloud-init key injection? Provider API? Password auth for first run?
2. **Secret persistence strategy** — Decide: local `.vault/secrets.yml` (gitignored)? Ansible Vault?
3. **Go build requirement** — Decide: must operator have Go installed? Or support pre-built binary path?

### Recommended Implementation Order

Scaffold first (Group 1), then build roles in dependency order (2.1 → 2.6 → 2.7 → 2.8 → 2.10 → 2.12 → 2.13), then wire everything (Group 3), then test (Group 4).
