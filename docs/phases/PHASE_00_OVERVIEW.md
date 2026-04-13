# Phase 0: Project Overview & Architecture

## Purpose

Deploy JA4proxy (Go production binary) on an independent, internet-facing Ubuntu 22.04 VM for **research purposes only** — collecting real-world bot/crawler attack data at the TLS layer and validating the reliability of the Go JA4proxy implementation.

This machine is **unattached to anything of importance**. It exists purely as a research honeypot behind a JA4 fingerprinting proxy.

---

## Design Decisions

| Decision | Rationale |
|----------|-----------|
| **No build tools on the server** | Internet-facing machine must have minimal attack surface. All artifacts are pre-built and transferred as deployable units only. |
| **Go binary for JA4proxy** | ~15,000+ conn/s, no GIL contention, production-grade. Cross-compiled locally, SCP'd to VM. |
| **Docker Compose for supporting services** | Official pre-built images from Docker Hub. No compilers, no build chains. Just `docker compose up`. |
| **No container registry** | We use only official Docker Hub images (HAProxy, Redis, Caddy, Prometheus, Grafana, Loki). The Go binary is transferred via SCP. |
| **Static HTML + Caddy for honeypot** | Caddy auto-manages HTTPS behind the TLS passthrough proxy. Zero-config, minimal moving parts. |
| **Dial = 0 at start** | Monitor-only mode. Log everything, block nothing. Escalate only after validating data quality. |
| **No external threat intel feeds initially** | Start with JA4 fingerprinting, GeoIP, ASN, and TCP signals. Add Spamhaus/AbuseIPDB later when baseline is solid. |

---

## Architecture Diagram

```mermaid
flowchart TB
    subgraph Internet["🌐 Internet"]
        Browsers["🟢 Legitimate Browsers"]
        Bots["🔴 Bots / Scanners / C2"]
        Crawlers["🟡 Search Crawlers"]
    end

    subgraph Firewall["🛡️ UFW Firewall Rules"]
        Allow80["Allow 80/tcp (HTTP → Caddy ACME)"]
        Allow443["Allow 443/tcp (TLS → HAProxy)"]
        AllowSSH["Allow 22/tcp (Admin IP only)"]
        DenyAll["Deny All Other Inbound"]
    end

    subgraph VM["🖥️ Internet-Facing Research VM (Ubuntu 22.04 LTS)"]

        subgraph DockerStack["🐳 Docker Compose Stack"]
            HAProxy["🔷 HAProxy\nTLS Passthrough\nPROXY Protocol v2"]
            Redis["🔴 Redis\nBan Lists + Rate Limits\nConfig Pub/Sub"]
            Caddy["🟢 Caddy\nHTTPS Honeypot\nStatic Form + Warnings"]
            Prometheus["📊 Prometheus\nMetrics Scraper"]
            Grafana["📈 Grafana\nDashboards"]
            Loki["📋 Loki\nLog Aggregation"]
        end

        subgraph Binary["⚙️ Standalone Go Binary"]
            JA4Proxy["JA4proxy Go\nL4 Interceptor\nJA4 Fingerprinting\nRisk Scoring"]
        end

        subgraph Systemd["🔧 systemd"]
            JA4Service["ja4proxy.service\nRestart=always\nUser=ja4proxy"]
        end
    end

    Browsers --> Allow443
    Bots --> Allow443
    Crawlers --> Allow443
    Browsers --> Allow80
    Bots --> Allow80

    Allow443 --> HAProxy
    Allow80 --> Caddy

    HAProxy -->|"PROXY v2\n:8080"| JA4Proxy
    JA4Proxy -->|":8081\nforward"| Caddy

    JA4Proxy <-->|"ACL + Bans\n:6379"| Redis

    Prometheus -->|"Scrape\n:9090/metrics"| JA4Proxy
    Prometheus -->|"Scrape\n:9090/metrics"| HAProxy
    Grafana --> Prometheus
    Grafana -->|"Query logs"| Loki

    JA4Service -. manages .-> JA4Proxy

    style VM fill:#1a1a2e,color:#fff
    style JA4Proxy fill:#e94560,color:#fff
    style HAProxy fill:#0f3460,color:#fff
    style Redis fill:#c0392b,color:#fff
    style Caddy fill:#27ae60,color:#fff
    style Prometheus fill:#e67e22,color:#fff
    style Grafana fill:#f39c12,color:#fff
    style Loki fill:#8e44ad,color:#fff
```

---

## Network Flow

```mermaid
sequenceDiagram
    participant Client as 🌐 Client
    participant FW as 🛡️ UFW
    participant HA as 🔷 HAProxy:443
    participant JA4 as ⚙️ JA4proxy:8080
    participant Redis as 🔴 Redis:6379
    participant Caddy as 🟢 Caddy:8081

    Client->>FW: TCP SYN :443
    FW->>HA: Forward (allowed)
    HA->>JA4: TCP stream + PROXY v2 header
    JA4->>JA4: Peek TLS ClientHello
    JA4->>JA4: Extract JA4 fingerprint
    JA4->>JA4: Run signal checks
    JA4->>Redis: Check ban list
    Redis-->>JA4: Ban status

    alt Fingerprint banned
        JA4->>Client: TCP RST (immediate)
    else Score >= tarpit threshold
        JA4->>Client: Redirect to tarpit
    else Score OK (dial=0: monitor all)
        JA4->>Caddy: Forward raw TCP
        Caddy->>JA4: TLS handshake completes
        Caddy->>Client: Serve honeypot form (HTTPS)
        Client->>Caddy: Browse / submit form
        Caddy->>Caddy: Log metadata, discard payload
    end
```

---

## Component Inventory

| Component | Type | Source | Port (internal) | Port (host) | User |
|-----------|------|--------|-----------------|-------------|------|
| **JA4proxy Go** | Binary (cross-compiled) | Build locally, SCP | 8080 (proxy), 9090 (metrics) | 8080, 9090 | `ja4proxy` (dedicated) |
| **HAProxy** | Docker container | `haproxy:2.8-alpine` | 443, 8404 (stats) | 443, 8404 | root (container) |
| **Redis** | Docker container | `redis:7-alpine` | 6379 | none (internal network) | redis (container) |
| **Caddy** | Docker container | `caddy:2-alpine` | 8081 | none (internal network) | caddy (container) |
| **Prometheus** | Docker container | `prom/prometheus:latest` | 9090 | 9091 (host) | nobody (container) |
| **Grafana** | Docker container | `grafana/grafana:latest` | 3000 | 3000 (host) | grafana (container) |
| **Loki** | Docker container | `grafana/loki:latest` | 3100 | none (internal network) | loki (container) |
| **Promtail** | Docker container | `grafana/promtail:latest` | - | none | root (container) |

---

## Data Flow Summary

```mermaid
flowchart LR
    subgraph Collection["📥 Data Collected"]
        JA4_FP["JA4/JA4X/JA4T\nFingerprints"]
        TLS_META["TLS Metadata\n(version, ciphers, SNI, ALPN)"]
        IP_INFO["IP + GeoIP Country\n+ ASN Classification"]
        RISK["Risk Scores (0-100)\n+ Decision Actions"]
        BEHAVIOR["Behavioral Signals\n(beaconing, probing, bursts)"]
        CONN["Connection Metrics\n(errors, weak ciphers, SSL attempts)"]
    end

    subgraph Storage["💾 Storage"]
        TSDB["Prometheus TSDB\n(time-series metrics)"]
        Logs["Loki\n(log aggregation)"]
        RedisDB["Redis\n(transient bans/rates)"]
    end

    subgraph Analysis["🔬 Research Output"]
        Dashboards["Grafana Dashboards\n(real-time bot visibility)"]
        Reports["Periodic Reports\n(JA4 distribution, attack trends)"]
        Validation["Proxy Reliability Data\n(latency, accuracy, uptime)"]
    end

    Collection --> TSDB
    Collection --> Logs
    Collection --> RedisDB
    TSDB --> Dashboards
    Logs --> Dashboards
    TSDB --> Reports
    Logs --> Reports
    TSDB --> Validation
```

---

## What We Gather (Detailed)

### Per-Connection Data
- **JA4 fingerprint** — `t13d1517h2_...` style identifier derived from TLS ClientHello
- **JA4X fingerprint** — Extended fingerprint (X.509 certificate metadata if available)
- **JA4T fingerprint** — TCP-level fingerprint
- **Source IP** — client IP (extracted via PROXY protocol v2)
- **GeoIP country code** — via IP2Location LITE database
- **ASN classification** — datacenter, hosting provider, Tor exit node
- **TLS version** — attempted TLS version (SSLv3, TLS 1.0/1.1/1.2/1.3)
- **Cipher suites** — list of offered ciphers
- **Extensions** — TLS extensions present in ClientHello
- **ALPN** — Application-Layer Protocol Negotiation values (h2, h1, etc.)
- **SNI** — Server Name Indication hostname

### Decision & Scoring Data
- **Risk score** (0–100) — composite score from all signal modules
- **Action taken** — `allow`, `flag`, `rate_limit`, `tarpit`, `block`, `ban`
- **Block reason** — which rule triggered the decision
- **Dial setting** — current dial value at time of decision
- **Bypass matched** — which bypass rule applied (if any)

### Behavioral Signals
- **Beaconing detection** — periodic callback patterns (CV-based)
- **Probing detection** — scanning/enumeration behavior
- **Burst detection** — rapid connection bursts from same source
- **Connection lifespan** — how long connections stay open
- **Return visitor tracking** — repeat connections from same JA4+IP
- **TCP session analysis** — resumption patterns, TLS alerts

### Operational Metrics
- **Connection rates** — connections/second by IP, JA4, and IP+JA4 pair
- **Tarpit stats** — concurrent tarpitted connections, overflow events
- **Ban lifecycle** — ban creation, expiration (5-min TTL)
- **Config reloads** — hot-reload events via SIGHUP
- **Pipeline duration** — end-to-end processing latency (p50, p99)
- **Connection errors** — by type (timeout, reset, parse failure)

---

## Security Posture

```mermaid
flowchart TD
    subgraph Principles["🔒 Security Principles"]
        P1["No TLS termination\nin JA4proxy"]
        P2["No PII collection"]
        P3["Fails open if\nfeeds unreachable"]
        P4["Auto-expiring bans\n(5 min TTL)"]
        P5["Monitor-first\n(dial=0 default)"]
        P6["Dedicated user\n(no root for proxy)"]
        P7["Internal networks\nonly for Docker"]
        P8["ReadOnly filesystem\ncontainers where possible"]
    end

    subgraph ThreatModel["⚠️ Threat Model"]
        T1["Internet scanning\n& exploitation attempts"]
        T2["Bot traffic floods"]
        T3["TLS vulnerability\nprobing"]
        T4["Resource exhaustion\n(connection floods)"]
    end

    subgraph Mitigations["🛡️ Mitigations"]
        M1["UFW default deny\n+ admin IP allowlist SSH"]
        M2["Tarpit for resource\nwaste on attackers"]
        M3["No sensitive data\non server to steal"]
        M4["Rate limiting\nper IP/JA4/IP+JA4"]
        M5["Container resource\nlimits enforced"]
        M6["Automated unattended\nupgrades enabled"]
    end

    Principles -. informs .-> Mitigations
    ThreatModel -. addressed by .-> Mitigations

    style Principles fill:#27ae60,color:#fff
    style ThreatModel fill:#e74c3c,color:#fff
    style Mitigations fill:#2980b9,color:#fff
```

---

## Phase Document Index

| Phase | Document | Status |
|-------|----------|--------|
| **Phase 0** | This document — overview, architecture, diagrams | ✅ This file |
| **Phase 1** | `PHASE_01_VM_PROVISIONING.md` — VM setup, hardening, firewall | ⏳ Next |
| **Phase 2** | `PHASE_02_ARTIFACT_PREPARATION.md` — build, config prep, transfer | ⏳ |
| **Phase 3** | `PHASE_03_JA4PROXY_DEPLOYMENT.md` — Go binary, systemd, monitor mode | ⏳ |
| **Phase 4** | `PHASE_04_SUPPORTING_SERVICES.md` — Docker Compose stack | ⏳ |
| **Phase 5** | `PHASE_05_DATA_COLLECTION.md` — research plan, dashboards, retention | ⏳ |
| **Phase 6** | `PHASE_06_OPERATIONAL_SECURITY.md` — access, alerting, incident response | ⏳ |
| **Phase 7** | `PHASE_07_VALIDATION_TESTING.md` — verification, traffic generation, dial escalation | ⏳ |
| **Phase 8** | `PHASE_08_SECURITY_HARDENING.md` — STRIDE threat model, kernel hardening, container security, forensics | ⏳ |

---

## Glossary

| Term | Definition |
|------|------------|
| **JA4** | JA4 fingerprinting — TLS ClientHello fingerprinting method by FoxIO |
| **JA4X** | Extended JA4 including X.509 certificate metadata |
| **JA4T** | TCP-level JA4 fingerprint |
| **Dial** | JA4proxy master control (0=monitor, 100=full block) |
| **Tarpit** | Slow TCP server that wastes attacker resources |
| **PROXY Protocol v2** | Header carrying original client IP through proxies |
| **Caddy** | Web server with automatic HTTPS (Let's Encrypt) |
| **Counterfactual** | "What would have happened if dial was higher?" — logged for analysis |
