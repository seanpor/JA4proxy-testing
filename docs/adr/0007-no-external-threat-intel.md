# 7. No external threat-intel feeds initially

## Status

Accepted

## Context

It is tempting to bolt third-party threat-intel feeds (Spamhaus,
AbuseIPDB, Emerging Threats, commercial reputation APIs) onto a new
detector on day one — "free" blocking power, plus a credible story
for "how do you know it's malicious." In practice every feed adds an
external dependency, a latency tail, a licensing or TOS footprint, and
a second source of truth that is hard to back out of once the signal
is entangled with our own. For a research box whose *purpose* is to
measure what the first-party signals (JA4 fingerprints, GeoIP, ASN,
raw TCP behaviour) can actually see on their own, pre-seeding with
external verdicts destroys the experiment.

## Decision

The honeypot runs only on first-party and locally-hosted signals for
its initial phase: JA4 / JA4S / JA4H fingerprints from the Go proxy,
GeoIP and ASN lookups from a local IP2Location database
(`ja4proxy_geoip_dir`), and raw TCP-layer signals from HAProxy. No
external reputation feed is consulted at connection time, and none is
included in the enforcement path.

This is encoded by omission — there is no role, template, or
docker-compose service that calls an external intel API. Phase 5
(`05-data-collection`) is the authoritative list of signals, and it
is deliberately short.

## Consequences

- **Positive:** The dataset we collect is clean: every block, label,
  or anomaly score is traceable back to a signal we can inspect and
  reproduce offline. That is the whole point of the research phase.
- **Positive:** Zero external dependencies in the request path means
  zero external-outage failure modes, zero TOS surprises, and zero
  exfiltration risk from feed lookups revealing our IPs of interest.
- **Negative:** Detection coverage is narrower than a feed-enriched
  system would have on day one. We are explicitly trading short-term
  coverage for long-term signal clarity.
- **Follow-on:** Once the baseline is solid and we know what the
  first-party signals can and cannot see, integrating feeds is on the
  table. That decision should arrive as its own ADR that supersedes or
  amends this one, not as a silent addition of a reputation lookup.
