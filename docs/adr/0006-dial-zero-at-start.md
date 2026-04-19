# 6. Dial = 0 at initial deployment

## Status

Accepted

## Context

JA4proxy's enforcement level is a single integer 0–100 exposed as
`dial:` in `/opt/ja4proxy/config/proxy.yml` and reloadable via
`SIGHUP`. 0 is monitor-only (log everything, block nothing); higher
values tighten thresholds and can eventually block outright. A new
fingerprint-based defence deployed at a non-zero dial on day one
carries a known failure mode: the block list is built from unfamiliar
traffic, so legitimate clients whose fingerprints happen to resemble
adversaries get blocked before we even see the data that would
exonerate them. We also need a clean baseline of fingerprint
frequencies before we can say what "anomalous" means.

## Decision

Every fresh deployment starts with `ja4proxy_dial: 0`
(`deploy/inventory/group_vars/all.yml`). Raising the dial is an
operator decision, documented per-step in `README.md` and
`docs/phases/PHASE_07_VALIDATION_TESTING.md`, and is applied by
editing the variable and re-running role 03 (or live-editing
`proxy.yml` and sending `SIGHUP`). Code changes to the repo **must
not** raise the default without an explicit request.

## Consequences

- **Positive:** First contact with the internet is strictly
  observational. We get the traffic picture before we alter it, which
  is the only way to validate the fingerprinting data itself.
- **Positive:** Safe rollback is trivial — set dial to 0, reload, done.
  No state migration, no cache to invalidate.
- **Positive:** The default makes the honeypot safe to accidentally
  deploy. Even a misconfigured run can't block real traffic.
- **Negative:** "Deployed" is not "enforcing"; an operator who forgets
  to escalate the dial gets telemetry but no protection. Operational
  documentation has to carry that message prominently.
- **Note:** This ADR is a standing constraint on every PR that
  touches `ja4proxy_dial` defaulting — reviewers should push back on
  any change that raises it silently.
