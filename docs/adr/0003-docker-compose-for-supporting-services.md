# 3. Docker Compose for supporting services

## Status

Accepted

## Context

Around JA4proxy we need HAProxy (TLS passthrough), Redis (bans and
rate-limit state), Caddy (honeypot HTTPS terminator), and the full
observability stack (Prometheus, Grafana, Loki, Promtail, Alertmanager,
Blackbox exporter). Installing each from distro packages would mean
version drift between Ubuntu releases, hand-written unit files, and a
bespoke upgrade path per service. Kubernetes is overkill for a
single-VM research honeypot — it would dwarf the workload it hosts.

## Decision

All non-JA4proxy services run via `docker compose` on the target VM,
from a single `/opt/ja4proxy-docker/docker-compose.yml` rendered by
`deploy/templates/docker-compose.yml.j2`. Role
`04-supporting-services` writes the compose file and starts the
stack; role `09-image-digests` pins each image to a
`repo:tag@sha256:…` reference so the compose is reproducible.

JA4proxy itself remains a host-level systemd service (ADR 0002);
a `ja4proxy-redis` systemd unit wraps the Redis container so
systemd can order `ja4proxy.service` after Redis is healthy.

## Consequences

- **Positive:** Every supporting service is a stock upstream image,
  pulled from Docker Hub (ADR 0004), so we inherit upstream patching
  by bumping a pin rather than maintaining our own build.
- **Positive:** One `docker compose down / up` rolls the whole
  dependent stack; health and logs are uniform across services.
- **Positive:** Resource limits (`*_memory_limit`, `*_cpu_limit` in
  `group_vars/all.yml`) are set once in the template rather than
  per-service unit files.
- **Negative:** Two supervision systems on one box — systemd owns
  JA4proxy, compose owns the rest. The shim `ja4proxy-redis.service`
  exists solely to bridge them.
- **Negative:** Digest pinning (Phase 9, plus Phase 18-G automation)
  is now load-bearing; a floating `:latest` tag would silently change
  behaviour on `docker compose pull`.
