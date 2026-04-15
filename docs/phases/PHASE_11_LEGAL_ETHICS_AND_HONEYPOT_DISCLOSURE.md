# Phase 11: Legal, Ethics, and Honeypot Disclosure

> **Status: work not yet implemented.** This phase document defines required outputs. Until they are in place, `make go-live` should be considered blocked for any deployment whose target audience extends beyond the operator's own research.

## Why this phase exists

An internet-facing honeypot is not a neutral observer. Legally it is a system that:

- receives personal data (IP addresses are personal data under GDPR);
- operates in an EU region (Alibaba Cloud eu-central-1), so GDPR, ePrivacy, and the AI-Act-adjacent research-exemption framework apply;
- presents itself as an ordinary HTTPS service, which raises honeypot-disclosure questions distinct from a passive packet-capture sensor;
- will be reported to ISP abuse desks, threat-intel lists, and potentially to law enforcement (both *about* this box by others, and *from* this box to them when we see active crime).

None of that is addressed by the current codebase. This phase defines the minimum governance layer required before public exposure.

## Deliverables

### 1. Honeypot disclosure page

Served by Caddy at `/honeypot-notice.html` (linked from the honeypot form's footer) and at `/.well-known/honeypot-notice` (machine-readable JSON mirror). Must state, in plain language and in English at minimum:

- This service is a research honeypot operated for TLS fingerprinting research.
- No real personal data is processed or persisted beyond the connection-level metadata needed for the research (see next item).
- Submitting data to this form is pointless: the form is fake and submissions are discarded.
- Contact for data-subject rights: `privacy@<ja4proxy_domain>`.
- Contact for abuse reports: `abuse@<ja4proxy_domain>`.

Ansible: add `files/honeypot-notice.html` and a task in role `04-supporting-services` that deploys it alongside the honeypot index page. Add a verification task that `curl -s https://<domain>/honeypot-notice.html | grep -q abuse@` during go-live.

### 2. Privacy / data-controller statement

A separate `/privacy.html` with, at minimum:

- **Controller:** operator name + contact email (Sean O'Riordain, `sean.oriordain@gmail.com` or a project-specific inbox).
- **Lawful basis:** Article 6(1)(f) GDPR — legitimate interests (security research). Document the balancing test (why the interest overrides data-subject rights for this narrow purpose).
- **Purposes:** TLS fingerprint analysis, bot/attacker classification, proxy effectiveness measurement.
- **Categories of data:** source IP, TCP/TLS fingerprints, ASN/GeoIP-derived country, User-Agent, request path, request timing.
- **Retention:** 90 days for metrics and logs (matches `ja4proxy_journald_max_retention`), 5 minutes for Redis bans, indefinite for aggregated/anonymised research outputs.
- **Recipients:** none, unless compelled by law. Document the law-enforcement request path below.
- **Data subject rights:** how to exercise access / erasure / objection. Acknowledge the research-exemption limits (Article 89) where applicable.
- **International transfers:** state whether data stays in eu-central-1 or moves elsewhere for analysis. If analysis machines are outside the EU/EEA, adequacy/SCCs must be addressed.

### 3. Abuse contact wiring

- `abuse@<domain>` MX record must exist *before* go-live. A preflight task in PHASE_10 should resolve it and fail the deploy if missing.
- SOA record's RNAME (responsible-person email) must also resolve.
- WHOIS/RDAP abuse contact for the VM's public IP range is the cloud provider's; document in the runbook that complaints to Alibaba abuse should be forwarded by them, not silently dropped.
- `security.txt` at `/.well-known/security.txt` with `Contact:` and `Expires:` fields, per RFC 9116.

### 4. Lawful-basis and DPIA documentation

Store in `docs/governance/`:

- `LAWFUL_BASIS.md` — the Article 6(1)(f) balancing test written out.
- `DPIA.md` — a short Data Protection Impact Assessment. For this project the DPIA trigger is arguable but we should have one anyway; it is also good ethics-board material.
- `ROPA.md` — Record of Processing Activities (GDPR Article 30). One page, tabular.
- `RETENTION.md` — one-pager mapping each data category to its retention period and its enforcement mechanism (journald config, Loki config, Prometheus TSDB retention flag, Redis TTL).

### 5. Law-enforcement and abuse-report handling

In `docs/governance/LE_REQUESTS.md`:

- Point of contact.
- What we will and will not do without a warrant / court order.
- How we preserve evidence pending a legitimate request (see PHASE_15 evidence-preservation).
- How long we keep the request itself (GDPR Article 15 also applies to the *request*, not just the subject data).

### 6. Research ethics approval

If any output of this project goes into a paper, a talk, or a shared dataset, an ethics-board / IRB approval is standard practice. Capture in `docs/governance/ETHICS.md`:

- Which body (if any) has reviewed the protocol.
- Approval reference number.
- Scope of approved sharing (can JA4 fingerprints be published? can IPs be hashed-and-shared? neither?).

If no ethics-board route is needed because this is personal research, write that down explicitly — a future collaborator will ask.

### 7. Honeypot-entrapment / CFAA-adjacent posture

The honeypot does not entice users to do anything illegal (no fake admin panel inviting brute-force attempts, no bait credentials). If that ever changes — e.g. if the honeypot is extended to log credential-stuffing attempts — re-review.

## Acceptance criteria for this phase

A machine-checkable list so PHASE_10 can gate on it:

```
[ ] curl -sI https://<domain>/honeypot-notice.html returns 200
[ ] curl -sI https://<domain>/privacy.html returns 200
[ ] curl -sI https://<domain>/.well-known/security.txt returns 200 with Contact: and Expires: fields
[ ] dig MX <domain> returns a record
[ ] dig +short abuse@<domain>'s MX host is reachable on :25 from the VM
[ ] docs/governance/LAWFUL_BASIS.md, DPIA.md, ROPA.md, RETENTION.md, LE_REQUESTS.md exist and have been reviewed within the last 12 months
```

Wire the first four as Ansible tasks in the go-live role's precondition block (PHASE_10 §Preconditions).

## Related

- `docs/phases/CRITICAL_REVIEW.md` §C1, §E
- `docs/phases/PHASE_10_GO_LIVE.md` (blocks on this phase)
- `docs/phases/PHASE_15_ABUSE_AND_INCIDENT_RESPONSE.md`
