# JA4proxy-testing vs JA4proxy4 — Duplication Analysis

## What Already Exists in JA4proxy4

### Deploy/ansible/ (Enterprise Ansible)
- **roles/ja4proxy/** — Full Ansible role for deploying JA4proxy Go binary
  - Supports binary, docker, and Podman Quadlet modes
  - Systemd service deployment with health checks
  - Molecule tests (3 scenarios: default, servicenow-enabled/disabled)
  - ServiceNow CMDB registration
  - Templates: `proxy.yml.j2`, `ja4proxy.service.j2`, `ja4proxy.container.j2`
- **roles/redis-secure/** — Redis hardening role with ACL, monitoring
- **playbooks/** — Deploy, policy apply, emergency ops, monthly report
- **deploy-redis.yml** — Redis deployment playbook

### Deploy/helm/ (Kubernetes)
- Full Helm chart: DaemonSet, ConfigMap, Service, ServiceMonitor, Redis, Secret

### Deploy/terraform/
- Infrastructure-as-code templates

### Deploy/monitoring/ (Full Observability Stack)
- **prometheus/prometheus.yml** — Production scraping config
- **prometheus/alerts.yml** — Production alert rules
- **prometheus/recording_rules.yml** — Recording rules
- **alertmanager/alertmanager.yml** — Alert routing
- **alertmanager/rules/** — 10 rule files (proxy, redis, security, SLO, TLS, TAP, etc.)
- **grafana/dashboards/** — 5 dashboards (overview, infrastructure, analytics, capacity, tap_sensor)
- **grafana/provisioning/** — Datasource and dashboard provisioning
- **loki/loki-config.yml** — Loki storage config
- **loki/promtail-config.yml** — Promtail log shipping
- **metrics_registry.md** — Complete metrics documentation

### Deploy/datadog/
- Custom check, OpenMetrics config, full dashboard JSON, monitors JSON

### Deploy/dynatrace/
- Custom extension with plugin.py

### Deploy/nagios/
- `check_ja4proxy.py` Nagios check script

### Deploy/zabbix/
- Zabbix monitoring template XML

## What JA4proxy-testing Needs (Research Honeypot Specific)

JA4proxy-testing deploys a **COMPLETELY DIFFERENT stack** — an internet-facing research honeypot. It needs:

1. **HAProxy** with TLS passthrough (NOT in JA4proxy4)
2. **Caddy** with honeypot HTML (NOT in JA4proxy4)
3. **Full VM provisioning** from scratch (SSH hardening, UFW, Fail2ban, Docker install)
4. **Redis in Docker** (JA4proxy4 has a systemd Redis role)
5. **Research-focused Grafana dashboards** (JA4proxy4 has production dashboards)
6. **Docker Compose stack** for all supporting services (JA4proxy4 deploys individually)

## Overlap Analysis

| Component | JA4proxy4 | JA4proxy-testing | Action |
|-----------|-----------|------------------|--------|
| **proxy.yml.j2** | ✅ Exists (enterprise config) | ✅ Created (research config) | **DELETE from testing** — use JA4proxy4's role |
| **ja4proxy.service.j2** | ✅ Exists (enterprise systemd) | ✅ Created (research systemd) | **DELETE from testing** — use JA4proxy4's role |
| **Grafana dashboards** | ✅ 5 production dashboards | ✅ 7 research skeletons | **KEEP in testing** — different purpose |
| **Prometheus config** | ✅ Production config | ✅ Research config | **KEEP in testing** — different scrape targets |
| **Loki config** | ✅ Production config | ✅ Research config | **KEEP in testing** — same base, different retention |
| **Promtail config** | ✅ Production config | ✅ Research config | **KEEP in testing** — different log sources |
| **Alertmanager** | ✅ 10 rule files | ❌ Not created | **REFERENCE JA4proxy4** — don't recreate |
| **Datadog/Dynatrace/Nagios/Zabbix** | ✅ All exist | ❌ Not needed | **N/A** — research VM doesn't use these |
| **Helm charts** | ✅ Full chart | ❌ Not needed | **N/A** — research VM is bare metal/VM |
| **Terraform** | ✅ Exists | ❌ Not needed | **N/A** — use Alibaba Cloud console/API |
| **Ansible role** | ✅ `roles/ja4proxy/` | ✅ `roles/03-ja4proxy-deploy/` | **MERGE/REFERENCE** — don't duplicate systemd |

## Key Finding

**JA4proxy-testing should NOT duplicate the Ansible roles from JA4proxy4.**

Instead, it should:
1. **Reference** JA4proxy4's `roles/ja4proxy/` for JA4proxy binary deployment
2. **Focus** on the research honeypot stack (HAProxy + Caddy + Docker Compose + monitoring)
3. **Use** JA4proxy4's monitoring configs as the baseline for research monitoring
4. **Create** only what's unique to the research honeypot scenario

## Recommended Approach

### Option A: Submodule JA4proxy4's Ansible roles
```
deploy/
├── ansible/
│   ├── vendor/ja4proxy/          → submodule → JA4proxy4/deploy/ansible/roles/ja4proxy/
│   ├── vendor/redis-secure/      → submodule → JA4proxy4/deploy/ansible/roles/redis-secure/
│   └── vendor/monitoring/        → submodule → JA4proxy4/monitoring/
└── roles/
    ├── 01-vm-provisioning/       → NEW: VM hardening from scratch
    ├── 02-artifact-build/        → NEW: Build + transfer for research
    ├── 03-ja4proxy-deploy/       → USE vendor/ja4proxy/ (REFERENCE)
    ├── 04-honeypot-stack/        → NEW: HAProxy + Caddy + Docker Compose
    └── 05-validation/            → NEW: Smoke tests for honeypot
```

### Option B: Reference JA4proxy4 via git submodule at repo level
```
JA4proxy-testing/
├── ja4proxy/                     → submodule → JA4proxy4 repo
└── deploy/
    ├── playbooks/site.yml        → Uses ja4proxy/deploy/ansible/roles/
    └── roles/
        ├── 01-vm-provisioning/   → NEW
        ├── 02-honeypot-stack/    → NEW
        └── 03-validation/        → NEW
```

### Option C: Keep separate (simplest for now)
Keep JA4proxy-testing as a standalone deployment plan for the research honeypot.
The Ansible roles are DIFFERENT enough that they don't need to share code.
Only reference JA4proxy4's monitoring dashboards as the "production" baseline.

## Recommendation: Option C for Now

The research honeypot deployment (JA4proxy-testing) and the enterprise deployment (JA4proxy4) have **different audiences, different infrastructure, and different goals**. Keeping them separate avoids tight coupling.

What we SHOULD do:
1. **Delete** the duplicate `proxy.yml.j2` and `ja4proxy.service.j2` from JA4proxy-testing
2. **Reference** JA4proxy4's Ansible role in the deployment plan
3. **Keep** the research-specific roles (VM provisioning, honeypot stack, validation)
4. **Reference** JA4proxy4's monitoring stack as the "production monitoring" standard
5. **Document** the relationship clearly in the README
