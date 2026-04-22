# Requirements & traceability

Last reviewed: 2026-04-19

Numbered functional (F-\*) and non-functional (NF-\*) requirements for
the JA4proxy research honeypot. Every row cites the role, template,
script, CI check, or phase doc that satisfies it. Renaming or removing
a satisfier without updating this table fails `make test` via
`scripts/ci/check_requirements_traceability.py`.

Scope: this repo only — the research honeypot stack and its staged
go-live workflow. Production K8s/Helm requirements live in the sibling
`JA4proxy4` repo and are out of scope here (see `CLAUDE.md`).

How to read a row: the **Satisfier(s)** column lists every backtick-quoted
path the traceability check verifies. A row may cite both the
implementation (a role or template) and the regression check that
guards it. Adding a new requirement means adding a satisfier path that
already exists; adding a new check means citing it from the row whose
invariant it guards.

## Functional requirements

| ID    | Requirement                                                                                                                            | Satisfier(s)                                                                                                                                |
| ----- | -------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------- |
| F-01  | The honeypot serves a clear warning page identifying itself as a research honeypot, not a real service.                                | `deploy/templates/honeypot-index.html`, `scripts/ci/check_honeypot_disclosure.py`, `docs/phases/PHASE_11_LEGAL_ETHICS_AND_HONEYPOT_DISCLOSURE.md` |
| F-02  | Visitors can reach a privacy notice and a `/.well-known/security.txt` with operator contact + expiry.                                  | `deploy/templates/privacy.html.j2`, `deploy/templates/security.txt.j2`, `scripts/ci/check_privacy_page.py`, `scripts/ci/check_security_txt.py` |
| F-03  | Enforcement is governed by a single integer dial 0–100 that is hot-reloadable via `SIGHUP` so an operator can escalate without restart. | `deploy/inventory/group_vars/all.yml`, `deploy/templates/ja4proxy.service.j2`, `docs/phases/PHASE_07_VALIDATION_TESTING.md`                  |
| F-04  | The proxy exposes health and metrics endpoints (`/health`, `/health/deep`, `:9090/metrics`) so liveness can be checked without log scraping. | `deploy/roles/03-ja4proxy-deploy`, `deploy/scripts/verify-local.sh`                                                                          |
| F-05  | A dead-man's-switch heartbeat pings an external URL on a fixed cadence so a silently-down VM is detected within one interval.          | `deploy/templates/heartbeat.timer.j2`, `deploy/templates/heartbeat.service.j2`, `scripts/ci/check_heartbeat_timer.py`                       |
| F-06  | Collected research data is exported on a recurring timer with anonymisation applied before it leaves the VM.                           | `deploy/templates/ja4proxy-export.timer.j2`, `deploy/scripts/export-week.sh`, `deploy/scripts/anonymise.py`, `scripts/ci/check_export_timer.py`, `scripts/ci/check_anonymise.py` |
| F-07  | Every secret in `deploy/.vault/secrets.yml` can be rotated end-to-end via a dedicated playbook + Make target without redeploying the stack. | `deploy/playbooks/rotate.yml`, `deploy/roles/12-secrets-rotation`, `scripts/ci/check_secrets_rotation.py`                                   |
| F-08  | Public exposure follows a three-stage workflow (locked → verified → live); Phase 10 is inert unless an explicit confirm flag is set.   | `deploy/roles/10-go-live`, `deploy/scripts/verify-local.sh`, `docs/phases/PHASE_10_GO_LIVE.md`                                              |
| F-09  | Operators can preserve forensic evidence (running container state, recent logs) before tearing down a suspect VM.                      | `deploy/scripts/preserve-evidence.sh`, `scripts/ci/check_preserve_evidence.py`, `docs/phases/PHASE_15_ABUSE_AND_INCIDENT_RESPONSE.md`       |
| F-10  | A documented incident-response runbook covers at minimum: VM compromise, cert near expiry, Loki disk full, abuse complaint, secrets leak. | `docs/phases/RUNBOOK.md`, `scripts/ci/check_runbook_scenarios.py`                                                                            |

## Non-functional requirements

| ID     | Requirement                                                                                                                        | Satisfier(s)                                                                                                                                |
| ------ | ---------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------- |
| NF-01  | The dial defaults to **0** (monitor-only). Raising the default in code requires an explicit, justified change.                     | `deploy/inventory/group_vars/all.yml`, `CLAUDE.md`, `AGENTS.md`                                                                              |
| NF-02  | No real PII is solicited or persisted; outbound research data is anonymised before export.                                         | `deploy/scripts/anonymise.py`, `deploy/scripts/test_anonymise.py`, `docs/governance/ANONYMISATION.md`, `docs/governance/DPIA.md`             |
| NF-03  | Log and metric retention is bounded: journald ≤ 90 d / 2 GB, Loki ≤ 90 d, Prometheus retention time + size both capped.            | `deploy/templates/journald.conf.j2`, `deploy/templates/loki.yml.j2`, `deploy/templates/prometheus.yml.j2`, `scripts/ci/check_journald_template.py`, `scripts/ci/check_loki_retention.py`, `scripts/ci/check_prometheus_retention.py` |
| NF-04  | The JA4proxy binary's provenance is verifiable: pinned SHA-256, reproducible build flags (`-trimpath`, `-buildvcs`), CycloneDX SBOM emitted, govulncheck run at build. | `deploy/roles/02-artifact-build`, `deploy/expected-binary-sha256.txt`, `deploy/templates/binary-provenance.yml.j2`, `scripts/ci/check_pinned_artifacts.py`, `scripts/ci/check_go_build_flags.py`, `scripts/ci/check_sbom.py`, `scripts/ci/check_govulncheck_wired.py` |
| NF-05  | Container images have pinned SHA-256 digests declared in `deploy/expected-image-digests.yml` (weekly-refreshed, enforced at deploy by role 09), and a Trivy scan fails the `image-scan` job on any CRITICAL or HIGH finding. `image-scan` is a **required** status check on `main` (Phase 20 follow-up), so a red scan mechanically blocks merge. | `deploy/roles/09-image-digests`, `deploy/expected-image-digests.yml`, `deploy/templates/docker-compose.yml.j2`, `.github/workflows/ci.yml`, `scripts/ci/check_digest_regex.py`, `scripts/ci/check_image_scan.py`, `scripts/ci/scan_images.sh` |
| NF-06  | TLS issuance defaults to ACME staging; production Let's Encrypt is only used after the go-live confirmation flag flips.            | `deploy/templates/caddyfile.j2`, `deploy/inventory/group_vars/all.yml`, `scripts/ci/check_acme_staging.py`                                  |
| NF-07  | SSH access is key-only, root login disabled, and the public attack surface before go-live is restricted to port 22 from the admin IP. | `deploy/templates/sshd_config.j2`, `deploy/roles/01-vm-provisioning`, `deploy/playbooks/site.yml`                                            |
| NF-08  | Compliance and ethics paperwork (DPIA, lawful basis, ROPA, retention, ethics, anonymisation, abuse-reply, outbound reporting, stakeholders, LE-requests) exists, is indexed, and is re-reviewed at least annually. | `docs/governance/README.md`, `docs/governance/DPIA.md`, `docs/governance/LAWFUL_BASIS.md`, `docs/governance/ROPA.md`, `docs/governance/RETENTION.md`, `docs/governance/ETHICS.md`, `docs/governance/ANONYMISATION.md`, `docs/governance/abuse-reply-template.md`, `docs/governance/OUTBOUND_REPORTING.md`, `docs/governance/STAKEHOLDERS.yml`, `docs/governance/LE_REQUESTS.md`, `scripts/ci/check_governance_docs.py` |
| NF-09  | A repo-level threat model exists, covers the four agreed attack-tree targets + residual risk, and is re-reviewed at least annually. | `THREAT_MODEL.md`, `scripts/ci/check_threat_model.py`                                                                                        |
| NF-10  | Secrets generation is idempotent: re-running the bootstrap script preserves existing values and never overwrites a populated vault. | `deploy/scripts/generate-secrets.sh`, `scripts/ci/check_secrets_path.py`                                                                     |
| NF-11  | Dependency hygiene: GitHub Actions and `requirements-dev.txt` are watched by Dependabot, and CI itself runs only SHA-pinned actions. | `.github/dependabot.yml`, `requirements-dev.txt`, `scripts/ci/check_dependabot.py`, `scripts/ci/check_workflow_pins.py`                      |

## Format contract (read before editing)

The traceability check parses each table row as follows:

1. The row must start with an `F-NN` or `NF-NN` ID in the first cell.
2. Every backtick-quoted token in the **Satisfier(s)** cell that contains
   a `/` is treated as a repo-relative path and must resolve to an
   existing file or directory.
3. Backticked tokens without a `/` (e.g. `` `SIGHUP` ``, `` `make test` ``)
   are ignored — use them freely in the requirement text or satisfier
   commentary.
4. Every requirement must have at least one satisfier path.

Adding a new requirement: pick the next free `F-NN` / `NF-NN`, write the
requirement, list at least one existing satisfier path. Removing a
satisfier without removing the row will fail `make test`.

## Out of scope (intentional)

Capturing upstream stakeholder needs, full SWEBOK §Requirements
elicitation, formal acceptance signoff, and traceability matrices to
external standards (ISO 25010, OWASP ASVS) are out of scope for a
single-person research project. SLSA L3, FedRAMP, and ISO 27001 are
listed as **Deferred** in `docs/phases/PHASE_18_SWEBOK_GAP_CLOSURE.md`.
