# QWEN.md — JA4proxy-testing

## Project Overview

**JA4proxy-testing** is a deployment and testing repository for **JA4proxy**, a Layer 4 TCP interceptor proxy that generates JA4 fingerprints from TLS Client Hello packets. The purpose of this project is to deploy JA4proxy in front of a honeypot HTTPS form on an internet-facing machine to collect real-world bot attack data and validate JA4 fingerprinting effectiveness in production-like conditions.

The system is designed as a **test environment only** — it must never collect real PII, must be clearly marked with warnings, and must remain isolated from production infrastructure.

## Architecture

```
Internet (Encrypted) -> [JA4proxy: L4 Interceptor] -> [HAProxy: TLS Termination] -> [Honeypot Backend]
                              |
                         [Redis: State Store]
                              |
                    [Observability Stack]
```

### Components

| Component | Role |
|-----------|------|
| **JA4proxy** | Listens on ports 80/443, intercepts raw TCP stream before TLS handshake, parses Client Hello to generate JA4 fingerprint, compares against blocklists, proxies allowed traffic to HAProxy |
| **HAProxy** | Receives proxied stream, performs TLS termination, enforces L7 rate limiting, routes to honeypot backend |
| **Honeypot Backend** | Simple HTTP server serving a fake form with massive warnings; logs submission metadata but discards form payloads |
| **Redis** | Stores dynamic ban lists and rate-limiting counters |
| **Observability Stack** | Prometheus + Grafana + Loki for metrics, visualization, and log aggregation |

## Key Files

| File | Description |
|------|-------------|
| `README.md` | High-level project description |
| `docs/DETAILED_DEPLOYMENT_PLAN.md` | Comprehensive phase-by-phase deployment plan (retrievable from git history; docs/ is git-ignored) |
| `.gitignore` | Ignores the `docs/` directory |
| `LICENSE` | Project license |

## Deployment Phases

The project follows a structured deployment plan:

1. **Phase 1: Infrastructure Setup** — Server provisioning, network architecture, domain configuration, OS hardening
2. **Phase 2: Honeypot Form Development** — Building the bait form with prominent warnings
3. **Phase 3: JA4proxy Deployment** — Configuring and running the L4 interceptor
4. **Phase 4: HAProxy & Backend Integration** — TLS termination and traffic routing
5. **Phase 5: Observability & Monitoring** — Prometheus, Grafana, Loki stack
6. **Phase 6: Testing & Validation** — Real-world bot attack data collection

## Technologies

- **OS:** Ubuntu 22.04 LTS or Debian 12
- **Containerization:** Docker / Docker Compose
- **Proxy:** JA4proxy (custom L4 interceptor), HAProxy (L7 TLS termination)
- **State Store:** Redis
- **Observability:** Prometheus, Grafana, Loki
- **Honeypot Backend:** Python/Flask or Node/Express

## Security Constraints

- System MUST be clearly marked as a test environment with impossible-to-miss warnings
- NO real PII collection or persistence
- Isolated from production infrastructure
- Monitor-first approach (no blocking initially)
- Full legal compliance with clear disclaimers

## Git Structure

- **Branch:** `main` (default)
- **Remote:** `origin` (GitHub: seanpor/JA4proxy-testing)
- The `docs/` directory is git-ignored but deployment plans exist in git history
