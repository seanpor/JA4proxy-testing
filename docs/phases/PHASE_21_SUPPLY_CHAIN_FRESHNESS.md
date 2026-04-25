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

## 21-G — Probe-coverage invariant for CRITICAL `.trivyignore` entries

**Scope.** A new gate inside `check_cve_reachability.py` that fails
`make test` if any CRITICAL `.trivyignore` entry has no probe in the
registry. Today the linkage between an entry and its probe is by
convention; 21-G makes it a mechanical invariant.

**Why.** With 21-A's four probes shipped (PRs #72-#75), the registry
covers every CRITICAL entry that exists *today*. But "today" is
brittle: if a new CRITICAL CVE is added to the allowlist next month
and no one remembers to register a probe, the allowlist regrows the
exact governance-theatre defect 21-A was meant to close — a
shipped justification that nothing tests. 21-G turns "remember to
add a probe" from a checklist item into a CI failure.

**Files.**
- `scripts/ci/check_cve_reachability.py`:
  - new `_critical_cves_in_trivyignore()` parser. Severity is
    determined by (1) explicit `(CRITICAL)` annotation in any
    preceding comment (handles the `=== CRITICAL + HIGHs ===`
    mixed-severity OpenSSL block), or (2) the most recent
    `=== CRITICALs ===` section header.
  - new `_registry_coverage()` that introspects each probe's
    docstring lead-in for declared CVE IDs.
  - `main()` runs the coverage check before any individual probe,
    so a missing probe surfaces even when every existing probe is
    green.
- `docs/phases/PHASE_21_SUPPLY_CHAIN_FRESHNESS.md` — this section.

**Acceptance.**
- Current good tree: `✓ 5 CVE reachability claim(s) still hold
  (covers all 5 CRITICAL .trivyignore entries): …`. Exit 0.
- A new uncovered CRITICAL CVE added to `.trivyignore`: probe
  registry fails with "CVE-XXXX-YYY: CRITICAL .trivyignore entry
  has no reachability probe in this registry. Add a probe…". Exit 1.
- Smoke-tested: removing the caddy probe surfaces both
  CVE-2026-30836 and CVE-2026-33186 as uncovered.

**Not in scope.** HIGH-severity entries. The response-time policy
(decision in 30 days, fix in 90) and the much higher volume of
HIGHs make probe-per-HIGH a poor cost trade. If a HIGH ever needs
the same treatment it can declare itself CRITICAL via an explicit
annotation, or 21-G's classifier can be extended.

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

## 21-H — Severity-aware expiry-ceiling gate

**Scope.** Codify the `.trivyignore` policy header — "CRITICAL → fix
within 30 days, HIGH → fix within 90 days" — into a mechanical gate
inside `check_image_scan.py`. Today the header is aspirational prose;
nothing stops a contributor from setting `# expires:` 18 months out
on a CRITICAL entry and silently widening the policy. 21-H makes that
edit fail `make test`.

**Why.** 20-P0-1 added the expiry convention and the not-yet-expired
check; 21-G locked in probe coverage for every CRITICAL entry. Both
treat *every entry* the same, regardless of severity. A 400-day
expiry on a CRITICAL is no longer a CRITICAL response — it's a HIGH
response with a CRITICAL label. The header pretends otherwise; 21-H
stops the pretence by failing CI when the window-to-today exceeds the
severity-tier ceiling.

**Files.**
- `scripts/ci/_trivyignore.py` — new shared severity classifier
  (`classify(text) -> dict[CVE, severity]`). Pure function over the
  file's text; consumers do their own I/O. Extracted from 21-G's
  parser so `check_cve_reachability.py` and `check_image_scan.py`
  cannot drift on a borderline classification.
- `scripts/ci/check_cve_reachability.py` — refactored to import the
  shared classifier; ~40 lines of duplicated parser logic deleted.
- `scripts/ci/check_image_scan.py`:
  - new `SEVERITY_MAX_DAYS = {"CRITICAL": 30, "HIGH": 90}`
    constant, sourced directly from the `.trivyignore` policy header.
  - extended `check_trivyignore()` to compute window-to-today on
    every non-expired entry and fail when it exceeds the severity
    ceiling. UNKNOWN-severity entries are skipped (the classifier
    returns UNKNOWN only for CVEs in mixed-severity sections without
    an explicit `(SEV)` annotation, which is itself a documentation
    defect but not the one this gate targets).
- `docs/phases/PHASE_21_SUPPLY_CHAIN_FRESHNESS.md` — this section.

**Acceptance.**
- Current good tree: every active entry's expiry is within its
  severity ceiling; `check_trivyignore()` prints its existing success
  line and exits 0.
- Synthetic drift: a CRITICAL entry with `# expires:` 251 days out
  fails with "(CRITICAL) expires … 251d away, beyond the 30d
  CRITICAL ceiling. … tighten the expiry, fix the CVE, or amend the
  policy." Same shape for HIGH at 1347 days vs the 90d ceiling.
- Boundary behavior: CRITICAL at exactly 30d and HIGH at exactly 90d
  both pass (the gate is `>`, not `>=`).
- Smoke-tested in-process before commit; `make lint` + `make test`
  both green.

**Not in scope.**
- Auto-tightening expiries on existing entries — that's a policy
  decision, not a mechanical fix.
- A separate "policy header parser" that reads the ceiling out of
  the `.trivyignore` comment header. The constant lives in code with
  a comment pointing back at the header; if the header ever changes,
  the constant moves with it. One source of truth, written twice on
  purpose so a header edit cannot silently retune the gate.

**Depends on.** 21-G (which introduced the per-CVE severity
classifier this PR extracts and shares).

## 21-I — Orphan-check gate

**Scope.** Fail `make test` if any `scripts/ci/check_*.py` file
exists on disk but is not invoked transitively by `make test` or
`make lint`. Closes the symmetric gap from 21-E.

**Why.** 21-E ensures CI runs nothing the local pre-push contract
can't reproduce. The reverse direction was open: a contributor adds
`check_new_thing.py`, forgets to add `test-new-thing` to the
Makefile, and the check ships dead. The angry reviewer reads the
filename in the tree and assumes it gates something; CI runs forever
without it. Today every check_*.py happens to be wired (verified
during this PR's audit — 53/53 files reachable). 21-I makes the
property mechanical so it doesn't quietly stop being true.

**Files.**
- `scripts/ci/check_orphaned_ci_scripts.py` — new check. Lists
  every `scripts/ci/check_*.py`, asks `make -n test` and `make -n
  lint` for the authoritative dry-run command surface, diffs.
  Falls back to a warning + exit 0 if `make` is not on PATH (mirrors
  21-B's `gh` fallback so a bare-checkout dev loop stays green).
- `Makefile` — new `test-orphaned-ci-scripts` target; added to the
  `test` prerequisite chain and to `.PHONY`.
- `docs/phases/PHASE_21_SUPPLY_CHAIN_FRESHNESS.md` — this section.

**Why dry-run, not regex.** A regex over the Makefile's text would
match a check that's mentioned but not actually invoked from `test`
(e.g. defined inside a target nothing requires). `make -n` traces
real prereq chains, including targets defined in `deploy/Makefile`,
so the gate's claim ("invoked by `make test`") is what it actually
checks.

**Acceptance.**
- Current good tree: prints `✓ orphan-check gate: 53 check_*.py
  file(s), all invoked from \`make test\`/\`make lint\``. Exit 0.
- Synthetic orphan: dropping a stub `check_synthetic_orphan.py` into
  `scripts/ci/` (without wiring it) trips the gate and lists the
  orphan with the remediation hint. Verified in-session before this
  PR.
- The check itself is wired only via the Makefile, so 21-I gates
  itself.

**Not in scope.** A unit-test-style gate (e.g. "every check has at
least one negative-case fixture"). That's a much bigger lift and
slides into the test-quality territory rather than the CI-plumbing
territory 21-I targets.

**Depends on.** 21-E (sibling concept; this is the reverse arrow).

## 21-J — Refuse UNKNOWN-severity .trivyignore entries

**Scope.** Fail `check_trivyignore` if any active CVE classifies as
`UNKNOWN` under `_trivyignore.classify()`.

**Why.** 21-G's coverage gate (CRITICAL must have a probe) and 21-H's
ceiling gate (CRITICAL≤30d, HIGH≤90d) both filter on severity. An
entry that the classifier returns `UNKNOWN` for — i.e. a CVE that
sits outside any `=== CRITICALs ===` / `=== HIGHs ===` header AND
without an inline `(CRITICAL)` / `(HIGH)` annotation — silently
bypasses both gates. Verified in-session: a CVE pasted at the top of
`.trivyignore` (before any header) classifies UNKNOWN, ships into
the allowlist, and neither 21-G nor 21-H complains.

The classifier deliberately returns UNKNOWN as a "caller decides how
strict to be" signal. 21-H chose to skip; 21-J chooses to refuse.
With both gates in place, "UNKNOWN" stops being an escape hatch.

**Files.**
- `scripts/ci/check_image_scan.py` — extends `check_trivyignore()`
  to error out when `severity == "UNKNOWN"` for an active entry,
  with a remediation hint pointing the contributor at the right
  section header or the inline `(SEV)` annotation.
- `docs/phases/PHASE_21_SUPPLY_CHAIN_FRESHNESS.md` — this section.

**Acceptance.**
- Current good tree (24 active entries, 0 UNKNOWN): unchanged. Same
  success line.
- Synthetic drift: a CVE inserted before any section header (no
  annotation) trips the gate with the file:line, the CVE ID, and
  the explicit "place under right section header or annotate inline"
  remediation. Verified in-session.

**Not in scope.** Extending the classifier with more severity tiers
(MEDIUM, LOW). Trivy's image scan only blocks on HIGH+CRITICAL today;
adding more tiers would require a policy decision about whether to
track them at all.

**Depends on.** 21-G (introduced the classifier) and 21-H
(extracted it into `_trivyignore.py`).

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
- [x] 21-A — reachability-tested CVE justifications, pilot probe (PR #72)
- [x] 21-A — probe for CVE-2026-31789 (Grafana OpenSSL 32-bit) (PR #73)
- [x] 21-A — probe for CVE-2025-68121 (blackbox MITM-on-probe-path) (PR #74)
- [x] 21-A — probe for CVE-2026-30836/33186 (caddy not on public path) (PR #75)
- [x] 21-G — probe-coverage invariant for CRITICAL .trivyignore (PR #76)
- [x] 21-H — severity-aware expiry-ceiling gate (PR #77)
- [x] 21-I — orphan-check gate for scripts/ci/check_*.py (PR #79)
- [x] 21-J — refuse UNKNOWN-severity .trivyignore entries (PR #TBD)
- [ ] 21-C — end-to-end VM verify pass (blocked on VM)
