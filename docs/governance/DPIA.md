# Data Protection Impact Assessment

Last reviewed: 2026-04-15

DPIA for the JA4proxy research honeypot. Structure follows the ICO's
DPIA template; the operator fills the prose. CI enforces presence and
freshness only.

## 1. Identify the need for a DPIA

- What is the processing and why?
- Does it involve systematic monitoring of a publicly accessible area,
  processing on a large scale, or innovative technology? If any is
  yes, a DPIA is required rather than optional.

_<Operator: answer yes/no with justification. Honeypot traffic from
the open internet is "publicly accessible" in the GDPR sense, which
is why this document exists.>_

## 2. Describe the processing

- **Nature:** passive collection of TLS fingerprints + HTTP metadata
  from connections that arrive unsolicited.
- **Scope:** single VM, single domain, EU region. See
  `../phases/PHASE_06_OPERATIONAL_SECURITY.md` for collection paths.
- **Context:** research project, single operator, no customer
  relationship.
- **Purpose:** see `LAWFUL_BASIS.md`.

## 3. Consultation

- Internal: _<who reviewed this DPIA inside the operator's team?>_
- External: _<if any external advisor was consulted, name + date>_.
- Data subjects: consultation is impractical for unsolicited traffic;
  the honeypot notice page + `/privacy.html` provide notice instead.

## 4. Necessity and proportionality

- Lawful basis: see `LAWFUL_BASIS.md`.
- Data minimisation: _<what isn't collected? E.g. request body is
  discarded, forms are not persisted, DNS queries are not logged>_.
- Retention: see `RETENTION.md`.
- Data subject rights: `/privacy.html` publishes the contact route.

## 5. Risks

| # | Risk to data subjects | Likelihood | Severity | Overall |
|---|----------------------|------------|----------|---------|
| 1 | Dataset deanonymisation via IP + timing | Medium | Medium | Medium |
| 2 | Abuse report misattribution (scanner IP flagged as malicious) | Low | Medium | Low |
| 3 | Dataset loss / unauthorised disclosure | Low | Medium | Low |

## 6. Mitigations

Cross-reference `../../THREAT_MODEL.md` §2.4 (data exfiltration) for
the technical mitigations. Summary:

- Observability ports loopback-only outside the live stage.
- HMAC anonymisation (chunk 12-B, pending) before any external share.
- No continuous export channel; operator-initiated `scp` only.
- Evidence tarballs mode-0600 in mode-0700 directory (chunk 15-A).

## 7. Sign-off

- **DPO / equivalent:** _<name, date>_ — single-operator project; if
  there is no DPO, state that explicitly.
- **Reviewer:** _<name, date>_.
- **Next review due:** 2027-04-15 (365 days).

## 8. Changes since last review

_<Dated list.>_
