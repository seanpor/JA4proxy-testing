# Research ethics statement

Last reviewed: 2026-04-15

Research-ethics statement for the JA4proxy honeypot. Single-operator
projects generally do not have an institutional review board; this
file is the operator's self-audit substitute.

## 1. Research question

_<State the research question the honeypot exists to answer. Be
specific — "what bots are there" is not a research question; "how
quickly do JA4 fingerprints drift after a new TLS library version
releases" is.>_

## 2. Subjects

- Subjects are the operators of machines that connect to the
  honeypot unsolicited (scanners, bots, researchers).
- They are not engaged with as people; only the network artefacts
  they generate are retained.
- Consent is not obtained, because consent is impractical for
  unsolicited traffic. Notice is substituted via `/privacy.html` and
  the honeypot landing page.

## 3. Harms and mitigations

| Potential harm | Mitigation |
|----------------|------------|
| Misattribution of a scanner IP to malicious activity in published dataset | HMAC anonymisation (12-B) before any share; aggregated statistics only |
| Use of the dataset to aid offensive targeting | No publication of raw IP lists; research output focuses on aggregate fingerprint statistics |
| Re-identification of individual researchers running security scans | Same HMAC approach; no cross-correlation with external identifiers |
| Operator absence during an incident impacting a third party | On-call posture in `README.md`; heartbeat + blackbox alerts |

## 4. Publication policy

- Aggregated statistics: OK to publish.
- Per-IP or per-fingerprint raw records: only with HMAC anonymisation
  and only where publication is necessary for the research claim.
- Source code and tooling: open, under the repo's existing licence.
- Timing data tied to IPs: treat as identifying; apply the same
  anonymisation.

## 5. Review

- This statement is reviewed every 365 days.
- Any change to the research question, the collected fields, or the
  publication policy triggers an immediate review (not the annual
  one).

## 6. Changes since last review

_<Dated list.>_
