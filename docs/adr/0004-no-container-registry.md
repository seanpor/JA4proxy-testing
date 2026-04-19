# 4. No private container registry

## Status

Accepted

## Context

A containerised stack usually implies a private registry — somewhere
to publish hand-built images, sign them, and pull them at deploy time.
Running our own registry would mean another internet-facing surface
(or a VPN path back to it), credential management for pulls, image
retention policy, and a separate CVE-scanning pipeline. For a
single-VM research honeypot that only runs stock upstream images,
this is infrastructure for its own sake.

## Decision

No private registry is operated or depended on. Every container image
in the stack is an official upstream image pulled directly from Docker
Hub: HAProxy, Redis, Caddy, Prometheus, Grafana, Loki, Promtail,
Alertmanager, Blackbox exporter. The JA4proxy binary — the one piece
of first-party code — is transferred via SCP as a plain file (ADRs
0001 and 0002), not packaged as an image.

Image identities are pinned by `repo:tag@sha256:…` in the compose
template rendered by role 09, and the pin set is tracked in
`deploy/expected-image-digests.yml` (Phase 18-G) so weekly automation
can propose bumps without trusting mutable tags.

## Consequences

- **Positive:** Nothing to operate, credentialise, or patch on the
  registry side. No registry means no registry outage.
- **Positive:** Supply-chain scrutiny focuses on two narrow vectors:
  (a) Docker Hub delivering the bytes the pin says, and (b) our own
  Go binary build. Phase 18-D addresses (b) with cosign; Phase 18-B
  addresses (a) with Trivy against pinned digests.
- **Negative:** Anything first-party and containerised would need a
  registry — we have none. If a future service must be containerised
  rather than shipped as a binary, this ADR is the one to revisit.
- **Negative:** Docker Hub anonymous pull rate limits are a real
  failure mode on fresh VMs; Phase 9 mitigates by pinning (no
  repeated manifest fetches across runs).
