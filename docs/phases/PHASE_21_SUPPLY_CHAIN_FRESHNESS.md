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

## 21-A — Reachability-tested CVE justifications (proposed, not started)

**Scope.** Each `.trivyignore` entry carries a prose justification
(e.g. "Caddy's cert-handling path is not on our public path"). Today
those justifications are asserted, not tested. 21-A would add a
smoke-test job that, for each CRITICAL entry, attempts the exploit
path from an external position and asserts it fails — turning the
prose into an automated claim.

**Why.** Post-Phase-20, every allowlist entry has a bounded expiry
and a written reachability argument. The argument is still human-
authored; a CI proof for the CRITICAL-class entries would close the
remaining gap between "we said it's unreachable" and "we show it is".

**Status.** Not started. Scoped here so it isn't lost.

## 21-C — End-to-end VM verify pass (blocked)

**Scope.** Run `make deploy` + `make verify` + `make go-live` against
a fresh Alibaba VM and capture the full output. Phase 20's P0-2 wired
role 09 into the deploy play; a live run is needed to prove the
assertion fires cleanly against real Docker Hub digests.

**Status.** Blocked on VM availability. The offline checks are all
green; the live rehearsal is operator work.

## Tracking

- [x] 21-B — digest-pin workflow freshness monitor (PR #TBD)
- [ ] 21-A — reachability-tested CVE justifications (proposed)
- [ ] 21-C — end-to-end VM verify pass (blocked on VM)
