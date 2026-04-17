# Phase 18 — SWEBOK & industry best-practice gap closure

Last reviewed: 2026-04-16

A SWEBOK v4 walkthrough (plus NIST SSDF, SLSA, OpenSSF Scorecard, and
CIS) identified a small number of real gaps left after Phases 14–17.
This phase closes them. Each chunk is sized for one PR, same shape as
`GOVERNANCE_ROADMAP.md` chunks: Scope / Why / Files / Acceptance / CI
hook / Depends on / Not in scope.

Ordering:

```
18-A → 18-B                           (supply chain: SBOM + vuln scan)
18-C → 18-D                           (supply chain: SLSA L2 provenance)
18-E                                  (OpenSSF Scorecard)
18-F → 18-G                           (automated dep updates)
18-H                                  (requirements traceability)
18-I                                  (ADR log)
18-J                                  (CIS benchmark scoring on the VM)
18-K                                  (NIST SSDF mapping — docs only)
18-L                                  (runbook drill cadence)
```

---

## 18-A — SBOM for the Go binary and compose stack

**Scope.** Generate a CycloneDX SBOM for the JA4proxy Go binary during
role `02-artifact-build`, and a second SBOM enumerating the pinned
container image digests rendered from `docker-compose.yml.j2`. Ship
both with the deploy artifact set.

**Why.** SWEBOK §Configuration Management and NIST SSDF PS.3.2 both
expect a machine-readable component inventory. Digest pins prove *what*
is deployed; an SBOM lets a future reader answer *which CVE touches
us* without re-deriving the list.

**Files.**
- `deploy/roles/02-artifact-build/tasks/build.yml` — invoke
  `cyclonedx-gomod` (or `syft`) against the built binary, emit
  `ja4proxy.cdx.json` alongside the binary.
- `scripts/ci/render_compose.py` — extend to also emit a
  `compose.cdx.json` listing each image with its pinned digest.
- `deploy/.gitignore` — ignore the rendered SBOMs; they are build
  outputs.

**Acceptance.**
- `make test` renders both SBOMs to a temp dir; jq assertions confirm
  each contains a `components` array with ≥1 entry per expected image.
- A deliberately unpinned image in the compose template causes the
  SBOM render step to fail.

**CI hook.** New `scripts/ci/check_sbom.py`: run the two SBOM emitters
against fixtures, assert schema validity (CycloneDX 1.5) and
non-empty component list.

**Depends on.** Nothing (14-A/B/C already nail the inputs).

**Not in scope.** Signing the SBOM (that's 18-D). Publishing SBOM to
an external store.

---

## 18-B — Container image vulnerability scan in CI

**Scope.** Run Trivy (or Grype) against every pinned image digest in
the rendered compose file on every PR. Fail on HIGH/CRITICAL
vulnerabilities with available fixes.

**Why.** SWEBOK §Software Security and NIST SSDF RV.1.1 ("identify and
confirm vulnerabilities on an ongoing basis") want active CVE
awareness. Pinning digests without scanning them means you find out
about a CVE when someone asks.

**Files.**
- `.github/workflows/ci.yml` — new `image-scan` job that renders the
  compose file, extracts image digests, runs Trivy per image.
- `scripts/ci/scan_images.sh` — wrapper so local `make scan-images`
  works the same way.
- `Makefile` — add `scan-images` phony target.

**Acceptance.**
- Adding a known-vulnerable tag temporarily (e.g. an old `redis:6`
  image) causes the job to fail with the CVE ids printed.
- The job runs in under 3 minutes with Trivy's CI cache.

**CI hook.** The job itself is the check. No offline-fixture needed —
Trivy is the tool.

**Depends on.** 18-A (uses the rendered compose digest list).

**Not in scope.** OS-package scanning on the VM itself (that's 18-J).
Scanning the Go binary for embedded CVEs (`govulncheck` — see 18-G).

### 18-B landing notes (2026-04)

Landed with two passes:

- **CRITICAL** — blocking. `.trivyignore` at the repo root acts as a
  short-lived allowlist. Every entry is gated by a
  `# expires: YYYY-MM-DD` comment; `scripts/ci/check_image_scan.py`
  fails the offline check if any entry is expired or lacks an expiry,
  forcing a re-decision at each deadline.
- **HIGH** — informational. Printed by the scan but does not fail the
  build. Tightening this is chunk 18-B-2 below.

Initial allowlist (all expire 2026-05-17, ~30 days from 18-B land).
The list is the *union* of CRITICAL findings observed across CI runs
— Trivy's DB refreshes and several of our images use floating tags
(`:latest`, `:2-alpine`, `:7-alpine`) so the specific CVE set flaps
day-to-day. Listing the union prevents a red-green coin flip.

- `CVE-2023-24538` and `CVE-2023-24540` — Go `html/template` flaws in
  `redis:7-alpine` (upstream base pins Go 1.18.2). Mitigation: move
  to `redis:7.4-alpine` or `redis:8-alpine`.
- `CVE-2026-30836` (`smallstep/certificates`) and `CVE-2026-33186`
  (`grpc-go`) — in `caddy:2-alpine`. Caddy's cert handling and gRPC
  surface are not on the public path (HAProxy terminates TLS as
  passthrough; Caddy only serves the static honeypot after
  JA4proxy). Fixes require upstream caddy image refresh.
- `CVE-2025-68121` — Go `crypto/tls` certificate validation flaw in
  `prom/blackbox-exporter:latest` (Go 1.25.5 stdlib in the shipped
  binary, fixed in 1.24.13 / 1.25.7). Blackbox probes known targets
  over HTTPS from the monitoring network; exploit requires MITM
  position on the probe path. Awaiting upstream image refresh.

## 18-B-2 — Tighten HIGH image-scan findings to blocking

**Scope.** Flip the HIGH Trivy pass from `--exit-code 0` (informational)
to `--exit-code 1` (blocking) once the current backlog of upstream
image refreshes has landed and `.trivyignore` covers any residual
HIGHs with justified expiries.

**Why.** The PHASE_18 acceptance matrix treats HIGH as a 30-day
decision window. An advisory gate that nothing enforces silently
decays; the two-pass split is a staging area, not a permanent
posture.

**Files.**
- `scripts/ci/scan_images.sh` — change the HIGH pass to
  `--exit-code 1` and merge it with the CRITICAL pass (one loop,
  `--severity HIGH,CRITICAL`) once the backlog clears.
- `scripts/ci/check_image_scan.py` — assert the wrapper blocks on
  HIGH; remove the `HIGH informational` check line.
- `.trivyignore` — audit remaining entries; drop any that are fixed
  upstream, refresh expiries on the rest.

**Acceptance.** CI's `image-scan` job fails on a fixable HIGH
against any pinned image unless it's explicitly allowlisted with a
valid future expiry.

**Depends on.** 18-B (this section).

**Not in scope.** Changing the severity model itself — we stay on
HIGH/CRITICAL with `--ignore-unfixed`.

---

## 18-C — govulncheck in CI against the Go source

**Scope.** Run `govulncheck ./...` against the JA4proxy sibling Go
checkout as part of `02-artifact-build` when `ja4proxy_build_machine_go_path`
is set. Fail deploy if a known vuln is reachable.

**Why.** SSDF RV.1.1 again, and SLSA L2's "build integrity" implies
you at least *know* you shipped a clean binary.

**Files.**
- `deploy/roles/02-artifact-build/tasks/build.yml` — add a
  `govulncheck` step gated on binary of the same name being on
  `$PATH`; skip with a warning if absent (ops may be on an air-gapped
  build host).
- `AGENTS.md` — one line: install govulncheck as part of
  `lint-install`.

**Acceptance.** A module with a known reachable advisory fails the
build with the advisory id and call-site. Skipping when govulncheck
is missing prints a loud `WARN` but does not fail.

**CI hook.** `scripts/ci/check_govulncheck_wired.py` — assert the
build task references `govulncheck` by name.

**Depends on.** Nothing.

**Not in scope.** Enforcing govulncheck in GitHub Actions (the build
happens outside CI; CI only renders Ansible).

---

## 18-D — Signed SLSA provenance for the binary

**Scope.** After 18-A, sign the emitted SBOM and a SLSA v1.0
provenance statement with `cosign sign-blob` (keyless via OIDC when
building in CI, key-based for local builds). Verify on deploy.

**Why.** SLSA L2 requires signed provenance from the build system.
Today the expected-sha256 pin proves the operator matched a known
hash, but not *who* built it or *how*. Signed provenance closes that.

**Files.**
- `deploy/roles/02-artifact-build/tasks/build.yml` — cosign sign-blob
  the binary + SBOM; emit `.sig` and `.pem` next to the artefacts.
- `deploy/roles/03-ja4proxy-deploy/tasks/main.yml` — verify the
  signature against a pinned public key (or the Rekor log) before
  installing the binary.
- `deploy/inventory/group_vars/all.yml` — new var
  `ja4proxy_cosign_public_key_path` (nullable; when unset, 18-D is
  a no-op).

**Acceptance.** Tampering with the binary after signing but before
deploy causes the deploy to abort. Setting the public-key var to a
wrong key also aborts. Unset key = warn + continue (so this is opt-in
while bootstrapping).

**CI hook.** `scripts/ci/check_cosign_wired.py` — assert both tasks
reference cosign and both honour the nullable var consistently.

**Depends on.** 18-A.

**Not in scope.** Keyless signing via GitHub OIDC (requires moving
the build into CI — separate phase).

---

## 18-E — OpenSSF Scorecard workflow

**Scope.** Add the official OpenSSF Scorecard workflow to
`.github/workflows/scorecard.yml`. Publish the badge in `README.md`.

**Why.** Scorecard is a cheap sanity check on repo-level hygiene —
token permissions, pinned-actions, dangerous-workflow, signed
releases. Several checks we already pass; a couple we don't and
should.

**Files.**
- `.github/workflows/scorecard.yml` — the upstream template, pinned
  by SHA.
- `README.md` — a badge under the title.
- `.github/workflows/ci.yml` — audit for unpinned action versions
  (most already pinned; fix the stragglers here).

**Acceptance.** First run produces a score; every subsequent PR that
would regress the score is caught before merge. A score floor (e.g.
7/10) is enforced via a follow-up job that fails if the JSON output
reports a lower number.

**CI hook.** The Scorecard workflow is the check.

**Depends on.** Nothing.

**Not in scope.** Chasing every Scorecard recommendation to 10/10 —
some (e.g. fuzzing) don't fit an Ansible repo.

---

## 18-F — Dependabot for Python dev deps

**Scope.** Turn on Dependabot for `requirements-dev.txt` and
`.github/workflows/*`.

**Why.** SWEBOK §Maintenance expects a known mechanism for tracking
dependency changes. Today `requirements-dev.txt` is manually pinned,
which is correct for reproducibility but invisible when a CVE drops.

**Files.**
- `.github/dependabot.yml` — two update ecosystems (`pip`,
  `github-actions`), weekly schedule, auto-assign to the default
  reviewer.

**Acceptance.** Dependabot opens its first PR against a stale pin
within a week of merge. PR goes through the same `lint-and-test`
gate as any human PR.

**CI hook.** None needed; the config is declarative.

**Depends on.** 18-E (so Scorecard's `Dependency-Update-Tool` check
goes green).

**Not in scope.** Automating Docker-image digest bumps (see 18-G).

---

## 18-G — Automated container digest updates

**Scope.** Script that, for each image in `docker-compose.yml.j2`,
queries the registry for the latest tag-within-series digest and
opens a PR bumping the pin. Runnable locally *or* on a weekly
scheduled workflow.

**Why.** Digest pinning is static by design. Without an update path,
pinned digests silently rot — every month that passes, the pinned
Redis is one more month of un-applied CVE fixes.

**Files.**
- `scripts/ci/update_digests.py` — resolves each `image: "name:tag@sha256:..."`
  by querying the registry for the current digest of `name:tag`.
- `.github/workflows/digest-update.yml` — weekly scheduled job that
  runs the script and opens a PR if anything changed.
- `Makefile` — `update-digests` phony target.

**Acceptance.** Manually rewriting a template digest to an older one
and running `make update-digests` produces a diff bumping it back.
The scheduled workflow opens one PR per week max.

**CI hook.** `scripts/ci/check_digest_regex.py` already validates the
format; extend it to assert the script's output still parses.

**Depends on.** 18-B (so the bump-PR runs the vuln scan on the new
digest before a human reviews it).

**Not in scope.** Auto-merging digest bumps. Human review stays in
the loop.

---

## 18-H — Requirements & traceability document

**Scope.** Add `docs/REQUIREMENTS.md` with numbered functional (F-*)
and non-functional (NF-*) requirements, each tagged with the phase
doc, role, or CI check that satisfies it.

**Why.** SWEBOK §Requirements expects an explicit artefact. Today the
requirements are implicit in README + phase docs. A junior engineer
asked "why does the dial default to 0?" cannot answer from the code
alone. Traceability also makes gaps visible (e.g. no requirement
currently mandates log retention of ≥ N days — just a config).

**Files.**
- `docs/REQUIREMENTS.md` — initial set: ~15 requirements covering
  dial-default, monitor-first, no-PII, retention, staged go-live,
  binary provenance, data-lifecycle, legal disclosures. Each entry
  cites its satisfier (`deploy/roles/...`, `scripts/ci/...`, or a
  phase doc).
- `scripts/ci/check_requirements_traceability.py` — parse the table,
  assert every cited file exists.

**Acceptance.** Renaming a cited role or check without updating the
table causes `make test` to fail. Every F-* and NF-* has a satisfier.

**CI hook.** The new check.

**Depends on.** Nothing.

**Not in scope.** Upstream capture of stakeholder needs (out of
scope for a single-person research project).

---

## 18-I — Architecture Decision Record (ADR) log

**Scope.** Convert `PHASE_00_OVERVIEW.md`'s "Design Decisions" table
into numbered ADRs under `docs/adr/`, Nygard-style (Title / Status /
Context / Decision / Consequences). One ADR per current row; future
decisions get a new ADR rather than an edit in place.

**Why.** A table can be mutated; an ADR log is append-only and makes
the decision history inspectable. SWEBOK §Models & Methods and
§Process both endorse append-only decision logs.

**Files.**
- `docs/adr/0001-no-build-tools-on-server.md` ... `0007-no-external-threat-intel.md`.
- `docs/adr/README.md` — index + instructions ("copy 0000-template.md").
- `docs/adr/0000-template.md` — the template.
- `PHASE_00_OVERVIEW.md` — replace the table with a link to
  `docs/adr/`.

**Acceptance.** Each ADR is ≤1 page, has all five Nygard headings,
and references the roles/templates that encode the decision.

**CI hook.** `scripts/ci/check_adr_format.py` — assert every
`docs/adr/*.md` has the five headings and a `Status:` line with a
known value.

**Depends on.** Nothing.

**Not in scope.** Retro-writing ADRs for decisions *not* already in
the overview table.

---

## 18-J — CIS Ubuntu 22.04 benchmark scoring

**Scope.** Install `lynis` on the target VM via role
`01-vm-provisioning`, add a scheduled systemd timer that runs
`lynis audit system --cronjob` weekly, export the score to
node_exporter's textfile collector so Prometheus/Grafana can track
it over time.

**Why.** PHASE_08 already hardens the VM against a STRIDE model, but
there is no *score*. CIS / Lynis gives an external, comparable number
and catches regressions (e.g. a future role accidentally loosening
`sshd_config`).

**Files.**
- `deploy/roles/01-vm-provisioning/tasks/main.yml` — install lynis.
- `deploy/templates/lynis-weekly.timer.j2` / `.service.j2`.
- `deploy/templates/lynis-textfile-export.sh.j2` — parses report,
  emits `lynis_score`, `lynis_warnings_total`, `lynis_suggestions_total`.
- Grafana panel addition for the score trend.

**Acceptance.** `curl localhost:9100/metrics | grep lynis_score`
returns a number 0–100 after the first timer fire. Score floor
(e.g. ≥ 70) enforced by a Prometheus alert, not CI.

**CI hook.** `scripts/ci/check_systemd_units.py` already validates
unit/timer pairs; it will pick up the new ones automatically.

**Depends on.** Nothing.

**Not in scope.** Running CIS remediation automatically — surface
the score, let a human decide.

---

## 18-K — NIST SSDF control mapping (docs only)

**Scope.** Add `docs/COMPLIANCE_SSDF.md`: a table from SSDF
Practice+Task (e.g. PS.1.1, PW.4.1, RV.1.1) to the role / CI
check / phase doc that implements it, plus an explicit "N/A because X"
for tasks that don't apply.

**Why.** Makes future compliance questions ("are you SSDF-aligned?")
answerable with a link instead of an essay. Also flags genuine gaps
early — the exercise of writing the table tends to surface one or
two missing controls.

**Files.**
- `docs/COMPLIANCE_SSDF.md`.
- `scripts/ci/check_governance_docs.py` — extend to assert the file
  exists and every cited path resolves.

**Acceptance.** Every SSDF task from the current spec has a row.
Rows marked "Not yet" link to a tracking issue.

**CI hook.** The extended check.

**Depends on.** 18-A through 18-G (so most "Yes" rows are true).

**Not in scope.** SLSA, FedRAMP, ISO 27001 — separate efforts if ever
needed.

---

## 18-L — Runbook drill cadence

**Scope.** Add a `runbook-drill` checklist item to
`docs/phases/RUNBOOK.md` with a 6-monthly cadence, plus a recurring
GitHub issue template that pre-fills the drill scenarios
(compromised VM, cert near expiry, Loki disk full, abuse complaint,
secrets leak).

**Why.** PHASE_15 wrote the IR playbooks; nobody has executed them
end-to-end. SWEBOK §Operations and NIST IR.4 both expect
*exercised* playbooks, not just written ones.

**Files.**
- `docs/phases/RUNBOOK.md` — new "Drill cadence" section.
- `.github/ISSUE_TEMPLATE/runbook-drill.md` — the checklist.
- `scripts/ci/check_runbook_scenarios.py` — already exists; extend to
  assert the drill checklist links to every scenario by name.

**Acceptance.** Opening a drill issue produces a filled-in checklist
with one checkbox per IR scenario; merging any new IR scenario into
the runbook without updating the template fails `make test`.

**CI hook.** The extended check.

**Depends on.** Nothing.

**Not in scope.** Automating the drills (they are deliberately
human).

---

## Deferred (noted, not in this phase)

- **SLSA L3 hermetic builds** — requires moving the Go build into a
  reproducible CI runner; meaningful but large.
- **Keyless cosign via GitHub OIDC** — same dependency as above.
- **DORA metrics instrumentation** — overkill for a single-VM research
  deploy; revisit if there are ever multiple environments.
- **ISO/IEC 25010 quality-in-use mapping** — documentation effort with
  unclear payoff for this scope.
- **OWASP ASVS pass on the honeypot + privacy pages** — pages are
  static; re-examine if they become interactive.
- **Fuzzing the Go binary** — belongs upstream in the JA4proxy repo,
  not here.

---

## Status

<!-- Append as chunks land. -->
