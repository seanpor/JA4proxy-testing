# Governance documents

Last reviewed: 2026-04-15

This directory holds the legal / ethical / operational governance
documents the operator is expected to keep current. They sit alongside
the code rather than in a separate system so that:

- a reviewer landing on the repo can judge whether the project has
  its legal house in order without chasing external links, and
- CI (`scripts/ci/check_governance_docs.py`) can fail loudly when
  any of these files rots past its review date.

Each file carries a `Last reviewed:` line. CI enforces it is ≤ 365
days old.

## Index

| File | Purpose |
|------|---------|
| [LAWFUL_BASIS.md](LAWFUL_BASIS.md) | GDPR Article 6(1)(f) balancing test for the fingerprint dataset |
| [DPIA.md](DPIA.md) | Data Protection Impact Assessment skeleton |
| [ROPA.md](ROPA.md) | Record of Processing Activities (one-page tabular) |
| [RETENTION.md](RETENTION.md) | Data-category → retention → enforcement-mechanism table |
| [LE_REQUESTS.md](LE_REQUESTS.md) | Law-enforcement request handling procedure |
| [ETHICS.md](ETHICS.md) | Research-ethics / personal-project statement |
| [abuse-reply-template.md](abuse-reply-template.md) | Canned reply for inbound abuse reports (15-C) |
| [OUTBOUND_REPORTING.md](OUTBOUND_REPORTING.md) | Decision tree for LE referrals / CERT reports (15-C) |
| [STAKEHOLDERS.yml](STAKEHOLDERS.yml) | Notification list: who to contact on which event (15-C) |

## Review cadence

Every 365 days, or sooner on any of:

- change to the data collected (new field in the fingerprint record),
- change to retention (edit `RETENTION.md` + `group_vars/all.yml` in
  the same PR),
- change to publication / sharing scope (triggers DPIA re-review),
- legal/regulatory change in the jurisdiction the VM is deployed in.

## Relationship to the rest of the repo

- `THREAT_MODEL.md` (repo root) covers the *security* model; these
  files cover the *legal and ethical* model. They overlap in the data
  exfiltration attack tree and in `RETENTION.md`.
- `docs/phases/PHASE_11_PROD_CUTOVER.md` is where the operator-facing
  go-live checklist references these documents.
- `docs/phases/RUNBOOK.md` references `LE_REQUESTS.md` from the
  "Law-enforcement request" scenario.

## Filling these in

The skeletons are deliberately non-prescriptive on legal content — the
operator is responsible for the wording and for getting independent
advice where needed. What the repo owns is the *structure* and the
review cadence, not the legal conclusions.
