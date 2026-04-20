# NIST SSDF v1.1 control mapping

Last reviewed: 2026-04-19

This document maps every task in the NIST Secure Software Development
Framework (SP 800-218, SSDF v1.1) to the role, CI check, or phase doc
in this repository that satisfies it — or to an explicit "N/A because
X" when the task does not apply to a single-VM research honeypot.

The point is to make compliance questions answerable with a link
instead of an essay, and to surface gaps early. CI validates that
every backticked path cited below still exists in the repo; renaming
a satisfier without updating this document breaks `make test`.

Status values:

- **Yes** — implemented in this repo.
- **N/A** — task does not apply in this context. Rationale required.
- **Partial** — implemented in part; the rest is deferred. Satisfier
  links to what exists today.
- **Not yet** — on the roadmap. Links to the tracking phase chunk or
  issue.

> **Note on scope.** This is a single-person research deployment
> (`CLAUDE.md`). Organisational practices (roles, training programmes,
> tool inventories) are necessarily compressed into "the maintainer is
> everyone"; where the framework asks for evidence of org-wide
> processes we record that honestly as `N/A` with the reason.

---

## PO — Prepare the Organization

| Task | Summary | Status | Satisfier / rationale |
|------|---------|--------|-----------------------|
| PO.1.1 | Identify and document security requirements | Yes | `docs/REQUIREMENTS.md` — 21 numbered F-\*/NF-\* requirements, path-traceable via `scripts/ci/check_requirements_traceability.py` |
| PO.1.2 | Identify and document compliance requirements | Yes | This file (`docs/COMPLIANCE_SSDF.md`) plus `docs/governance/LAWFUL_BASIS.md` and `docs/governance/ROPA.md` |
| PO.1.3 | Communicate requirements to third parties | N/A | No third-party developers. Sole-maintainer research project; see `CLAUDE.md` |
| PO.2.1 | Create roles and responsibilities | Partial | `docs/governance/STAKEHOLDERS.yml` names roles (maintainer, operator, abuse contact). Formal separation of duties not applicable |
| PO.2.2 | Provide role-based training | N/A | Sole maintainer; no team to train. Learning happens on the research itself |
| PO.2.3 | Obtain upper-management commitment | N/A | No hierarchical organization |
| PO.3.1 | Specify tools used in the SDLC | Yes | `AGENTS.md` plus `requirements-dev.txt` pin the toolchain (ansible, yamllint, ansible-lint, ruff, shellcheck, pymarkdown). See `./AGENTS.md` |
| PO.3.2 | Deploy and maintain tools | Yes | `./Makefile` target `make lint-install` reproduces the dev venv from `./requirements-dev.txt` |
| PO.3.3 | Generate artefact data to demonstrate use | Yes | `.github/workflows/ci.yml` runs `make lint` + `make test` on every PR; green runs are the artefact |
| PO.4.1 | Define criteria for security checks | Yes | `AGENTS.md` pre-merge contract; `docs/REQUIREMENTS.md` traces each NF-\* to a check |
| PO.4.2 | Implement processes to collect / review check results | Yes | CI gates on `make lint` and `make test`; Dependabot opens PRs for dep updates (`.github/dependabot.yml`) |
| PO.5.1 | Separate and protect build environments | Yes | ADR 0001 forbids build tools on the target VM (`docs/adr/0001-no-build-tools-on-server.md`). Build happens on a separate control host via `deploy/roles/02-artifact-build/` |
| PO.5.2 | Harden and monitor build environments | Partial | Build host is operator-controlled; monitoring of the host itself is out of repo scope. `deploy/roles/08-hardening/` covers the target VM |

---

## PS — Protect Software

| Task | Summary | Status | Satisfier / rationale |
|------|---------|--------|-----------------------|
| PS.1.1 | Store all forms of code securely | Yes | Git + GitHub; `.github/workflows/scorecard.yml` runs OpenSSF Scorecard (Phase 18-E); secrets never committed — the deploy/.vault/ directory is gitignored (see repo-root `./.gitignore`) and re-rendered from `deploy/scripts/generate-secrets.sh` |
| PS.2.1 | Provide integrity verification for releases | Yes | cosign sign-blob signs the binary and SBOM in `deploy/roles/02-artifact-build/tasks/build.yml`; verify happens before systemd start in `deploy/roles/03-ja4proxy-deploy/tasks/main.yml`. See Phase 18-D |
| PS.3.1 | Archive each software release | Yes | Immutable git tags + sha256-pinned `expected-binary-sha256.txt` (`scripts/ci/check_pinned_artifacts.py`) |
| PS.3.2 | Collect provenance data for each release | Yes | CycloneDX SBOM (`scripts/ci/check_sbom.py`, Phase 18-A) + `deploy/templates/binary-provenance.yml.j2` emitting commit/build-host facts alongside the binary |

---

## PW — Produce Well-Secured Software

| Task | Summary | Status | Satisfier / rationale |
|------|---------|--------|-----------------------|
| PW.1.1 | Use secure design practices | Yes | STRIDE threat model (`./THREAT_MODEL.md`, at repo root); staged go-live (`deploy/roles/10-go-live/`) keeps the service locked to localhost until an operator confirms |
| PW.1.2 | Document security requirements that constrain the design | Yes | ADR log (`docs/adr/`) records design decisions that are load-bearing for security (build-tool exclusion, monitor-first dial, no external intel) |
| PW.1.3 | Reuse existing well-secured software where feasible | Yes | Official Docker Hub images for HAProxy/Redis/Caddy/Prometheus/Grafana/Loki — see `docs/adr/0004-no-container-registry.md` |
| PW.2.1 | Review the design to confirm it meets security requirements | Yes | `./THREAT_MODEL.md` reviewed within 365 days (gated by `scripts/ci/check_threat_model.py`) |
| PW.4.1 | Acquire well-secured components | Yes | Upstream components are pinned by digest in `deploy/expected-image-digests.yml` and scanned by Trivy (`scripts/ci/scan_images.sh`, Phase 18-B) |
| PW.4.2 | Create and maintain lists of approved components | Yes | `deploy/expected-image-digests.yml` + `deploy/inventory/group_vars/all.yml` image-tag vars are the allowlist |
| PW.4.4 | Verify each acquired component's integrity | Yes | Image digests enforced in role `deploy/roles/09-image-digests/`; Go binary sha256 checked in `deploy/roles/03-ja4proxy-deploy/` against `expected-binary-sha256.txt` |
| PW.4.5 | Discourage use of unmaintained software | Yes | Dependabot config (`.github/dependabot.yml`) opens PRs for outdated pip + GitHub Actions deps; weekly digest-refresh workflow (`.github/workflows/digest-update.yml`) nudges stale image pins |
| PW.5.1 | Follow secure coding practices | Yes | `ruff` lints all first-party Python (`scripts/ci/` + `deploy/scripts/anonymise.py`); `ansible-lint` at `production` profile is the Ansible equivalent — both wired into `./Makefile` `lint` target |
| PW.6.1 | Use compiler/interpreter/build-tool security features | Yes | `ja4proxy_go_build_flags` injects `-trimpath -buildvcs=true` (`scripts/ci/check_go_build_flags.py`, Phase 14-A) |
| PW.6.2 | Determine which settings to use and document | Yes | Flag rationale captured in `deploy/inventory/group_vars/all.yml` comments alongside the variable |
| PW.7.1 | Determine whether code review is needed | Yes | Every change lands via PR on GitHub; main is protected, CI required. See `./AGENTS.md` pre-merge contract and the `ci` workflow in `.github/workflows/ci.yml` |
| PW.7.2 | Perform code review | Partial | Solo-maintainer self-review with CI gating (`.github/workflows/ci.yml`). Explicitly acknowledged in `./CLAUDE.md`; no reviewer-of-last-resort exists |
| PW.8.1 | Determine whether executable-code testing is needed | Yes | Yes for both the Ansible layer (gated by `./Makefile`'s `make test` target) and supporting tooling (`deploy/scripts/test_anonymise.py`) |
| PW.8.2 | Design and perform the testing | Yes | `make test` runs 40+ structural CI checks; Molecule scenarios exercise role idempotency (`scripts/ci/check_molecule_scenarios.py`) |
| PW.9.1 | Define a baseline of secure settings | Yes | `deploy/roles/08-hardening/` (sysctl, AppArmor, AIDE, kernel module blocklist); `deploy/roles/01-vm-provisioning/tasks/ssh.yml` (SSH config) |
| PW.9.2 | Implement the baseline as the default | Yes | Baseline applied on every deploy; `ja4proxy_dial: 0` default (ADR `docs/adr/0006-dial-zero-at-start.md`) keeps the honeypot in monitor-only mode unless explicitly escalated |

---

## RV — Respond to Vulnerabilities

| Task | Summary | Status | Satisfier / rationale |
|------|---------|--------|-----------------------|
| RV.1.1 | Identify and confirm vulnerabilities on an ongoing basis | Yes | `govulncheck` at build time (`scripts/ci/check_govulncheck_wired.py`, Phase 18-C); Trivy image scan in CI (`scripts/ci/check_image_scan.py`, Phase 18-B); Dependabot for deps (`.github/dependabot.yml`, Phase 18-F) |
| RV.1.2 | Review and analyse vulnerability reports | Partial | Manual review of CI output + Dependabot PRs. `.trivyignore` entries carry expiry dates (`scripts/ci/check_image_scan.py`) so deferred decisions auto-reopen |
| RV.1.3 | Have a vulnerability disclosure programme | Yes | `docs/phases/PHASE_11_LEGAL_ETHICS_AND_HONEYPOT_DISCLOSURE.md` plus `security.txt` served by the honeypot (`scripts/ci/check_security_txt.py`); contact email is in the rendered file |
| RV.2.1 | Analyse each vulnerability | Yes | Mapped to runbook scenarios in `docs/phases/RUNBOOK.md` (`scripts/ci/check_runbook_scenarios.py`) |
| RV.2.2 | Plan and implement remediation | Yes | Remediation lands as a PR that goes through the same CI gates as any other change (`.github/workflows/ci.yml`); the `./AGENTS.md` pre-merge contract applies |
| RV.3.1 | Analyse vulnerabilities for root causes | Partial | Post-mortem templates for runbook scenarios 1–8 in `docs/phases/RUNBOOK.md`; no formal RCA doc yet |
| RV.3.2 | Analyse root-cause frequency | N/A | Insufficient deployment history to be meaningful on a research box. Revisit when ≥ 1 year of production incidents exist |
| RV.3.3 | Use information to improve SDLC | Yes | Phase chunks are the mechanism — 18-B was tightened to HIGH-blocking (18-B-2) after CVE-2023-2454x whack-a-mole on `redis:7-alpine`. See `docs/phases/PHASE_18_SWEBOK_GAP_CLOSURE.md` 18-B landing notes |
| RV.3.4 | Have a process for reviewing EOL components | Partial | Dependabot (`.github/dependabot.yml`) surfaces outdated deps; digest-refresh workflow (`.github/workflows/digest-update.yml`) surfaces stale image pins. No separate EOL calendar |

---

## Deferred / out of scope

The following practices are deliberately out of scope for this repo
and will not be retrofitted unless context changes:

- **SLSA L3 hermetic builds.** Requires moving the Go build into a
  reproducible CI runner. Tracked as a deferred item in
  `docs/phases/PHASE_18_SWEBOK_GAP_CLOSURE.md`.
- **Formal code review by a second party.** Single-maintainer project;
  `PW.7.2` is marked Partial for this reason and cannot be closed by
  process alone.
- **ISO 27001 / FedRAMP / SOC 2 mappings.** Separate efforts with
  different acceptance criteria. Not started.

---

## How this document is maintained

- Any PR that adds, renames, or deletes a role, CI check, phase doc,
  or ADR that is cited above must update this file in the same
  commit. `make test` fails otherwise.
- When a "Partial" or "Not yet" row is closed, flip it to "Yes" and
  cite the satisfier path. Do not delete the row — the history is the
  value.
- Refresh the `Last reviewed:` line at the top at least every 365
  days; CI enforces this via `scripts/ci/check_compliance_ssdf.py`.
