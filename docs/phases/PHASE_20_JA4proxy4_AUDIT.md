# Phase 20 — JA4proxy4 Governance-Theatre Audit (cross-repo record)

**Author:** angry reviewer, 2026-04-22
**Audited repo:** `../JA4proxy4/` (sibling enterprise-production repo; K8s / Helm / Datadog)
**Audit scope:** read-only, no edits or PRs landed in JA4proxy4. This doc exists
in JA4proxy-testing as a cross-repo record so the findings are not lost.

## Why this audit exists

Phase 20 (PR #61, PR #64) surgically fixed 13 defects in JA4proxy-testing
where Phase 18 claimed a control was in place while the mechanism was
cosmetic, broken, or contradicted by config. The same defect *patterns*
are worth checking for in the sibling production repo, since both repos
were evolved in parallel by the same toolchain.

Per `CLAUDE.md`, production governance is not JA4proxy-testing's job —
so this doc is a hand-off, not a remediation plan. The fixes (if the
operator of JA4proxy4 chooses to land them) happen in that repo, not
this one.

## Methodology

For each of the 10 Phase 20 defect categories, grep JA4proxy4 for the
equivalent artifact/control and classify:

- **Compliant** — present and honestly wired.
- **Defective** — present but the control doesn't actually fire.
- **Not applicable** — no equivalent infrastructure exists, so the
  defect pattern cannot occur.

Categories (verbatim from PHASE_20_PHASE_18_REMEDIATION.md):

1. False merge-gate claims
2. Artifacts shipped but never consumed
3. Traceability checkers that pass on file existence
4. Workflow pin validators that check syntax not semantics
5. Opt-in controls labelled "Yes" in an SSDF map
6. Drill cadence as prose, no scheduler
7. Allowlist expiries all on one day
8. SBOM generated but never scanned
9. ADR format check toothless
10. Roadmap entries missing

## Infrastructure inventory

**Present in JA4proxy4:**

- `.github/workflows/ci.yml` — 8 jobs
- `scripts/branch_protection.sh` — bootstrap for required-check config
- `.github/dependabot.yml` — github-actions + pip + gomod
- `tests/test_workflow_pinning.py` — SHA-pin + tag verification + drift check
- `deploy/helm/ja4proxy/` — K8s deployment
- `.goreleaser.yml` — CLI binary SBOM + GPG signing
- `docs/decisions/ADR-001.md` … `ADR-094d.md` — 25 ADRs
- `docs/phases/manifest.yaml` — phase registry

**Absent in JA4proxy4:**

- `.trivyignore` (no CVE allowlist)
- SSDF v1.1 requirements matrix
- `check_requirements_traceability.py` equivalent
- SBOM consumer (CI `trivy sbom` gate)
- Image digest pin file / consumer (Helm `values.yaml:8` uses `tag: latest`)
- Drill scheduler (no reminder workflow)
- Unified governance roadmap / phase-registry completeness checker

## Findings

| # | Pattern | Status | Severity | Evidence |
|---|---|---|---|---|
| 1 | False merge gates | Partially present; honestly stated | P1 (partial) | `scripts/branch_protection.sh:29-42` requires 7 contexts; `smoke-docker` (`ci.yml:189-192`) + `dependency-review` (`ci.yml:169-172`) are explicitly `continue-on-error: true` / PR-only and excluded from required — honest, not theatre |
| 2 | Artifacts not consumed | **Defective** | **P1** | `.goreleaser.yml:53-56` emits `ja4proxy-cli_*_*.bom.json`; `grep -r "\.bom\.json\|sbom"` in `deploy/` + `tests/` + `src/` returns zero consumer hits. Helm `values.yaml:8` uses `tag: latest` — no digest pin file exists at all |
| 3 | Traceability false-positives | Not applicable | — | No requirements matrix; no traceability checker |
| 4 | Workflow pin validator | **Compliant** | — | `tests/test_workflow_pinning.py:167-199` — `test_sha_matches_tag_comment()` validates every `uses: action@<SHA> # v<tag>` against a vendored `KNOWN_ACTION_SHAS` allowlist (lines 42-103, 13 triples). Phase 61 review-fix |
| 5 | Opt-in "Yes" | Not applicable | — | No SSDF map; no cosign deployment config. `.goreleaser.yml:42-51` does GPG signing of CLI checksums (not keyless, not deployment) |
| 6 | Drill cadence w/o scheduler | **Defective** | **P1** | `docs/reports/CYBER_RISK_REVIEW_2026-04-09.md` §F-3 lists DR drill as PROPOSED in Phase 64; `docs/enterprise/security-architecture.md` mentions incident-response drill with no cadence. No `.github/workflows/drill-reminder.yml` or cron |
| 7 | Allowlist single-day expiry | Not applicable | — | No `.trivyignore` to allowlist from |
| 8 | SBOM not scanned | **Defective** | **P1** | `.goreleaser.yml:53-56` emits SBOM; `scripts/run-all-tests.sh:16-19` runs `trivy image --severity HIGH,CRITICAL` only if trivy is installed *locally* — not CI-wired. No `trivy sbom` anywhere |
| 9 | ADR format check | Not applicable (no checker) | P2 (missing control) | 25 ADRs exist under `docs/decisions/`; no `check_adr_format.py` equivalent. Can't be "toothless" if it doesn't exist, but min-content / Superseded-by / index-sync drift is invisible |
| 10 | Roadmap missing entries | Loose | P2 | `docs/phases/manifest.yaml` exists; no completeness check. Unlike JA4proxy-testing's 18-J gap (which was a missing entry in a registry that *claimed* completeness), JA4proxy4 doesn't make the completeness claim — so the defect is thinner |

## Recommended remediation order (if JA4proxy4 operators want to act)

Mirror Phase 20's ordering:

1. **P1 item 2** — pin Helm images by digest (or at minimum, ship a
   `deploy/expected-image-digests.yml` + CI refresh workflow + consumer
   assertion). JA4proxy4 currently deploys `tag: latest`, which is
   strictly worse than pre-Phase-20 JA4proxy-testing (which at least
   shipped pinned digests, even if unconsumed).
2. **P1 item 8** — add a `trivy sbom --severity HIGH,CRITICAL --exit-code 1`
   step to CI against the `.goreleaser` output.
3. **P1 item 6** — add a semi-annual (or whatever cadence matches the
   security-architecture doc) reminder workflow on a cron. JA4proxy-testing
   used `0 9 1 4,10 *` for April/October drills; copy shamelessly.
4. **P2 item 9** — add an ADR format checker if ADR hygiene matters.
5. **P2 item 10** — add a completeness check over `manifest.yaml` if the
   file is meant to be authoritative.

## Summary

JA4proxy4 has **fewer theatre defects than JA4proxy-testing had pre-Phase 20**
because it claims less. No false SSDF rows, no cosign "Yes" that doesn't
sign anything, no runbook-drill cadence in prose. But two P1 defects are
substantive supply-chain gaps:

- Helm deploys `tag: latest` with no digest assertion.
- SBOM is generated and published but scanned by nothing.

If JA4proxy4 is the production surface, both of those should be closed
before any compliance narrative mentions "supply-chain integrity."

## Non-goals

- Landing fixes in JA4proxy4 from this repo. Per `CLAUDE.md` §"Relationship
  to JA4proxy4", this repo must not duplicate production work.
- Re-running this audit on a schedule. This is a one-shot post-Phase 20
  hand-off. If JA4proxy4 wants recurring cross-repo review, the scheduler
  belongs there, not here.
