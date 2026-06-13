# Phase 11: Legal, Ethics, and Honeypot Disclosure

> **Status: partially implemented.** Disclosure pages and templates exist. Remaining work: wiring the automated go-live verification and MX preflight assertions.

## Why this phase exists

An internet-facing honeypot is not a neutral observer. Legally it is a system that:

- receives personal data (IP addresses are personal data under GDPR);
- operates in an EU region (Alibaba Cloud eu-central-1), so GDPR, ePrivacy, and the AI-Act-adjacent research-exemption framework apply;
- presents itself as an ordinary HTTPS service, which raises honeypot-disclosure questions distinct from a passive packet-capture sensor;
- will be reported to ISP abuse desks, threat-intel lists, and potentially to law enforcement.

None of that is addressed by a "naked" deployment. This phase defines the minimum governance layer required before public exposure.

## Deliverables

### 1. Honeypot disclosure page

Served by Caddy at `/honeypot-notice.html` (linked from the honeypot form's footer) and at `/.well-known/honeypot-notice` (machine-readable JSON mirror). Must state, in plain language:

- This service is a research honeypot operated for TLS fingerprinting research.
- No real personal data is processed or persisted beyond connection-level metadata.
- Submitting data to this form is pointless: the form is fake and submissions are discarded.
- Contact for data-subject rights: `privacy@<ja4proxy_domain>`.
- Contact for abuse reports: `abuse@<ja4proxy_domain>`.

### 2. Privacy / data-controller statement

A separate `/privacy.html` with:

- **Controller:** Sean O'Riordain (`sean.oriordain@gmail.com`).
- **Lawful basis:** Article 6(1)(f) GDPR — legitimate interests (security research).
- **Purposes:** TLS fingerprint analysis, bot/attacker classification.
- **Retention:** 90 days for metrics/logs, 5 minutes for Redis bans.
- **International transfers:** Data stays in `eu-central-1` for capture; HMAC-anonymized exports travel to the control machine for analysis.

### 3. Abuse contact wiring

- `abuse@<domain>` MX record must exist *before* go-live.
- `security.txt` at `/.well-known/security.txt` with `Contact:` and dynamic `Expires:` field (rendered as `now + 1 year`).

### 4. Governance documentation

Ensure `docs/governance/` files are populated and reviewed annually:
- `LAWFUL_BASIS.md`, `DPIA.md`, `ROPA.md`, `RETENTION.md`, `LE_REQUESTS.md`.

## Acceptance criteria (Go-Live Blockers)

A machine-checkable list wired into `deploy/roles/10-go-live/`:

```
[ ] curl -sI https://<domain>/honeypot-notice.html returns 200
[ ] curl -sI https://<domain>/privacy.html returns 200
[ ] curl -sI https://<domain>/.well-known/security.txt returns 200 with Contact: and valid Expires:
[ ] dig MX <domain> returns a record (preflight check)
```

## Improvement: Automated Disclosure Verification
Added a `verify-disclosure` tag to the `10-go-live` role that performs a regex check on the served `security.txt` to ensure the `Expires` date is in the future and the `Contact` email is correct.
