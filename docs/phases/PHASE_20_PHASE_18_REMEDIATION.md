# Phase 20 — Phase 18 Remediation (governance theatre fixes)

**Author:** angry reviewer, 2026-04-21
**Scope:** defects in merged Phase 18 work (PRs #44–#60) that claim a control is in place while the mechanism is cosmetic, broken, or actively contradicted by config.
**Status (2026-04-22):** 13 of 13 remediation items merged in PR #61 (commit `ab110f5`). P1-9's ecosystem-expansion half was withdrawn on inspection (see below) and the comment-refresh half landed. `make lint` and `make test` green locally and on post-merge `main` CI.

**Follow-up (2026-04-22).** P0-1 initially took option (B) "honest advisory" in PR #61. Post-merge the branch-protection flip was executed and `image-scan` is now a required status check alongside `lint-and-test`. Docs reverted to reflect the mechanical gate. See P0-1's Resolution block below.

**P1-9 scoping update (2026-04-22).** The original defect proposed adding `docker` and `gomod` Dependabot ecosystems. On inspection, this repo has no `Dockerfile` and no `go.mod` (the Go source lives in the sibling `JA4proxy4` checkout; Docker base images are referenced via Jinja-templated compose and tracked by the separate `digest-update.yml` weekly workflow against Docker Hub). Ansible collections have no Dependabot ecosystem. So the only applicable part of P1-9 was the stale comment refresh, which landed; the ecosystem-expansion half is formally withdrawn.

## Summary of the indictment

Phase 18 landed a lot of docs, matrices, and scoring pages that *describe* a mature SSDLC. In practice:

1. The "hard merge gate" for Trivy HIGH findings is advisory — `image-scan` is not a required check on `main`.
2. The Docker Hub digest pin file (`deploy/expected-image-digests.yml`) is shipped, refreshed weekly, and referenced by zero roles/templates — compose still renders by tag.
3. The requirements-traceability checker greenlights rows whose "satisfier" is any file that exists — it does not verify behaviour. Several satisfiers are therefore passing falsely (NF-04 cosign, NF-05 digest pins).
4. The SSDF mapping miscounts its own rows in the landing notes (says 42 maps, doc has 43; claims "5 Partial" and then lists 6 IDs).
5. Runbook drill "cadence" is a markdown paragraph with no scheduler — a missed drill is silent.
6. `.trivyignore` expiries are all the same day, so the allowlist flips to red in one big-bang event instead of forcing a periodic decision.
7. `check_workflow_pins.py` validates the *shape* of the `# v…` comment, not that the SHA resolves to the claimed tag.
8. Cosign signing is opt-in (empty key paths by default) and the check enforces the empty default — PS.2.1 in the SSDF map is really "Yes if the operator remembers to configure keys".
9. GOVERNANCE_ROADMAP omits 18-J entirely (neither Done nor Deferred).

Fixing these restores the story to reality. Many fixes are one-line.

---

## P0 — false claims and broken gates (fix first)

### P0-1. "HIGH Trivy is a hard merge gate" — not in branch protection

**Evidence:**
- `.trivyignore:14` — "Since 18-B-2, HIGH is a hard merge gate (same as CRITICAL)".
- `docs/phases/PHASE_18_SWEBOK_GAP_CLOSURE.md:141-147` — repeats the claim.
- `docs/REQUIREMENTS.md:45` NF-05 — ties the claim to Trivy.
- `.github/workflows/ci.yml:43-47` — **the comment itself admits** "Not required to merge while the Trivy DB churns".
- `gh api repos/seanpor/JA4proxy-testing/branches/main/protection` → `required_status_checks.contexts = ["lint-and-test"]`. `image-scan` is not required, has no `needs:` link, and does not block a merge.

**Fix (pick one):**
- **(A, preferred)** Add `image-scan` to required status checks on `main` (and any other protected branches). Document on BRANCH_PROTECTION. Remove the apologetic comment in `ci.yml:44-47`.
- **(B, honest fallback)** Delete every "hard merge gate" phrase (`.trivyignore:14`, `PHASE_18…md:141-147`, `REQUIREMENTS.md:45` NF-05), downgrade SSDF rows that cite it (RV.1.2, RV.3.1, PW.7.2 as applicable) from Yes→Partial, and call it advisory.

Owner: whoever owns branch protection. Effort: 10 min for (A), 20 min for (B).

**Resolution (2026-04-22, Phase 20 follow-up).** Initially landed as (B) in PR #61 (honest advisory language). Post-merge the branch-protection flip was executed: `PATCH /repos/seanpor/JA4proxy-testing/branches/main/protection/required_status_checks` now lists both `lint-and-test` and `image-scan` with `strict: true`. The advisory language in `.trivyignore`, `REQUIREMENTS.md` NF-05, `ci.yml:43-47`, and `PHASE_18…md` §18-B-2 was reverted to reflect the mechanical gate. Option (A) is now the live state; (B) is history.

### P0-2. `deploy/expected-image-digests.yml` is never consumed

**Evidence:**
- File exists with 9 pins; `.github/workflows/digest-update.yml` refreshes it weekly via `scripts/ci/update_digests.py`.
- `grep -r expected-image-digests` hits only: `Makefile`, `digest-update.yml`, `update_digests.py`, `check_digest_regex.py`, `docs/COMPLIANCE_SSDF.md`, `docs/adr/0004-no-container-registry.md`, `PHASE_18_SWEBOK_GAP_CLOSURE.md`.
- Zero hits under `deploy/roles/` or `deploy/templates/`. Role 09 (image digests) does not read the file; compose renders by tag.
- `PHASE_18…md:358-365` admits "currently advisory".
- `PHASE_18…md:353-354` claims the weekly workflow "calls `make update-digests`" but `digest-update.yml:36` actually runs `python3 scripts/ci/update_digests.py`.

**Fix:**
- Wire the pin file into role 09: before compose renders, resolve each image's live digest (`docker manifest inspect` or `skopeo inspect`) and assert it matches the pin. Fail the play on mismatch. Either emit `image@sha256:…` into compose or keep the tag but gate deploy on the assertion.
- Update NF-05 satisfier and the SSDF row for PW.4.4 / PW.4.5 (supply-chain) to cite the role task, not the pin file alone.
- Correct the `make update-digests` → `python3 scripts/ci/update_digests.py` misstatement in the phase doc.

Owner: deploy-roles. Effort: 1–2 hr.

### P0-3. `check_requirements_traceability.py` passes on file existence

**Evidence:** `scripts/ci/check_requirements_traceability.py:93-95` asserts the satisfier path exists. No content assertion. Result: NF-04 (cosign) and NF-05 (digest pins) go green even when the mechanism does nothing.

**Fix:** Per-requirement behavioural assertions:
- NF-04: satisfier must contain `cosign verify-blob` **and** the verify task must not be gated on `when: <key> | length > 0`.
- NF-05: satisfier must contain `Docker-Content-Digest` or a digest-comparison assertion, not just the pin filename.
- Add a smoke test row to `tests/` that runs the checker against a deliberately weakened satisfier and asserts it goes red.

Owner: ci-scripts. Effort: 1 hr.

---

## P1 — theatre / partial

### P1-4. SSDF landing notes miscount rows

`PHASE_18…md:545` says "42 SSDF v1.1 tasks". `:550` says "43 task rows parsed" (which matches reality: 43). `:547` says "5 Partial" then lists 6 IDs. Fix the three numbers.

### P1-5. Runbook drill cadence has no scheduler

`PHASE_18…md:593-594` and `.github/ISSUE_TEMPLATE/runbook-drill.md` describe April/October drills. `check_runbook_scenarios.py` only asserts the heading exists. No cron, no reminder workflow.

**Fix:** add `.github/workflows/drill-reminder.yml` on a semi-annual cron (`0 9 1 4,10 *`) that opens an issue from the template. Link the workflow from the phase doc. Either that or strike "cadence" from COMPLIANCE_SSDF.md and call it "on-demand".

### P1-6. Cosign is opt-in but SSDF row PS.2.1 says "Yes"

`deploy/inventory/group_vars/all.yml` defaults `ja4proxy_cosign_private_key_path` and `ja4proxy_cosign_public_key_path` to `""`. All 7 cosign tasks use `when: … | length > 0`. `scripts/ci/check_cosign_wired.py:210-214` **enforces the empty default**. If the operator doesn't configure keys, nothing is signed and nothing is verified — but PS.2.1 is still "Yes".

**Fix:** downgrade PS.2.1 and NF-04 to "Partial — opt-in; unsigned deploy permitted". Add a run-time assertion at Phase 10 (`go-live`) that refuses to rebind to 0.0.0.0 if the keys are empty — that at least ties the "Yes" to the public-exposure path.

### P1-7. `check_workflow_pins.py` validates syntax only

`scripts/ci/check_workflow_pins.py:63-66` enforces a trailing `# v<digits>` comment. It does not verify the SHA resolves to that tag. A future PR could write `actions/checkout@<any-hex> # v99.99.99` and pass CI.

**Fix:** call `gh api repos/<owner>/<repo>/git/ref/tags/<tag>` (cached per-SHA) and diff against the comment. If offline, print a warning instead of skipping silently.

### P1-8. SBOM is generated but never read

`02-artifact-build/tasks/build.yml:286-344` ships `ja4proxy.cdx.json` + `.sig` to the target. `check_sbom.py` only validates schema of a transient render. No consumer ever diffs SBOM components against the pin file, no scanner runs over it, no attestation gate refers to it.

**Fix:** at minimum, add a post-build step that runs `trivy sbom --severity HIGH,CRITICAL --exit-code 1 ja4proxy.cdx.json` and fail CI on hits. Long-term: compare SBOM components to the digest-pin file (see P0-2).

### P1-9. Dependabot ecosystem gaps + stale comment

`.github/dependabot.yml:29` — "We already pin by tag (actions/checkout@v4 etc.)" — wrong, everything is SHA-pinned since 18-E. Coverage: `pip` + `github-actions` only. Missing: `docker` (for digest pins), `gomod` (for the sibling Go checkout that is invoked by this repo's build), Ansible collections (`deploy/requirements.yml`).

**Fix:** refresh the comment, add `docker` and `gomod` ecosystems, update `check_dependabot.py:20` to require the expanded set.

### P1-10. ADR format check is toothless

`scripts/ci/check_adr_format.py` validates filename + heading order + first-word-of-Status. It does not enforce: minimum content under Context/Decision/Consequences, `Superseded by NNNN-…md` pointer on a Deprecated/Superseded status, uniqueness of slug, or the index table in `docs/adr/README.md` staying in sync. README:41-47 claims ADRs are append-only; nothing mechanically stops rewriting an accepted ADR's Decision section.

**Fix:** extend the checker: require ≥100 chars in each required section; if Status ∈ {Deprecated, Superseded}, require a `Superseded by` link that resolves to another ADR; diff the README table against the filesystem.

---

## P2 — sloppy but harmless

### P2-11. `.trivyignore` expiry dates all identical (2026-05-17)

All 17 entries expire same day → one big-bang red day. Stagger expiries across ±2 weeks so the "periodic decision" goal holds. Also deduplicate justifications that currently appear in both `.trivyignore` and `PHASE_18…md:128-139`.

### P2-12. GOVERNANCE_ROADMAP omits 18-J

`docs/phases/GOVERNANCE_ROADMAP.md:1059-1070` lists 18-A…L except 18-J (CIS/Lynis benchmark scoring — see `PHASE_18…md:469-500`). Not marked Done, not marked Deferred. Either land 18-J or explicitly defer it in the roadmap.

### P2-13. CRITICAL_REVIEW banner points at an incomplete tracker

`docs/phases/CRITICAL_REVIEW.md:6-14` tells the reader that the landing log is authoritative. The landing log (`GOVERNANCE_ROADMAP.md`) is itself missing 18-J (P2-12). Either add 18-J there or weaken the banner.

---

## Fix order (recommended)

1. **P0-1** — pick honest language or add the required check (10–20 min).
2. **P0-3** — tighten the traceability checker so subsequent fixes actually get verified (1 hr).
3. **P0-2** — wire the digest pin file or delete it (1–2 hr).
4. **P1-6 / P1-8 / P1-5** — downgrade Yeses that are actually Partials and/or add the missing enforcement.
5. **P1-4 / P2-12 / P2-13** — doc-only truth-up.
6. **P1-7 / P1-9 / P1-10** — harden checkers (do last; they protect the fixes above from regressing).

Each defect should land as its own PR (small, reviewable), against `main`, with a one-line entry in `GOVERNANCE_ROADMAP.md` under a new "Phase 20" section. If a defect changes an SSDF row from Yes→Partial, the PR must update `docs/COMPLIANCE_SSDF.md`, the SSDF landing note counts in `PHASE_18_SWEBOK_GAP_CLOSURE.md`, and this doc's status.

## Non-goals

- Rewriting Phase 18. Most of what landed is reusable. This phase is surgical — change the claims that are false and the mechanisms that are cosmetic. Do not redo the SSDF map or the ADR infrastructure from scratch.
- Expanding scope into JA4proxy4. Production governance is not this repo's job.
