# 2. Go binary for JA4proxy

## Status

Accepted

## Context

JA4proxy is the enforcement point for every inbound TLS connection
after HAProxy terminates the PROXY-protocol handoff. It needs to
fingerprint ClientHello bytes, consult Redis for bans and rate-limit
counters, and forward to Caddy — all in the data path, per connection.
A scripting-language implementation would either serialise on a GIL
(Python) or require a much larger runtime footprint (JVM). An
always-on research box also benefits from a single static binary with
no interpreter or library drift between deployments.

## Decision

JA4proxy runs as a statically linked Go binary, built on a separate
machine and delivered to the target VM via SCP. It is managed as a
plain `systemd` unit, not a container — the host's systemd is the
natural supervisor and gives direct journald logging.

This is encoded in `deploy/roles/02-artifact-build` (the build step)
and `deploy/roles/03-ja4proxy-deploy` (which drops the binary into
`/opt/ja4proxy/bin/ja4proxy` and installs the unit file from
`deploy/templates/ja4proxy.service.j2`). Build flags
(`-trimpath -buildvcs=true`) live in `ja4proxy_go_build_flags`.

## Consequences

- **Positive:** Production-grade throughput (target ≥15 k conn/s) with
  no GIL contention or interpreter start-up cost per connection.
- **Positive:** Single static artifact pairs cleanly with ADR 0001
  (no build tools on the server) and with Phase 18-D cosign signing —
  there is exactly one blob to sign and verify.
- **Positive:** Failure modes are systemd-native: `journalctl -u
  ja4proxy`, `systemctl restart`, resource limits via the unit file.
- **Negative:** Split from the rest of the stack — JA4proxy is the
  only service *not* in Docker Compose, so role 03 and role 04 have to
  coordinate (see ADR 0003).
- **Negative:** Cross-compilation needs a matching Go toolchain on the
  build machine; version skew there is a real operational concern.
