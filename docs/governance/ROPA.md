# Record of Processing Activities

Last reviewed: 2026-04-15

One-page ROPA under GDPR Article 30. Tabular so it fits on a single
screen; operator updates when any column changes.

## Controller

| Field | Value |
|-------|-------|
| Name | _<operator name / legal entity>_ |
| Contact | _<email for data-subject rights requests — must match `/privacy.html`>_ |
| DPO | _<name, or "not required, single-operator research project">_ |
| Representative (if non-EU) | _<name or N/A>_ |

## Processing activity — honeypot fingerprint collection

| Field | Value |
|-------|-------|
| Purpose | TLS fingerprint research on bot / scanner populations |
| Lawful basis | Article 6(1)(f) — legitimate interests (see `LAWFUL_BASIS.md`) |
| Data categories | Source IP; TLS ClientHello fields (JA4); HTTP request metadata; coarse geolocation; timestamps |
| Special categories | None |
| Data subjects | Operators of scanners / bots / researchers that connect to the honeypot unsolicited |
| Recipients | Operator only (no third-party sharing without LE request — see `LE_REQUESTS.md`) |
| International transfers | None (EU-only VM region) |
| Retention | See `RETENTION.md` |
| Technical & organisational measures | See `THREAT_MODEL.md` §2.4 and `docs/phases/PHASE_08_SECURITY_HARDENING.md` |

## Processing activity — operational logs

| Field | Value |
|-------|-------|
| Purpose | Operational visibility (uptime, error rates) and security audit |
| Lawful basis | Article 6(1)(f) |
| Data categories | System logs, container logs, HAProxy access logs |
| Retention | See `RETENTION.md` |
| Recipients | Operator only |

## Changes since last review

_<Dated list. Any new data category or recipient triggers a DPIA
re-review in addition to the ROPA update.>_
