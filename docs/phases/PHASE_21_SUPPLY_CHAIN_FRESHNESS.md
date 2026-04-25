# Phase 21 — Supply-chain freshness & post-remediation follow-ups

**Author:** angry reviewer, 2026-04-24
**Context:** Phase 20 (PR #61, #64, #66, #67) closed 13 governance-theatre
defects. Phase 21 collects the follow-up work that Phase 20 *surfaced*
but did not land: monitoring the load-bearing refresh mechanisms, and
sharpening the justifications behind the Trivy allowlist.

Like Phase 18, Phase 21 is decomposable; each sub-item is one small PR.

## 21-B — Digest-pin workflow freshness monitor

**Scope.** New offline CI check `scripts/ci/check_digest_freshness.py`.
Queries the GitHub Actions API for the latest successful run of
`.github/workflows/digest-update.yml`; fails `make test` if the last
success is more than 14 days old (= 2 missed weekly fires).

**Why.** Phase 18-G added a weekly workflow that queries Docker Hub for
the live digest of each pinned image and opens a PR on drift. Phase 20
P0-2 wired the pin file into role 09 as a deploy-time assertion,
giving the file real teeth. But the refresh itself was best-effort —
if the cron was disabled, the PAT expired, or the workflow broke
silently, the pin file would age and the deploy-time assertion would
start blocking deploys against stale digests without any upstream
signal.

21-B converts the "weekly refresh" from best-effort to load-bearing.
A quiet refresh (zero drift, file untouched) still proves the
mechanism is alive; mtime-on-the-file would raise false alarms in
quiet periods. The check uses the workflow's *last-success timestamp*
for exactly this reason.

**Files.**
- `scripts/ci/check_digest_freshness.py` — the new check (14-day
  default ceiling, configurable via `--max-age-days`).
- `Makefile` — new `test-digest-freshness` target; added to the `test`
  target's prerequisite list.
- `docs/phases/PHASE_21_SUPPLY_CHAIN_FRESHNESS.md` — this doc.

**Acceptance.**
- Green workflow, recent run: check prints `✓ digest-update.yml last
  success: Nd ago` and exits 0.
- Green workflow, last run > 14 days ago: check prints the age and
  exits 1 — `make test` goes red.
- Offline / no `gh` on PATH / no repo-slug: check warns and exits 0
  (so the dev loop stays green without GitHub credentials — same
  pattern as `check_workflow_pins.py`). Opt out explicitly via
  `--offline` or `CI_OFFLINE=1`.

**CI hook.** The check itself. In the GitHub Actions `ci` job, `gh`
is authenticated via `GH_TOKEN: ${{ secrets.GITHUB_TOKEN }}` (already
added to the `make test` step for `check_workflow_pins.py` in Phase
20), so the freshness check also gets real API quota in CI.

**Depends on.** Phase 18-G (the workflow to monitor) and Phase 20
P0-2 (which made the pin file load-bearing).

**Not in scope.** Auto-enabling the workflow if it's disabled; that's
a privileged action and belongs to a human response. The check's job
is to *surface* the gap, not paper over it.

## 21-D — Scheduled-workflow enabled-state gate

**Scope.** New offline CI check `scripts/ci/check_workflow_enabled.py`.
Enumerates every workflow under `.github/workflows/` that contains a
top-level `schedule:` key and fails `make test` if any has
`state != "active"` in the GitHub Actions API.

**Why.** 21-B catches the case where a scheduled workflow fires but
produces no successful run in 14 days. It cannot catch two other
silent-failure modes:

1. **GitHub auto-disables scheduled workflows after 60 days of repo
   inactivity** (`state = "disabled_inactivity"`). A workflow whose
   last successful run happened 61 days ago, then got auto-disabled,
   still *reports* a prior success — the freshness gate stays green
   right up until the ceiling bites, by which point the cron hasn't
   fired for two full ceilings.
2. **Semi-annual workflows legitimately have long silent windows.**
   `drill-reminder.yml` is scheduled for April 1 and October 1; a
   180-day ceiling is the earliest the freshness gate could catch a
   problem, and by then the drill has already been missed. The
   enabled-state gate catches a disabled semi-annual workflow the
   moment CI next runs, not after the window lapses.

Together, 21-B and 21-D make the scheduled-workflow layer
load-bearing rather than ceremonial.

**Files.**
- `scripts/ci/check_workflow_enabled.py` — the new check.
- `Makefile` — new `test-workflow-enabled` target; added to the
  `test` prerequisite list.
- `docs/phases/PHASE_21_SUPPLY_CHAIN_FRESHNESS.md` — this section.

**Acceptance.**
- All scheduled workflows active: prints `✓ N scheduled workflow(s)
  all active` and exits 0.
- Any workflow disabled (manually or by inactivity): prints the
  workflow name + observed state and exits 1 — `make test` goes red.
- Offline / no `gh` on PATH / no repo-slug: check warns and exits 0
  (same pattern as `check_digest_freshness.py`).

**Depends on.** Phase 20 P0-1 (branch protection) so a red check
mechanically blocks merge; 18-G, 18-L, 18-E (the three scheduled
workflows this guards).

**Not in scope.** Auto-re-enabling a disabled workflow — that's a
privileged operator action and a defensible escalation gate. The
check's job is to surface the problem, not silently paper over it.

## 21-E — Local-vs-CI parity gate

**Scope.** New offline CI check `scripts/ci/check_local_ci_parity.py`.
Parses `.github/workflows/ci.yml` and `Makefile` + `deploy/Makefile`
+ `scripts/ci/scan_images.sh`; flags any `scripts/ci/*.py` or `trivy
<subcmd>` invocation present in CI but unreachable from `make lint`
/ `make test` / `make scan-images`. Fails `make test` on mismatch.

**Why.** `AGENTS.md` and the `Makefile` header claim `make lint &&
make test` locally is the pre-push contract, and `make lint-all`
"matches CI end-to-end". Before 21-E that was untrue: the `image-scan`
job in `ci.yml` inlined a "Generate compose SBOM" step
(`python3 scripts/ci/render_compose.py --sbom /tmp/…`) and a "Scan
compose SBOM with Trivy" step (`trivy sbom …`), neither of which any
Makefile target invoked. A developer running `make lint-all` locally
passed while CI could still legitimately turn red on the same commit.

This is exactly the Phase-20 defect pattern (shipped gate, no local
parity). 21-E converts the parity claim from aspirational to
mechanical.

**Files.**
- `scripts/ci/check_local_ci_parity.py` — the parity checker.
- `scripts/ci/scan_images.sh` — extended to render the compose SBOM
  and run `trivy sbom` over it with the same severity + allowlist
  rules as the image scan. This restores parity so `make scan-images`
  locally is the same gate as the CI `image-scan` job.
- `.github/workflows/ci.yml` — two inline steps collapsed into the
  single `make scan-images` call. The artifact-upload step remains.
- `Makefile` — new `test-local-ci-parity` target; added to `test`
  prereqs.
- `docs/phases/PHASE_21_SUPPLY_CHAIN_FRESHNESS.md` — this section.

**Acceptance.**
- Any `python3 scripts/ci/X.py` in `ci.yml` that isn't invoked from
  a Makefile recipe: the check fails with the specific script name.
- Any `trivy <subcmd>` in `ci.yml` whose subcmd doesn't also appear
  in the Makefile / `scan_images.sh`: fails with the specific subcmd.
- Clean state (all CI invocations reachable locally): exits 0.

**CI hook.** The check itself; 100% offline (pure text parsing of
two repo files).

**Depends on.** Phase 20 P1-8 (the compose-SBOM scan is what 21-E's
first fix absorbs).

**Not in scope.** The reverse direction (Makefile invocations absent
from CI) — that's a different trade-off and would constrain CI from
legitimately pruning flaky checks. If worth gating, own it as a
separate check.

## 21-F — Tighten existence-only gates in `scripts/ci/check_*.py`

**Scope.** A meta-audit pass over the 51 `scripts/ci/check_*.py`
checkers, looking for the same governance-theatre pattern Phase 20
attacked at the policy layer: a checker whose docstring claims to
verify *behaviour* but whose body only verifies *presence of a string
or file*. This first PR tightens the two clearest offenders.

**Why.** The repo's CI gate is only as load-bearing as its weakest
checker. If `check_blackbox_exporter.py` claims "CertExpiringSoon
rule declared" but actually only confirms the substring appears
*anywhere* in the rules file (including a comment or a different
rule's `expr`), then renaming or deleting the alert leaves the gate
green. Same shape as Phase 20: shipped policy, no enforcement.

**Findings (verified).**
- `check_heartbeat_timer.py:79` — gate detection used
  `"ja4proxy_heartbeat_url" in txt and "length" in txt`. Two
  unrelated substrings would satisfy it (e.g. a `# length: 32`
  comment + an unrelated `ja4proxy_heartbeat_url:` line). Tightened
  to a regex that requires `when: … ja4proxy_heartbeat_url … |
  length` on the same line — the actual gate shape role 06 uses.
- `check_blackbox_exporter.py:88-94` — parsed the rules YAML for
  syntax then fell back to substring matching the raw text for
  `CertExpiringSoon` and `probe_ssl_earliest_cert_expiry`. Tightened
  to walk the parsed `groups → rules` tree, find the alert by
  `alert: CertExpiringSoon`, and confirm `probe_ssl_earliest_cert_
  expiry` is in *that rule's* `expr`.

**Findings considered and rejected.**
- `check_digest_regex.py:75` accepts `0{64}` as a valid hash. This
  is the documented "not pinned yet" sentinel, supported end-to-end
  by role 09's assert (`expected_suffix == sentinel or pulled_suffix
  == expected_suffix`). Allowing it is correct.
- `check_digest_freshness.py:132` (claimed "silent on zero runs"):
  read the code — the `run is None` branch explicitly returns 1 with
  a clear error. The claim was wrong.
- `check_molecule_scenarios.py`, `check_export_timer.py` etc. —
  documented as structural-only or content-trivial. No defect.

**Acceptance.**
- Before this PR: a no-op rename of the heartbeat `when:` clause to
  drop `| length`, or deletion of the CertExpiringSoon alert leaving
  the substring in a comment, would not fail CI. After: both
  perturbations fail. Verified by an in-memory smoke test.
- Current good tree: both checkers still print their success line
  (no false positive introduced).

**CI hook.** None new — same `make test` targets, just stricter.

**Not in scope.** The remaining 47+ checkers were surveyed by an
Explore agent; no other findings rose to "shipped gate that doesn't
gate". Future tightening should follow the same pattern: each finding
gets verified against the actual code before any change lands —
"the agent said so" is not enough.

## 21-A — Reachability-tested CVE justifications (pilot landed)

**Scope.** Each `.trivyignore` entry carries a prose justification
(e.g. "this deployment only configures Prometheus + Loki data
sources, not Postgres"). Today those justifications are asserted,
not tested. 21-A turns them, one CVE at a time, from human prose
into static checks against the configuration that backs them.

**Why.** Post-Phase-20, every allowlist entry has a bounded expiry
and a written reachability argument. The argument is still human-
authored; a CI proof — even a static one — closes the gap between
"we said it's unreachable" and "we show it is", and catches
configuration drift before the prose silently goes stale.

**Static, not live.** The original phase language said "attempt the
exploit path from an external position". That implementation needs
the deployed VM, network access from CI, and per-CVE exploit
machinery — heavy, flaky, VM-coupled. The pilot instead tests the
*configuration that enables reachability*: if the configuration
forbids the precondition, the prose claim survives; if it permits
it, the claim is dead. Cheaper, runs offline, lives in `make test`.
Live probing remains a separate effort if it ever becomes
load-bearing.

**Pilot.** One probe — CVE-2026-33816 (Grafana jackc/pgx Postgres-
driver memory-safety flaw). Allowlist prose claim: "this deployment
only configures Prometheus + Loki data sources … not Postgres". The
probe parses `deploy/templates/grafana-datasources.yml.j2`, walks the
declared datasources, and asserts each one's `type` is in the
expected `{prometheus, loki}` set. Any datasource of type `postgres`
— or *any* type outside the allowlist — fails the check, forcing a
deliberate decision (remove the datasource, drop the CVE from
`.trivyignore`, or extend the probe to re-justify).

**Files.**
- `scripts/ci/check_cve_reachability.py` — the probe registry. One
  function per CVE; the pilot ships with `probe_cve_2026_33816`.
  Structured so additional CVEs land as one-function PRs.
- `Makefile` — new `test-cve-reachability` target; added to `test`
  prereqs.
- `docs/phases/PHASE_21_SUPPLY_CHAIN_FRESHNESS.md` — this section.

**Acceptance.**
- Current good tree: probe prints `✓ 1 CVE reachability claim(s)
  still hold: CVE-2026-33816` and exits 0.
- A drifted Grafana provisioning that adds a `postgres` datasource:
  probe fails with the specific CVE ID and the new datasource type.
  Verified by an in-memory smoke test.
- A drifted provisioning with an unrelated new datasource (`mysql`):
  probe fails on the allowlist-semantics check, surfacing that the
  claim now needs re-justification.

**Not in scope (this PR).**
- The other three CRITICAL entries (CVE-2026-30836 / 33186 caddy
  cert path; CVE-2025-68121 blackbox MITM-on-probe-path;
  CVE-2026-31789 OpenSSL 32-bit overflow). Each gets its own one-
  function follow-up — the framework is the load-bearing part of
  the pilot, not the count of CVEs covered.
- Live network probes. See "Static, not live" above.

**Depends on.** None — pure offline static check.

## 21-C — End-to-end VM verify pass (blocked)

**Scope.** Run `make deploy` + `make verify` + `make go-live` against
a fresh Alibaba VM and capture the full output. Phase 20's P0-2 wired
role 09 into the deploy play; a live run is needed to prove the
assertion fires cleanly against real Docker Hub digests.

**Status.** Blocked on VM availability. The offline checks are all
green; the live rehearsal is operator work.

## Tracking

- [x] 21-B — digest-pin workflow freshness monitor (PR #68)
- [x] 21-D — scheduled-workflow enabled-state gate (PR #69)
- [x] 21-E — local-vs-CI parity gate (PR #70)
- [x] 21-F — tighten existence-only gates in scripts/ci/check_*.py (PR #71)
- [x] 21-A — reachability-tested CVE justifications, pilot probe (PR #TBD)
- [ ] 21-A — extend probes to remaining 3 CRITICAL `.trivyignore` entries
- [ ] 21-C — end-to-end VM verify pass (blocked on VM)
