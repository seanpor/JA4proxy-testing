# 5. Static HTML plus Caddy for the honeypot

## Status

Accepted

## Context

The honeypot's only job, from a visitor's point of view, is to look
like a plausible HTTPS site and capture the TLS handshake plus any
subsequent HTTP request. It must not do anything a real web
application does — no database, no server-side rendering, no
authentication — because every added component widens the attack
surface of the research box and invites accidental exposure of real
data. We also need HTTPS with a publicly trusted certificate during
the `live` stage so client TLS stacks behave naturally; self-signed
certs distort the fingerprint population.

## Decision

The honeypot is a single static HTML warning page served by Caddy.
Caddy auto-manages HTTPS via ACME (Let's Encrypt staging in `locked`
and `verified` stages, production in `live`; see `ja4proxy_acme_staging`
and role 10). Caddy listens only on `ja4proxy_caddy_internal_port`
(default 8081), receiving PROXY-protocol traffic from JA4proxy; it
does not bind 80/443 itself.

This is encoded in `deploy/roles/04-supporting-services` (compose
service) and `deploy/templates/Caddyfile.j2`. The honeypot content
lives under `deploy/templates/honeypot/`.

## Consequences

- **Positive:** Zero server-side logic means zero RCE surface at the
  application layer. The honeypot cannot be tricked into executing
  attacker input because it does not execute anything.
- **Positive:** Caddy's automatic ACME removes a whole class of
  cert-rotation failure modes; Phase 10 only needs to flip the ACME
  directory, not rewrite certificate provisioning.
- **Positive:** Real-browser TLS stacks treat the site as legitimate
  (valid cert, HTTP/2, HSTS), so the fingerprints collected reflect
  real-world behaviour rather than reactions to a broken site.
- **Negative:** No application-layer telemetry beyond access logs —
  if we later want to study HTTP-layer bot behaviour (form fills,
  JS execution), this ADR will need to be superseded.
