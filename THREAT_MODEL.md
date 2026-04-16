# JA4proxy Research Honeypot — Threat Model

Last reviewed: 2026-04-15
Owner: repo maintainer (single operator posture, see README → Operations → On-call posture)

This document is the repo-level threat model for the JA4proxy research
honeypot. It sits above the implementation-specific STRIDE table in
[`docs/phases/PHASE_08_SECURITY_HARDENING.md`](docs/phases/PHASE_08_SECURITY_HARDENING.md)
and the Phase-by-Phase hardening work, naming the attacker goals and
showing where in the codebase each one is (or isn't) mitigated. The
Phase 08 STRIDE matrix remains the ground-truth mitigation list;
this file exists so a reviewer can judge the *system* rather than
picking through individual phases.

Review cadence: every 365 days or on any change to exposure surface
(new public port, new upstream dependency, new data export channel).
CI enforces the `Last reviewed:` date is ≤ 365 days old.

## 1. System under analysis

Deployment posture is a single cloud VM (Alibaba ECS, EU region) in
a staged locked → verified → live flow. Traffic path:

```
Internet → HAProxy :443 (TLS passthrough, PROXY v2)
         → JA4proxy :8080 (L4 interceptor, Go systemd service)
         → Caddy :8081 (HTTPS honeypot, static warning page)
           ↕
         Redis :6379 (bans, rate-limit counters — loopback only)

Observability (loopback-only outside live stage):
  Prometheus :9090 ←──── scrapes ───→ ja4proxy, haproxy, blackbox_exporter
  Promtail   (agent) ──→ Loki :3100
  Grafana    :3000   ←── reads ────→ Prometheus + Loki
```

Design constraints that shape this model:

- **The honeypot must look real to attackers.** Visible identifiers
  for the research project stay out of the TLS handshake and HTTP
  response headers.
- **Dial defaults to 0 (monitor-only).** The research value is the
  fingerprint dataset, not the blocks. Raising the dial is a
  deliberate post-verification step.
- **Single-operator on-call.** 3 business days for abuse email, 24 h
  for heartbeat/budget alerts (README → Operations). This shapes the
  residual-risk acceptance below.
- **Research artefact, not a production service.** No customer data,
  no SLA, no multi-tenant isolation. The blast radius of a full
  compromise is "one VM, one domain, one research dataset" —
  important but bounded.

## 2. Attack trees

Four attacker goals that actually matter for this deployment. Each
tree names the realistic paths; leaves link to the phase doc where
the mitigation lives.

### 2.1 VM compromise

Goal: attacker gains root on the VM and can read/modify anything.

```
VM compromise
├── Exploit exposed service
│   ├── JA4proxy RCE on :8080 (live stage, fronted by HAProxy)
│   │     → mitigations: systemd sandboxing + AppArmor profile
│   │       (PHASE_03, PHASE_08 §8.3.1), -trimpath build (14-A).
│   ├── Caddy / HAProxy CVE
│   │     → mitigations: digest-pinned images (role 09), AIDE
│   │       monitors installed binaries (13-I), blackbox probe
│   │       fails loudly (13-F).
│   └── SSH brute force or key theft
│         → mitigations: UFW permits 22/tcp from
│           ja4proxy_admin_ip only, Ed25519 keys, no password auth
│           (PHASE_01, PHASE_08 §8.5).
├── Supply-chain injection
│   ├── Malicious Docker image (tag mutation)
│   │     → mitigation: role 09 pins sha256 digests, fails deploy
│   │       on mismatch.
│   ├── Malicious JA4proxy binary (build-time swap)
│   │     → mitigation: expected-binary-sha256.txt pin (14-B),
│   │       binary-provenance.yml records commit + goflags (12-D).
│   └── Malicious Ansible collection
│         → mitigation: collections pinned in requirements
│           (14-D), check_collections.py enforces.
└── Operator mistake
    ├── `make go-live` against wrong host
    │     → mitigation: DNS + MX preflight, explicit
    │       ja4proxy_go_live_confirm=true (11-D, 13-G).
    └── Secrets committed to git
          → mitigation: check_secrets.py (repo secret scan),
            deploy/.vault/ gitignored.
```

Residual risk: medium. A zero-day in Caddy or HAProxy fronting
TLS is the most realistic path; AIDE + blackbox alerting gives us
detection, not prevention.

### 2.2 Honeypot as DDoS reflector

Goal: attacker uses the honeypot to amplify or reflect traffic at a
third party, so the abuse report lands on *us* and the real target
sees traffic from our IP.

```
DDoS reflector abuse
├── Outbound connection from JA4proxy / Caddy
│     → mitigations: Caddy serves static HTML only; JA4proxy does
│       not make outbound requests; egress UFW is default-deny
│       with narrow exceptions (PHASE_08 §8.4).
├── DNS amplification via a local resolver
│     → mitigation: no resolver is exposed to the public net; only
│       systemd-resolved listens on 127.0.0.53.
├── ACME-triggered egress used as a covert channel
│     → mitigation: ACME staging by default (13-H), production
│       flip is a deliberate go-live step; Caddy logs ACME activity.
└── Abuse from inside a compromised container
      → mitigations: read-only FS, no-new-privs, non-root users
        where supported (PHASE_08 §8.3.1); docker.sock is
        read-only and mounted only into Promtail.
```

Residual risk: low — the stack is structurally non-amplifying.
The main variable is egress UFW staying default-deny; a future
chunk should add a CI check that egress rules don't drift.

### 2.3 DNS / domain hijack

Goal: attacker redirects `<ja4proxy_domain>` elsewhere — either to
collect abuse reports intended for us, or to MITM the honeypot.

```
DNS / domain hijack
├── Registrar account takeover
│     → mitigation: out of scope for this repo (depends on the
│       operator's registrar 2FA). Called out in RUNBOOK budget
│       alert setup + PTR record request (13-K) so the operator is
│       reminded to pin the registrar down before go-live.
├── Authoritative-DNS record tampering
│     → mitigation: MX + A preflight before go-live (11-D, 13-G)
│       — we assert the A record resolves to us and the MX is not
│       the wildcard catchall before opening UFW.
├── BGP hijack of Alibaba's prefix
│     → accepted risk: nothing in a research-scale deployment
│       mitigates this. Detection: heartbeat fails from our side
│       (13-F).
└── PTR record absent
      → mitigation: RUNBOOK "PTR record request" section requires
        it pre-go-live so abuse reports route to us, not Alibaba
        (13-K).
```

Residual risk: medium. Registrar hijack is the realistic leaf and
is out-of-repo; we rely on operator discipline and the heartbeat to
detect the aftermath quickly.

### 2.4 Data exfiltration via metrics / logs

Goal: attacker reads the research dataset (IP fingerprints,
geolocation, timing) or pivots it to deanonymise traffic.

```
Data exfiltration
├── Public Grafana / Prometheus endpoint
│     → mitigations: ports bound to 127.0.0.1 outside the live
│       stage (compose template gate); UFW restricts 3000/9090/3100
│       to ja4proxy_admin_ip (PHASE_08 §8.4).
├── Loki query over the public net
│     → mitigation: same loopback + UFW pattern as Grafana.
├── Docker socket abuse via Promtail
│     → mitigation: docker.sock mounted ro; Promtail does not
│       accept inbound queries.
├── Export channel abuse
│     → mitigations: weekly export (12-A) is local-only;
│       anonymisation (12-B) HMACs IPs before any share;
│       no push to a third-party store is wired (out of scope).
└── Form submissions retained
      → mitigation: honeypot landing page discards submissions
        before persistence; /privacy.html makes this explicit
        (11-B). Nothing in the stack writes form content to disk.
```

Residual risk: low. The dataset leaves the VM only via
operator-initiated `make export-pull` (12-C) or `scp`; HMAC
anonymisation (12-B) scrubs IPs before any share. Evidence
collection (15-A) bundles raw logs into mode-0600 tarballs in a
mode-0700 directory and is incident-triggered, not continuous.

## 3. Residual risk register

| # | Risk | Likelihood | Impact | Owner | Accepted until |
|---|------|------------|--------|-------|---------------|
| R1 | Zero-day in Caddy / HAProxy → VM compromise | Low | High | operator | detection via AIDE (13-I) + heartbeat (13-F); no prevention beyond digest pinning |
| R2 | Registrar account takeover | Low | High | operator (out of repo) | registrar 2FA + pre-go-live DNS preflight |
| R3 | BGP hijack of Alibaba prefix | Very low | High | cloud provider | accepted; heartbeat detects aftermath |
| R4 | Operator absence during incident | Medium | Medium | operator | README on-call posture: 3 bus. days / 24 h; stop-before-away |
| R5 | CertExpiringSoon fires with no delivery | Low | Medium | operator | 13-D Alertmanager now delivers; SMTP config is operator opt-in |
| R6 | Heartbeat URL exfil via env var in process listing | Low | Low | operator | accepted; URL is a low-secrecy identifier, rotatable at healthchecks.io |
| R7 | Dataset deanonymisation via IP + timing | Low | Medium | operator | 12-B HMAC anonymisation landed; IPs scrubbed before any share |
| R8 | Egress UFW rules drift to allow arbitrary outbound | Medium | High | operator | no CI check today; candidate for a future chunk |

## 4. What this model does **not** cover

- **Formal methods / proof of correctness.** Research project, not
  aerospace. Roadmap explicitly excludes this (TM-A "Not in scope").
- **Multi-tenant isolation.** There is only one tenant — the operator.
- **Insider threat beyond operator mistake.** Single-operator repo.
- **Long-term dataset publication governance.** 11-E (DPIA / ROPA)
  skeletons are in place; operator fills in the legal content.

## 5. Cross-references

- [`docs/phases/PHASE_08_SECURITY_HARDENING.md`](docs/phases/PHASE_08_SECURITY_HARDENING.md) — STRIDE matrix, kernel + container hardening, per-mitigation detail.
- [`docs/phases/GOVERNANCE_ROADMAP.md`](docs/phases/GOVERNANCE_ROADMAP.md) — per-chunk history of governance changes referenced here (14-A/B, 11-B/D, 12-D, 13-F/G/H/I/K, 15-A, TM-A).
- [`docs/phases/RUNBOOK.md`](docs/phases/RUNBOOK.md) — incident-response steps, budget alert setup, PTR record request.
- [`README.md`](README.md) — operational posture and on-call commitments.
