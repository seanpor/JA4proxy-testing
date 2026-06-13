# JA4proxy Real-World Testing Deployment Plan

Last reviewed: 2026-06-13

## Executive Summary

This document provides a comprehensive, phase-by-phase implementation plan for deploying JA4proxy in front of an internet-facing honeypot to collect real-world bot attack data and validate JA4 fingerprinting effectiveness in production-like conditions.

**Critical Constraints:**
- System MUST be clearly marked as a test environment with impossible-to-miss warnings.
- NO real PII collection or persistence.
- Isolated from production infrastructure.
- Monitor-first approach (no blocking initially).
- Full legal compliance with clear disclaimers.

---

## 1. Architecture and Staged Deployment

The deployment follows a rigid 3-stage model managed by Ansible, ensuring the system is fully verified before exposure to the public internet.

### Network Flow

```
Internet (Encrypted) -> [HAProxy: TLS Passthrough] -> [JA4proxy: L4 Interceptor] -> [Caddy: HTTPS Honeypot]
                                                              |
                                                      [Redis: State Store]
```

### Staged Rollout

| Stage | Port Bindings | TLS | UFW 80/443 | Access |
|-------|--------------|-----|------------|--------|
| **Locked** (Deploy) | `127.0.0.1` | Self-signed | Closed | SSH tunnel only |
| **Verified** (Test) | `127.0.0.1` | Self-signed | Closed | SSH tunnel (confirmed health) |
| **Live** (Go-Live) | `0.0.0.0` (Public) | Let's Encrypt | Open | Direct HTTPS |

---

## 2. Implementation Phases

The deployment is executed via Ansible playbooks (`deploy/playbooks/site.yml`), breaking down the implementation into discrete roles:

### Phase 1: VM Provisioning (`01-vm-provisioning`)
- Base OS updates (Ubuntu 22.04 LTS).
- Setup of a dedicated `ja4proxy` system user.
- SSH hardening (key-only authentication, port 22 access restricted to Admin IP).
- UFW firewall initialization (default deny).
- Fail2ban and Docker installation.

### Phase 2: Artifact Preparation (`02-artifact-build`)
- Cross-compile JA4proxy Go binary or download a verified checksum release.
- Deploy Jinja2 templates for configurations (`Caddyfile`, `haproxy.cfg`, Prometheus, Loki).
- Download IP2Location GeoIP databases.

### Phase 3: JA4proxy Deployment (`03-ja4proxy-deploy`)
- Install JA4proxy as a `systemd` service.
- Apply security constraints (e.g., `NoNewPrivileges`, `PrivateTmp`, `ProtectSystem`).

### Phase 4: Supporting Services (`04-supporting-services`)
- Deploy Docker Compose stack:
  - **HAProxy**: TLS passthrough and PROXY protocol v2.
  - **Redis**: Shared state, ban lists, and rate limits.
  - **Caddy**: Honeypot serving a static warning page.
  - **Prometheus/Grafana/Loki/Promtail**: Observability and metric scraping.

### Phase 5 & 6: Data Collection and Operations (`05-data-collection`, `06-operational-security`)
- Configure Grafana dashboards and Loki retention.
- Setup cron jobs for health checks and backups.
- Initialize dead-man's-switch heartbeat.

### Phase 7 & 8: Validation and Hardening (`07-validation`, `08-hardening`)
- Execute local verification script (`verify-local.sh`).
- Apply kernel `sysctl` hardening, AppArmor profiles, and initialize AIDE (Advanced Intrusion Detection Environment).

### Phase 9: Digest Pinning (`09-image-digests`)
- Enforce Docker image pulling by SHA-256 digests to prevent supply chain tag-mutation attacks.

### Phase 10: Go-Live (`10-go-live`)
- The final, deliberate step.
- Re-bind HAProxy to public `0.0.0.0`.
- Switch Caddy to production Let's Encrypt (ACME).
- Open UFW ports 80 and 443.

---

## 3. Honeypot Application and Governance

### Honeypot Design (`deploy/templates/honeypot-index.html`)
- The backend is deliberately static HTML served by Caddy.
- Features massive, impossible-to-miss visual warnings: "SECURITY TEST ENVIRONMENT" and "THIS IS NOT A REAL WEBSITE".
- Form submissions are actively discarded by the server configuration; no payload data is logged or persisted.

### Legal and Ethics Posture (`docs/governance/`)
- Operations comply with GDPR Article 6(1)(f) (Legitimate Interests).
- PII is strictly avoided; logged IP addresses are HMAC-anonymized prior to any research export.
- Publicly accessible `privacy.html` and `security.txt` clearly outline the research nature of the system and provide abuse contacts.

---

## 4. Graduated Dial Escalation

JA4proxy utilizes a `dial` setting to control enforcement strictness. It defaults to `0` (monitor-only) to establish baselines before enacting blocking mechanisms.

| Period | Dial | Behavior | Goal |
|--------|------|----------|------|
| **Weeks 1-2** | 0 | Monitor | Establish traffic baselines, analyze fingerprint distribution. |
| **Weeks 2-3** | 20 | Flag | Evaluate False Positive rate based on counterfactual logging. |
| **Weeks 3-4** | 40 | Rate Limit | Test effectiveness against sustained bot behavior. |
| **Weeks 4-5** | 55 | Tarpit | Exhaust attacker resources. |
| **Weeks 6+** | 85-100 | Block/Ban | Full enforcement against known malicious signatures. |

---

## 5. Operations and Maintenance

### Key Commands
- `make deploy`: Deploy locked-down stack.
- `make verify`: Run 25+ local integration tests via SSH.
- `make go-live`: Expose honeypot to the internet (requires confirmation).
- `make status`: View service health and active ban counts.
- `make destroy`: Stop containers and the JA4proxy service.

### Monitoring Output
- **Prometheus/Grafana**: Accessible via SSH tunnel to port 3000. Provides real-time visibility into JA4 score distributions, geographic anomalies, and system health.
- **Loki/Promtail**: Centralized logging for forensic queries regarding specific TLS fingerprints or IP behaviors.

For incident response and specific troubleshooting scenarios, refer to the `docs/phases/RUNBOOK.md`.
