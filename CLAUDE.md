# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this repo is

Ansible-based deployment automation for a **research honeypot** that puts [JA4proxy](https://github.com/FoxIO-LLC/ja4) in front of a fake HTTPS form to collect real-world bot/attacker TLS fingerprints. It is *not* the JA4proxy source code and it is *not* a production deployment (that lives in a sibling repo, `JA4proxy4`). This repo only owns the research-specific stack: honeypot + observability + staged go-live.

There is no application source code here — the deliverable is the Ansible playbook, roles, templates, and Makefile. JA4proxy itself is built from a sibling Go checkout (`ja4proxy_build_machine_go_path`) or supplied as a prebuilt binary.

## Commands

All `make` targets must be run from the **repo root**, not from `deploy/`. The Makefile and `ansible.cfg` both use paths relative to the repo root (`deploy/inventory/hosts.ini`, `deploy/playbooks/site.yml`, etc.).

```
make secrets           # Generate/rotate passwords into deploy/.vault/secrets.yml (gitignored)
make check             # Ansible dry run (--check --diff)
make deploy            # Full deployment, prompts for domain/VM/admin IP/SSH key
make verify VM_IP=...  # Run deploy/scripts/verify-local.sh on the VM via SSH (25+ checks)
make go-live VM_IP=... # Phase 10 only: rebind to 0.0.0.0, switch to prod ACME, open UFW
make status VM_IP=...  # Quick health peek via SSH
make destroy VM_IP=... # docker compose down on the VM (does not destroy VM)
make cloud ALIYUN_ARGS="..."  # Provision Alibaba Cloud VM (VPC + ECS + EIP)
```

Partial deploys by tag: `make docker` (phase4), `make validate` (phase7), `make harden` (phase8), `make digests` (phase9). Every role is tagged both by name (`docker`, `hardening`, …) and by `phaseN`.

CI/CD path skips prompts by setting env vars (`JA4PROXY_DOMAIN`, `JA4PROXY_VM_HOST`, `JA4PROXY_ADMIN_IP`, `JA4PROXY_SSH_PUBLIC_KEY`, `JA4PROXY_BUILD_MACHINE_GO_PATH` or `JA4PROXY_PREBUILT_BINARY_PATH`) and using `make ci-deploy` / `make ci-check`.

Running a single role directly:

```
ansible-playbook -i deploy/inventory/hosts.ini deploy/playbooks/site.yml --tags phase4
```

## Architecture

Traffic path on the target VM:

```
Internet → HAProxy :443 (TLS passthrough, PROXY v2)
         → JA4proxy :8080 (L4 interceptor, Go systemd service)
         → Caddy :8081 (HTTPS honeypot, static warning page)
           ↕
         Redis :6379 (bans, rate-limit counters — internal only)
```

Observability is parallel: Prometheus scrapes JA4proxy (`:9090/metrics`) and HAProxy; Promtail ships journald + Docker logs to Loki; Grafana reads both.

**Key split: JA4proxy runs as systemd on the host; everything else is Docker Compose** (`/opt/ja4proxy-docker/docker-compose.yml`). Redis is wrapped by a `ja4proxy-redis` systemd unit so systemd can order JA4proxy after it.

## Staged deployment model (important)

`make deploy` intentionally does **not** expose the service publicly. It leaves the VM in a **locked** state:

- Docker ports bound to `127.0.0.1` only
- Caddy uses self-signed certs
- UFW blocks 80/443 from the public internet (only 22 from `ja4proxy_admin_ip` is open)

You then run `make verify VM_IP=…` to run all health checks over SSH, and only `make go-live VM_IP=…` (Phase 10) rebinds to `0.0.0.0`, switches to production Let's Encrypt, and opens UFW. The `ja4proxy_go_live_confirm=true` flag is required (set automatically by the `go-live` target) so Phase 10 is inert during normal `make deploy`.

When editing roles, preserve this invariant: **nothing before Phase 10 should bind a public port or open UFW for 80/443.**

## Playbook structure

`deploy/playbooks/site.yml` is the only playbook. It:

1. Collects inputs via `vars_prompt`, overrides them from `JA4PROXY_*` env vars in `pre_tasks`, asserts they're present and valid.
2. Runs `scripts/generate-secrets.sh` on the control machine and loads `deploy/.vault/secrets.yml` (gitignored) into `ja4proxy_secrets`.
3. Adds the target to inventory dynamically via `add_host` (the static `hosts.ini` is populated by `provision-alibaba-cloud.sh`).
4. Runs ten phase-numbered roles in order. Each role is tagged `[<name>, phaseN]`.

Defaults for ~137 variables live in `deploy/inventory/group_vars/all.yml`. Templates in `deploy/templates/` (~21 Jinja2 files) render configs for HAProxy, Caddy, Prometheus, Loki, Promtail, Grafana provisioning, the JA4proxy `proxy.yml`, the systemd unit, and the Docker Compose file.

## The "dial" concept

JA4proxy's enforcement level is a single integer 0–100 (`ja4proxy_dial`), exposed as `dial:` in `/opt/ja4proxy/config/proxy.yml` and reloadable with `SIGHUP`. **Default is 0 (monitor-only, block nothing).** The dial escalation plan is in `README.md` and `docs/phases/PHASE_07_VALIDATION_TESTING.md`. Do not raise the default in code without an explicit request — the monitor-first posture is a deliberate design constraint.

## Relationship to JA4proxy4

A sibling repo (`JA4proxy4`) handles enterprise production deployment (K8s, Datadog, Helm, etc.). This repo must **not** duplicate that work — it is scoped to the research honeypot stack and the staged public-exposure workflow. If a task sounds like it belongs to production monitoring/alerting integrations, check whether it should live in `JA4proxy4` instead.

## Secrets & gitignore

- `deploy/.vault/secrets.yml` — generated by `make secrets`, gitignored, referenced by the playbook. Regenerating is idempotent (existing values are preserved).
- `docs/` is listed in `.gitignore` but `docs/phases/*.md` **are** tracked (the ignore entry predates them — don't delete the docs tree assuming it's ephemeral).

## QWEN.md

`QWEN.md` exists for another assistant and is partially stale (e.g. it describes JA4proxy as listening on 80/443 directly, which is not how the current deployment works — HAProxy fronts TLS and hands off via PROXY v2 to JA4proxy on :8080). Prefer `README.md` and the actual roles/templates as the source of truth.
