# Governance roadmap — PHASE_11–15 + threat model

Turns `CRITICAL_REVIEW.md` §C1–C6 and `PHASE_11`–`PHASE_15` into a flat
list of small, independently-mergeable chunks. Each chunk is sized for
**one PR, one junior engineer, a few hours end-to-end**.

This document is the working checklist. Tick chunks off as they land on
`main`. The source phase docs remain the normative spec; this file is
the delivery plan.

## How to work a chunk

Standard loop per chunk, same as A1–A9 and the lint/test build-out:

1. **TDD test** — add or extend a check under `scripts/ci/` (or a unit
   test) that fails *before* the change and passes *after*. If the
   invariant can't be checked offline, say so explicitly in the PR.
2. **Doc** — update the relevant `docs/phases/PHASE_NN_*.md` file and
   any affected runbook / README section. If the chunk only adds docs,
   this *is* the deliverable.
3. **Code** — implement the smallest change that makes the test pass.
4. **QA** — `make lint && make test` green locally; `gh pr create`;
   wait for the `ci` workflow to go green on the PR commit.
5. **Critical review** — re-read the diff as if you were reviewing
   someone else's PR. Ask: does this actually enforce the invariant,
   or does it only *declare* it? If the latter, stop and widen the test.
6. **Merge** — watch `ci` on the post-merge `main` commit. Green = done.
   Red = P0: revert or fix-forward immediately.

## Ordering

The chunks are grouped and sequenced so earlier work makes later work
safer. Do them in this order unless you have a reason:

```
14-A → 14-B → 14-C → 14-D → 14-E        (finish the CI safety net)
13-A → 13-B → 13-C                       (retention — enforce what docs claim)
11-A → 11-B → 11-C → 11-D → 11-E         (legal/ethics — pre-req for any go-live)
13-D → 13-E → 13-F                       (alerting)
13-G → 13-H                              (cert/DNS preflight)
13-I → 13-J → 13-K                       (operational hygiene)
12-A → 12-B → 12-C → 12-D                (data export)
15-A → 15-B → 15-C → 15-D                (incident response)
TM-A                                     (threat model)
```

## Chunk template

Every chunk below follows the same shape:

- **Scope** — one or two sentences on what changes.
- **Why** — what invariant this enforces, or what risk it retires.
- **Files** — the paths a junior should expect to touch.
- **Acceptance** — observable post-conditions. These are the TDD target.
- **CI hook** — the offline check to add or extend. If none is
  possible, note it and explain what would detect regression.
- **Depends on** — earlier chunks that must land first.
- **Not in scope** — explicit non-goals so the PR stays small.

---

# Phase 14 — Finish the CI safety net

Purpose: every chunk after this one relies on `make lint && make test`
catching regressions offline. Close the remaining gaps before spending
time on new features.

## 14-A — Go build hygiene (`-trimpath -buildvcs=true`)

**Scope.** Add `-trimpath -buildvcs=true` to the `go build` invocation
in role `02-artifact-build` so the emitted binary carries reproducible
build info queryable via `go version -m`.

**Why.** Without these, the binary embeds local paths and no VCS
revision, so we cannot later answer "which commit emitted this
fingerprint?" — which `PHASE_12 §4` (binary provenance) depends on.

**Files.**
- `deploy/roles/02-artifact-build/tasks/build.yml` — extend the existing
  `go build` command.
- `deploy/roles/02-artifact-build/defaults/main.yml` — introduce
  `ja4proxy_go_build_flags: "-trimpath -buildvcs=true"` so ops can
  override in one place.

**Acceptance.**
- Deployed binary: `go version -m /opt/ja4proxy/bin/ja4proxy` prints a
  `build` section containing `-trimpath=true` and `vcs.revision=<sha>`.
- Existing A8 checksum assertion still passes (checksum changes, but
  source-side and target-side still match).

**CI hook.** New `scripts/ci/check_go_build_flags.py`. Parse
`build.yml`, find the `go build` command, assert the tokens `-trimpath`
and `-buildvcs=true` are present. Fail loudly with the file + line.

**Depends on.** Nothing.

**Not in scope.** Changing `GOFLAGS` env var handling; full reproducible
build (needs pinned toolchain too).

## 14-B — Pinned prebuilt binary sha256

**Scope.** For the prebuilt-binary flow, maintain an expected checksum
in-repo and assert the supplied binary matches.

**Why.** A8 added source↔target checksum verification, which proves the
copy was not corrupted. It does **not** prove the operator handed the
playbook the *right* binary. A known-good hash closes that gap.

**Files.**
- `deploy/expected-binary-sha256.txt` — new file, one line:
  `<64-hex>  ja4proxy` (same format as `sha256sum`).
- `deploy/roles/02-artifact-build/tasks/build.yml` — when
  `ja4proxy_prebuilt_binary_path` is set, read the expected hash and
  `assert` source-side stat checksum matches it.
- `README.md` — one line in the prebuilt-binary section: "update
  `deploy/expected-binary-sha256.txt` when you change the binary".

**Acceptance.**
- Supplying a binary whose sha256 ≠ the pinned value fails the deploy
  with a clear message naming both hashes.
- Supplying the right binary deploys cleanly.

**CI hook.** Extend `scripts/ci/check_secrets_path.py` (or split into
`check_pinned_artifacts.py`) to assert
`deploy/expected-binary-sha256.txt` exists and parses as
`^[0-9a-f]{64}\s+\S+$`.

**Depends on.** 14-A (so the pinned hash reflects a trimpath/buildvcs
binary).

**Not in scope.** Signed binaries (cosign, Sigstore) — out of scope for
this research project.

## 14-C — GeoIP source integrity

**Scope.** Pin the sha256 of the expected GeoIP database file in
`group_vars/all.yml` and verify it on deploy before the file is
installed.

**Why.** The IP2Location LITE download rotates; silent content drift
means yesterday's research result isn't reproducible from today's data.

**Files.**
- `deploy/inventory/group_vars/all.yml` — new var
  `ja4proxy_geoip_expected_sha256: ""` (empty default = skip check,
  so offline tests still pass).
- `deploy/roles/02-artifact-build/tasks/geoip.yml` (or wherever the
  GeoIP file is copied) — `ansible.builtin.stat` with
  `checksum_algorithm: sha256`, then `assert` against the pinned value
  when non-empty.
- `docs/phases/PHASE_02_ARTIFACT_PREPARATION.md` — document that
  updating the GeoIP db requires updating the pin.

**Acceptance.**
- When pin is set and file matches: deploy succeeds.
- When pin is set and file differs: deploy fails with both hashes
  shown.
- When pin is empty: deploy succeeds unchanged (preserve existing
  behaviour so the smoke test still works without a pinned GeoIP).

**CI hook.** Extend `scripts/ci/check_groupvars_coverage.py` to require
`ja4proxy_geoip_expected_sha256` be declared (may be empty string).

**Depends on.** Nothing.

**Not in scope.** Automating the pin update — operator does it
deliberately.

## 14-D — Idempotency test (inside VM smoke)

**Scope.** Add an idempotency run to the VM smoke test runbook: after
the first `make deploy` succeeds, run it a second time and fail if the
final `PLAY RECAP` reports any `changed > 0`.

**Why.** Non-idempotent tasks are silent bugs that look fine on first
deploy and cause drift on every subsequent run. Catching this on the
smoke test (not production) is the safe place.

**Files.**
- `docs/phases/VM_SMOKE_TEST.md` — add a new section "Idempotency"
  between "Deploy" and "Verify", with the re-run command and the grep
  for `changed=[1-9]`.
- `deploy/scripts/check-idempotency.sh` — new helper that re-runs the
  playbook and parses the last `PLAY RECAP` line, exiting non-zero if
  any host reports `changed > 0`. Invokable as
  `make idempotency-check VM_IP=...` if we want; at minimum callable
  from the runbook.
- `deploy/Makefile` — new `idempotency` target mirroring `verify`.

**Acceptance.**
- On a cleanly-deployed VM, running the new target exits 0 and prints
  a one-line summary.
- Deliberately introducing a non-idempotent task (e.g. `command:`
  without `changed_when`) makes it exit non-zero.

**CI hook.** Cannot run without a VM; `scripts/ci/check_makefile_phony`
will catch the new PHONY target existing, and `check_roles_exist` will
catch any role path typo. Note the gap in the PR description.

**Depends on.** 14-A (so both runs produce the same binary hash and
don't diff).

**Not in scope.** Full Molecule framework — that's 14-E.

## 14-E — Molecule scenario for `01-vm-provisioning`

**Scope.** Add a Molecule scenario that boots Ubuntu 22.04 in Docker
and runs just role 01, asserting its post-conditions (user created, UFW
installed, baseline packages present).

**Why.** Role 01 is the highest-risk role because it shapes every later
role's environment. Molecule gives us a ~2-minute feedback loop without
renting a VM.

**Files.**
- `deploy/roles/01-vm-provisioning/molecule/default/molecule.yml` —
  docker driver, ubuntu:22.04 image with systemd.
- `deploy/roles/01-vm-provisioning/molecule/default/converge.yml` —
  play that applies the role.
- `deploy/roles/01-vm-provisioning/molecule/default/verify.yml` —
  assertions.
- `Makefile` root — `molecule` target that invokes
  `molecule test` for this scenario.
- `.github/workflows/ci.yml` — optional: run `make molecule` in a
  separate job. Docker-in-Docker matrix row. Gate behind a label to
  keep PR feedback fast.

**Acceptance.**
- `make molecule` green locally.
- CI job green on PR.
- Deliberately breaking role 01 (e.g. bad package name) turns the job
  red.

**CI hook.** The Molecule scenario itself *is* the check. Also add
`scripts/ci/check_molecule_scenarios.py` asserting every scenario
directory has `molecule.yml`, `converge.yml`, `verify.yml`.

**Depends on.** Docker available in CI runner (already is).

**Not in scope.** Molecule for other roles — one at a time; add more in
follow-ups.

---

# Phase 13a — Retention enforcement

Turns the declared retention period into an enforced one. The privacy
statement (11-B) will promise these numbers; we must be able to show
they're real.

## 13-A — `journald.conf` templating + handler

**Scope.** Render `/etc/systemd/journald.conf` from a template,
enforcing `MaxRetentionSec`, `SystemMaxUse`, and `Compress=yes`. Restart
`systemd-journald` via handler on change.

**Why.** `ja4proxy_journald_max_retention` exists in group_vars today
but is never written to disk — so the journal retains by default
policy, not ours.

**Files.**
- `deploy/templates/journald.conf.j2` — new template.
- `deploy/roles/05-data-collection/tasks/main.yml` — task to template
  into `/etc/systemd/journald.conf` with `mode: "0644"`.
- `deploy/roles/05-data-collection/handlers/main.yml` — `Restart
  systemd-journald` via `ansible.builtin.systemd_service`.

**Acceptance.**
- On VM: `grep -E '^MaxRetentionSec|^SystemMaxUse' /etc/systemd/journald.conf`
  shows the templated values.
- `journalctl --disk-usage` stays below `SystemMaxUse`.

**CI hook.** Extend `scripts/ci/check_jinja.py` to parse
`journald.conf.j2` without error (already covers all `.j2` files
generically, but verify it's picked up).

**Depends on.** Nothing.

**Not in scope.** Forwarding journald to a remote host.

## 13-B — Loki retention configuration

**Scope.** Add `table_manager.retention_deletes_enabled: true` and
`retention_period: 2160h` (90d) to the Loki config template.

**Why.** Same story as journald — the "90d" number in
`PHASE_11 §2 / RETENTION.md` has to be true, not aspirational.

**Files.**
- `deploy/templates/loki-config.yml.j2` — add the `table_manager`
  stanza.
- `deploy/inventory/group_vars/all.yml` — add
  `ja4proxy_loki_retention_period: "2160h"` so it's a single source.

**Acceptance.**
- `curl -s http://127.0.0.1:3100/config | grep -E 'retention_period|retention_deletes_enabled'`
  shows the templated values.
- Synthetic old log (pushed with `--ts` in the past) is deleted on next
  retention sweep.

**CI hook.** Extend `scripts/ci/render_compose.py` (or add a sibling
`render_loki.py`) to render the template with test vars and assert the
retention keys appear in the output.

**Depends on.** 13-A (for consistency — journald then Loki).

**Not in scope.** Swapping Loki's storage backend.

## 13-C — Prometheus TSDB retention flags

**Scope.** Add `--storage.tsdb.retention.time=90d` and
`--storage.tsdb.retention.size=5GB` to the Prometheus container command
in the compose template.

**Why.** Without these, Prometheus keeps data forever and eventually
fills the VM.

**Files.**
- `deploy/templates/docker-compose.yml.j2` — extend the Prometheus
  `command:` block.
- `deploy/inventory/group_vars/all.yml` — new vars
  `ja4proxy_prometheus_retention_time: "90d"` and
  `ja4proxy_prometheus_retention_size: "5GB"`.

**Acceptance.**
- `docker inspect ja4proxy-prometheus | grep retention` shows both
  flags.
- Over time, `prometheus_tsdb_lowest_timestamp_seconds` lags
  `now() - 90d` appropriately.

**CI hook.** Extend `scripts/ci/render_compose.py` to assert both
retention flags appear in the rendered compose command for the
`prometheus` service.

**Depends on.** 13-B.

**Not in scope.** Enabling `--web.enable-admin-api` (that comes with
12-A when we actually need the snapshot endpoint).

---

# Phase 11 — Legal, ethics, and honeypot disclosure

The minimum governance layer required before any real go-live. Most
chunks are template + one verify task; the docs chunk is authoring.

## 11-A — Honeypot disclosure page

**Scope.** Serve a plain-English disclosure at `/honeypot-notice.html`
via Caddy. Link from the honeypot form's footer.

**Why.** GDPR transparency obligation, and it lets abuse-report
recipients immediately see what they're looking at.

**Files.**
- `deploy/files/honeypot-notice.html` — static HTML; plain prose
  listing: research purpose, no-real-data claim, abuse contact,
  privacy contact.
- `deploy/roles/04-supporting-services/tasks/main.yml` — new copy task
  to deploy into `/opt/ja4proxy-docker/caddy-www/`.
- `deploy/templates/Caddyfile.j2` — ensure the notice path is served
  (it will be, if the directory is the site root; just verify).
- `deploy/roles/07-validation/tasks/main.yml` — add a smoke check:
  `uri:` to `https://127.0.0.1/honeypot-notice.html` with
  `validate_certs: false`, assert body contains "abuse@".

**Acceptance.**
- `curl -ks https://<domain>/honeypot-notice.html | grep abuse@` matches
  on the VM.
- Validation role fails clearly if the file is missing.

**CI hook.** Extend `scripts/ci/check_secrets.py` (which already scans
for plaintext) to also assert `deploy/files/honeypot-notice.html`
contains the literal strings `abuse@` and `privacy@`.

**Depends on.** Nothing.

**Not in scope.** Translation — English only for now.

## 11-B — Privacy / data-controller page

**Scope.** Serve `/privacy.html` with the GDPR statement (controller,
lawful basis, purposes, categories, retention, recipients, rights,
transfers).

**Why.** Required by GDPR Article 13 for any EU-facing service, even a
decoy.

**Files.**
- `deploy/files/privacy.html` — static HTML; can be mostly-static but
  the domain and retention periods must be templated. Move to
  `deploy/templates/privacy.html.j2` if so.
- `deploy/roles/04-supporting-services/tasks/main.yml` — deploy task.
- `deploy/roles/07-validation/tasks/main.yml` — smoke check as 11-A.

**Acceptance.**
- `curl -ks https://<domain>/privacy.html` returns 200 with non-empty
  body.
- Retention periods on the page equal the values in `group_vars`.

**CI hook.** New `scripts/ci/check_privacy_page.py`: render the
template with default vars, assert required section headings are
present (`Controller`, `Lawful basis`, `Retention`, etc.).

**Depends on.** 13-A, 13-B, 13-C (so the retention values promised on
the page are actually enforced).

**Not in scope.** DPIA / ROPA (those are 11-E).

## 11-C — `security.txt`

**Scope.** Serve `/.well-known/security.txt` per RFC 9116 with
`Contact:` and `Expires:`.

**Why.** Standard security-contact discovery; many researchers check
here before the HTML page.

**Files.**
- `deploy/templates/security.txt.j2` — template with Contact, Expires
  (one year out, templated from `ansible_date_time`), Preferred-Languages.
- `deploy/roles/04-supporting-services/tasks/main.yml` — deploy into
  `/.well-known/security.txt`.
- `deploy/templates/Caddyfile.j2` — confirm routing (Caddy serves
  static files by default; may need an explicit route for the
  dot-prefixed directory).
- `deploy/roles/07-validation/tasks/main.yml` — smoke check.

**Acceptance.**
- `curl -ks https://<domain>/.well-known/security.txt` returns 200
  with a `Contact:` line and an `Expires:` in the future.

**CI hook.** Extend `check_jinja.py` to also parse
`security.txt.j2` (it will by default; verify). Add a small assertion
in `render_compose.py` style that `Contact:` and `Expires:` both appear
in the rendered output.

**Depends on.** Nothing.

**Not in scope.** PGP-signing the file; sufficient as plain text.

## 11-D — `abuse@<domain>` MX preflight

**Scope.** Before opening UFW 80/443 in role 10, resolve the
`abuse@<ja4proxy_domain>` MX record on the control machine and fail
the deploy if missing.

**Why.** The privacy page promises an abuse contact. If the MX doesn't
exist, complaints bounce silently and the honeypot looks malicious to
the wider ecosystem.

**Files.**
- `deploy/roles/10-go-live/tasks/main.yml` — new task block at the top:
  `ansible.builtin.command: dig +short MX {{ ja4proxy_domain }}`
  delegated to localhost, `assert` that stdout is non-empty and
  parseable.
- `docs/phases/PHASE_10_GO_LIVE.md` — document the preflight.

**Acceptance.**
- Domain with no MX: `make go-live` fails at the preflight with a
  message naming the missing record.
- Domain with a valid MX: preflight passes.

**CI hook.** Cannot DNS-resolve offline; note this in PR. Add
`scripts/ci/check_preflight_tasks.py` that greps role 10 for the
preflight task name so its deletion would be caught.

**Depends on.** Nothing.

**Not in scope.** Verifying the MX host actually accepts mail (that's a
network test, runbook territory).

## 11-E — Governance document skeletons

**Scope.** Create `docs/governance/` with skeleton files that the
operator fills in: `LAWFUL_BASIS.md`, `DPIA.md`, `ROPA.md`,
`RETENTION.md`, `LE_REQUESTS.md`, `ETHICS.md`. Each file has a section
structure, empty fields, and a date stamp.

**Why.** These documents are operator-authoring work, not Ansible, but
they must exist and be kept current. A skeleton file in the repo is
both a placeholder and a prompt.

**Files.**
- `docs/governance/LAWFUL_BASIS.md` — Article 6(1)(f) balancing test
  sections.
- `docs/governance/DPIA.md` — standard DPIA sections.
- `docs/governance/ROPA.md` — one-page tabular template.
- `docs/governance/RETENTION.md` — data-category → retention →
  enforcement-mechanism table; reference the actual config paths.
- `docs/governance/LE_REQUESTS.md` — request-handling procedure.
- `docs/governance/ETHICS.md` — ethics board / personal-research
  statement.
- `docs/governance/README.md` — index + review-cadence note.

**Acceptance.**
- All seven files exist.
- Each has a `Last reviewed:` line within the last year.
- `RETENTION.md` values match `group_vars/all.yml` and the privacy
  page.

**CI hook.** New `scripts/ci/check_governance_docs.py`: assert all
seven files exist, each has a `Last reviewed:` line with an ISO date
within the last 365 days. Fails loudly if anything gets stale.

**Depends on.** 13-A, 13-B, 13-C (so `RETENTION.md` reflects enforced
values) and 11-A..D (so references are accurate).

**Not in scope.** Filling in legal content — operator does that; the
skeleton prompts the right questions.

---

# Phase 13b — Alerting and dead-man's switch

A silent research run is a wasted research run. This batch adds the
plumbing to notice when something stops working.

## 13-D — Alertmanager container + wiring

**Scope.** Add Alertmanager to the compose stack, bound to
`127.0.0.1:9093`, and point Prometheus's `alerting:` block at it.

**Files.**
- `deploy/templates/docker-compose.yml.j2` — new `alertmanager` service.
- `deploy/templates/alertmanager.yml.j2` — config with a single route
  sending email via the operator's SMTP.
- `deploy/templates/prometheus.yml.j2` — `alerting:` block referencing
  `alertmanager:9093`.
- `deploy/inventory/group_vars/all.yml` — SMTP vars (server, from
  address); password in vault via `ja4proxy_secrets.smtp_password`.
- `deploy/scripts/generate-secrets.sh` — add `smtp_password` to the
  generated secret set (prompted if missing; default skip-and-warn).

**Acceptance.**
- `docker ps | grep alertmanager` on VM shows Running.
- `curl -s 127.0.0.1:9093/-/healthy` returns 200.
- `curl -s 127.0.0.1:9090/api/v1/alertmanagers` lists the Alertmanager.

**CI hook.** Extend `render_compose.py` to assert the `alertmanager`
service is rendered and that Prometheus's rendered config references
it.

**Depends on.** 13-C.

**Not in scope.** Non-email delivery targets (13-F adds a heartbeat
webhook; multi-channel routing comes later).

## 13-E — Alert rules file

**Scope.** Add `deploy/files/prometheus/alert-rules.yml` with:
`JA4proxyDown`, `HAProxyDown`, `RedisDown`, `NoTrafficLastHour`,
`DiskFull`.

**Files.**
- `deploy/files/prometheus/alert-rules.yml` — the rules.
- `deploy/templates/prometheus.yml.j2` — `rule_files:` stanza.
- `deploy/roles/04-supporting-services/tasks/main.yml` — copy the rules
  file into the Prometheus volume.

**Acceptance.**
- `curl -s 127.0.0.1:9090/api/v1/rules` returns the five rules loaded.
- Stopping `ja4proxy` (manually) fires `JA4proxyDown` within 2 min.

**CI hook.** New `scripts/ci/check_alert_rules.py`: parse the YAML,
assert the five expected alert names exist, each with `expr`, `for`,
and `labels.severity`.

**Depends on.** 13-D.

**Not in scope.** `CertExpiringSoon` — belongs with 13-F.

## 13-F — blackbox_exporter + cert expiry alert + heartbeat

**Scope.** Two related additions: (1) blackbox_exporter probing
`https://<domain>` so we have `probe_ssl_earliest_cert_expiry`;
(2) a cron or systemd-timer on the VM that pings a healthchecks.io
URL every 5 minutes.

**Files.**
- `deploy/templates/docker-compose.yml.j2` — `blackbox_exporter`
  service.
- `deploy/templates/blackbox.yml.j2` — HTTPS probe module.
- `deploy/templates/prometheus.yml.j2` — scrape job for blackbox,
  targeting `https://<domain>`.
- `deploy/files/prometheus/alert-rules.yml` — `CertExpiringSoon`
  rule on `probe_ssl_earliest_cert_expiry - time() < 7*24*3600`.
- `deploy/templates/heartbeat.timer.j2` +
  `deploy/templates/heartbeat.service.j2` — systemd units that
  `curl` the heartbeat URL.
- `deploy/inventory/group_vars/all.yml` —
  `ja4proxy_heartbeat_url: ""` (empty = skip).
- `deploy/scripts/generate-secrets.sh` — add optional heartbeat URL
  (URLs can be secret-ish).

**Acceptance.**
- `curl -s 127.0.0.1:9090/api/v1/query?query=probe_ssl_earliest_cert_expiry`
  returns a value.
- Heartbeat URL shows "green" in the external service within 10 min
  of deploy.

**CI hook.** Extend `check_alert_rules.py` to require
`CertExpiringSoon`. Extend `render_compose.py` for `blackbox_exporter`.

**Depends on.** 13-D, 13-E.

**Not in scope.** Replacing healthchecks.io with self-hosted —
research-scale; don't bikeshed.

---

# Phase 13c — Cert and DNS preflight

## 13-G — DNS A-record preflight in role 10

**Scope.** Resolve `ja4proxy_domain` on the control machine and assert
it maps to `ja4proxy_vm_host` before opening UFW 80/443 or switching
Caddy to production ACME.

**Files.**
- `deploy/roles/10-go-live/tasks/main.yml` — add a preflight block at
  the top (next to 11-D's MX preflight), `dig +short A` + assert.
- `docs/phases/PHASE_10_GO_LIVE.md` — document.

**Acceptance.**
- A record missing / wrong: `make go-live` aborts with the observed vs
  expected IP.
- A record correct: proceeds.

**CI hook.** `check_preflight_tasks.py` (from 11-D) extended to assert
this preflight exists.

**Depends on.** 11-D.

**Not in scope.** AAAA records (we aren't publishing IPv6).

## 13-H — ACME staging default + phase10 flip

**Scope.** Default `ja4proxy_acme_staging: true` so `make deploy`
issues staging certs. Role 10 flips it to `false` on go-live (by
setting a fact for the play, not by editing group_vars — idempotent).

**Files.**
- `deploy/inventory/group_vars/all.yml` — `ja4proxy_acme_staging: true`.
- `deploy/templates/Caddyfile.j2` — already conditional on the flag;
  verify.
- `deploy/roles/10-go-live/tasks/main.yml` — `set_fact:
  ja4proxy_acme_staging: false`, re-template Caddyfile, notify restart.

**Acceptance.**
- `make deploy` on a fresh VM: Caddy uses LE-staging (certs are
  browser-invalid but issuance succeeds).
- `make go-live`: Caddy switches to production LE; `curl` shows a valid
  cert chain.

**CI hook.** Extend `render_compose.py` / Caddyfile render check:
render with `ja4proxy_acme_staging=true` and assert the staging
directive is present; render with `false` and assert absence.

**Depends on.** 13-G (run DNS preflight before switching to production
issuance; otherwise we burn LE rate-limit budget on a bad domain).

**Not in scope.** Custom ACME servers.

---

# Phase 13d — Operational hygiene

## 13-I — AIDE check systemd timer

**Scope.** Schedule `aide --check` daily at 03:30 via a systemd timer
+ service pair; email the operator on non-zero exit.

**Files.**
- `deploy/templates/aide-check.timer.j2` — `OnCalendar=*-*-* 03:30:00`.
- `deploy/templates/aide-check.service.j2` — runs `aide --check`, pipes
  output to `mail -s "[aide] ..." <operator>` on non-zero.
- `deploy/roles/08-hardening/tasks/main.yml` — deploy both; enable the
  timer.
- `deploy/inventory/group_vars/all.yml` — `ja4proxy_aide_email: ""`
  (empty = skip mailing, log only).

**Acceptance.**
- On VM: `systemctl list-timers --all | grep aide-check` shows a next
  run time.
- Manual `systemctl start aide-check.service` runs to completion (exit
  0 on an unchanged VM).

**CI hook.** New `scripts/ci/check_systemd_units.py`: for each
`*.timer.j2` there must be a matching `*.service.j2`; parse the timer
for a sensible `OnCalendar` line.

**Depends on.** Nothing.

**Not in scope.** AIDE database updates — that's still a manual
operator step.

## 13-J — Secrets rotation role

**Scope.** New role `deploy/roles/12-secrets-rotation/` tagged `rotate`
(not in the default `roles:` list). Regenerates Redis, Grafana admin,
HAProxy stats passwords; re-templates their configs; restarts only the
affected services. Re-encrypts `deploy/.vault/secrets.yml`.

**Files.**
- `deploy/roles/12-secrets-rotation/tasks/main.yml`
- `deploy/roles/12-secrets-rotation/defaults/main.yml`
- `deploy/playbooks/rotate.yml` — single-role playbook.
- `deploy/Makefile` — `make rotate VM_IP=…` target invoking
  `rotate.yml` with `--tags rotate`.
- `docs/phases/PHASE_13_POST_LAUNCH_OPERATIONS.md` — document the
  rotation cadence (quarterly).

**Acceptance.**
- `make rotate VM_IP=...` completes green.
- Post-rotation, Grafana login with the old password fails; new
  password from `secrets.yml` works.
- Zero data loss (Redis persistence + appropriate restart semantics).

**CI hook.** Extend `check_roles_exist.py` to include role 12 and
assert `deploy/playbooks/rotate.yml` exists and references it.

**Depends on.** A5 (vault at rest) — already landed.

**Not in scope.** Rotating JA4proxy signing keys (would need a proxy
reload strategy; defer).

## 13-K — Dead-man's-switch heartbeat + cost hints

**Scope.** Combines three small items: (1) document the healthchecks
heartbeat URL setup (complements 13-F); (2) `provision-alibaba-cloud.sh`
prints estimated monthly cost and requires `--confirm` to proceed;
(3) `docs/phases/RUNBOOK.md` adds steps for configuring the Alibaba
budget alert and requesting a PTR record.

**Files.**
- `deploy/scripts/provision-alibaba-cloud.sh` — cost estimate block +
  `--confirm` flag.
- `docs/phases/RUNBOOK.md` — new sections "Budget alert setup" and
  "PTR record request".
- `README.md` — mention the heartbeat env var in the Operations
  section.

**Acceptance.**
- `make cloud` without `--confirm`: prints the estimate and exits 2.
- `make cloud ALIYUN_ARGS="--confirm ..."`: proceeds.
- Runbook sections render cleanly.

**CI hook.** `shellcheck` catches shell syntax; no new check needed.

**Depends on.** 13-F (for the heartbeat URL concept to already exist).

**Not in scope.** Auto-tearing down idle VMs.

---

# Phase 12 — Data lifecycle and export

Turns the honeypot's data into a portable research artefact, with
anonymisation gated in front of sharing.

## 12-A — Weekly export timer + script

**Scope.** Systemd timer on the VM that weekly produces
`/opt/ja4proxy-export/<YYYY-WW>/` containing a Prometheus TSDB
snapshot, Loki logs JSONL dump, and `manifest.yml` with sha256s.

**Files.**
- `deploy/scripts/export-week.sh` — the worker.
- `deploy/templates/ja4proxy-export.timer.j2` + `.service.j2`.
- `deploy/roles/11-data-export/tasks/main.yml` — new role.
- `deploy/playbooks/site.yml` — add role 11 to the `roles:` list.
- `deploy/templates/prometheus.yml.j2` — ensure
  `--web.enable-admin-api` on the Prometheus container (safe because
  the port is loopback-only).

**Acceptance.**
- `systemctl list-timers | grep ja4proxy-export` shows a next run.
- Manually running the service produces a directory with a non-empty
  `manifest.yml`.
- Every file in the directory has a matching sha256 in the manifest.

**CI hook.** `check_systemd_units.py` (from 13-I) picks up the new
pair. `check_roles_exist.py` extended for role 11. `shellcheck` for the
script.

**Depends on.** 13-C (Prometheus retention set first) and 13-I (timer
scaffolding pattern established).

**Not in scope.** Pushing the artefact anywhere — that's 12-C.

## 12-B — Anonymisation script

**Scope.** `deploy/scripts/anonymise.py` runs on the control machine
(not the VM), taking an export directory + a per-run salt and producing
an anonymised copy. IPv4 → HMAC-SHA-256 keyed by the salt; IPv6 → same
on the /64; rows containing plausible PII in form submissions are
dropped entirely.

**Files.**
- `deploy/scripts/anonymise.py` — the tool.
- `deploy/scripts/test_anonymise.py` — unit tests covering: IP hashing
  stability under the same salt, IP hashing divergence under different
  salts, PII-row drop.
- `scripts/ci/check_test_anonymise.py` — runs the unit tests in CI.
- `docs/governance/ANONYMISATION.md` — documents the scrub.

**Acceptance.**
- `python3 deploy/scripts/test_anonymise.py` passes.
- On a sample export, every IPv4 octet sequence present in the input
  is absent in the output; ASNs preserved.

**CI hook.** Wire `test_anonymise.py` into `make test` via a new
Makefile target `test-anonymise` that the root `test` target calls.

**Depends on.** 12-A (you need an export to anonymise).

**Not in scope.** Differential privacy — out of scope; HMAC is the
stated method.

## 12-C — `make export-pull VM_IP=...`

**Scope.** Makefile target that `rsync`s the newest
`/opt/ja4proxy-export/<YYYY-WW>/` from the VM to
`./exports/<VM>-<YYYY-WW>/` on the control machine, verifies every
sha256 in `manifest.yml`, and refuses to overwrite an existing local
directory.

**Files.**
- `deploy/Makefile` — `export-pull` target.
- `deploy/scripts/export-pull.sh` — the rsync + verify worker.

**Acceptance.**
- `make export-pull VM_IP=...` produces a local directory matching
  remote.
- Tampering with any file post-pull: next `make export-pull` to a
  different local dir + compare detects the drift via sha256.

**CI hook.** `shellcheck`; `check_makefile_phony.py` picks up the new
target.

**Depends on.** 12-A.

**Not in scope.** S3 / object-store uploads.

## 12-D — Binary-provenance file

**Scope.** At build time (role 02), write
`/opt/ja4proxy/config/binary-provenance.yml` with the commit hash,
sha256, build timestamp, and `goflags`. Include it in the weekly
export manifest.

**Files.**
- `deploy/roles/02-artifact-build/tasks/build.yml` — render provenance
  file after the copy step.
- `deploy/scripts/export-week.sh` — include `binary-provenance.yml`
  content in the manifest.

**Acceptance.**
- `cat /opt/ja4proxy/config/binary-provenance.yml` shows a commit sha,
  sha256 matching the A8 assertion, and ISO-8601 timestamp.
- Weekly export manifest references it.

**CI hook.** Extend the role-02 check (if any) or add a grep in
`check_go_build_flags.py` ensuring the provenance template exists.

**Depends on.** 14-A, 14-B, 12-A.

**Not in scope.** Signing the provenance file.

---

# Phase 15 — Incident response

Documentation-heavy phase. Only one script (15-A); the rest is
authoring the operator's runbook into existence.

## 15-A — `preserve-evidence.sh` on the VM

**Scope.** Script at `/usr/local/sbin/preserve-evidence.sh`, deployed
by a role, that dumps journald / Prometheus snapshot /
`docker compose logs` / iptables / `/opt/ja4proxy/config` into a
timestamped tarball with a sha256 hash printed at the end.

**Files.**
- `deploy/scripts/preserve-evidence.sh` — the script.
- `deploy/roles/06-operational-security/tasks/main.yml` — copy the
  script, `mode: "0750"`, owner root.
- `docs/phases/RUNBOOK.md` — reference from scenario 6 (compromise).

**Acceptance.**
- Running `preserve-evidence.sh` on the VM produces a tarball with all
  expected sections, and the printed sha256 matches.
- Script exits with a clear instruction to `rsync` off the VM before
  reboot.

**CI hook.** `shellcheck`; `check_roles_exist.py` unchanged.

**Depends on.** 13-C (so the Prometheus admin API is available for the
snapshot).

**Not in scope.** Encrypted evidence tarballs.

## 15-B — Runbook expanded with IR scenarios

**Scope.** Add to `docs/phases/RUNBOOK.md` (or split into
`INCIDENT_RESPONSE.md` if it grows > 400 lines) the eight scenarios
from `PHASE_15 §15.4`: SSH lockout, Caddy ACME rate-limit, Redis
corruption, disk full, Grafana password reset, VM compromise, LE
request, DNS-misconfig-opened-UFW.

**Files.**
- `docs/phases/RUNBOOK.md` or `docs/phases/INCIDENT_RESPONSE.md`.

**Acceptance.**
- Each scenario has: preconditions, numbered procedure, rollback.
- Compromise scenario references `preserve-evidence.sh` from 15-A.

**CI hook.** New `scripts/ci/check_runbook_scenarios.py`: assert the
eight scenario headings exist in the file. Fails if any is deleted.

**Depends on.** 15-A.

**Not in scope.** Walking through each scenario on a live VM — that's
a quarterly ops exercise.

## 15-C — Governance: abuse / outbound / stakeholders docs

**Scope.** Three more files under `docs/governance/`:
`abuse-reply-template.md` (canned reply), `OUTBOUND_REPORTING.md`
(decision tree for LE referrals), `STAKEHOLDERS.yml` (notification
list).

**Files.**
- `docs/governance/abuse-reply-template.md`
- `docs/governance/OUTBOUND_REPORTING.md`
- `docs/governance/STAKEHOLDERS.yml`

**Acceptance.**
- Files exist, have a `Last reviewed:` line.
- `STAKEHOLDERS.yml` is valid YAML.

**CI hook.** Extend `check_governance_docs.py` (from 11-E) to require
these three.

**Depends on.** 11-E.

**Not in scope.** Filling stakeholder names in the repo — keep the
list generic; operator fills locally.

## 15-D — README Operations section

**Scope.** Add a short `## Operations` section to `README.md` stating
the on-call posture: 3 business days for abuse email, 24 h for
down-alerts, documented away periods use `make go-dark` (or a manual
stop) before leaving.

**Files.**
- `README.md`.

**Acceptance.**
- Section exists, is ≤ 20 lines, references the relevant runbook
  scenarios.

**CI hook.** Extend `check_governance_docs.py` to assert README
contains an `## Operations` heading.

**Depends on.** 15-B (so the runbook references have targets).

**Not in scope.** Implementing `make go-dark` — a later chunk if
needed; manual stop is fine for now.

---

# C6 — Threat model

## TM-A — `THREAT_MODEL.md`

**Scope.** A single `THREAT_MODEL.md` at repo root with: system
diagram (reuse the README traffic-path ASCII), attack trees for the
obvious targets (VM compromise, honeypot-as-DDoS-reflector,
DNS/domain hijack, data-exfil via metrics/logs), residual risk
register with owners.

**Files.**
- `THREAT_MODEL.md`

**Acceptance.**
- Contains the required sections; cross-links to each Phase doc that
  mitigates.
- `docs/phases/PHASE_08_SECURITY_HARDENING.md` STRIDE table links
  here.

**CI hook.** Extend `check_governance_docs.py` to require
`THREAT_MODEL.md` has a `Last reviewed:` date ≤ 365 days old.

**Depends on.** All previous chunks landed — gives an accurate
residual-risk picture.

**Not in scope.** Formal methods; this is a research project, not
aerospace.

---

# Tracking

Each chunk, when landed, should append one line to the bottom of this
file:

```
- [x] 14-A Go build hygiene — merged 2026-04-17 (PR #8)
```

That makes the file a living checklist and keeps the review cadence
visible.

## Status

<!-- Append as chunks land. -->

- [x] 14-A — GOFLAGS -trimpath + -buildvcs (PR #?)
- [x] 14-B — prebuilt binary sha256 pin (PR #?)
- [x] 14-C — GeoIP sha256 pin (PR #?)
- [x] 14-D — idempotency re-run target (PR #?)
- [x] 14-E — Molecule scenario skeleton (PR #?)
- [x] 13-A — journald.conf template (PR #?)
- [x] 13-B — Loki retention regression guard (PR #15)
- [x] 13-C — Prometheus TSDB retention time + size (PR #16)
- [x] 11-A — honeypot disclosure page (PR #17)
- [x] 11-C — RFC 9116 security.txt (PR #18)
- [x] 11-D — MX preflight before go-live (PR #19)
- [x] 13-G — DNS A-record preflight (PR #20)
- [x] 13-H — ACME staging default + go-live flip (PR #21)
- [x] 11-B — /privacy GDPR page (PR #27)
- [ ] 11-E — governance document skeletons
- [ ] 13-D — Alertmanager
- [ ] 13-E — alert rules
- [x] 13-F — blackbox_exporter + heartbeat (PR #29)
- [ ] 13-I — AIDE timer
- [ ] 13-J — secrets rotation role
- [x] 13-K — heartbeat / cost hints (PR #26)
- [ ] 12-A — weekly export timer
- [ ] 12-B — anonymisation in export
- [ ] 12-C — export-pull on control machine
- [x] 12-D — binary provenance (PR #25)
- [ ] 15-A — preserve-evidence.sh
- [ ] 15-B — runbook IR scenarios
- [ ] 15-C — governance docs body
- [x] 15-D — README Operations (PR #28)
- [ ] TM-A — THREAT_MODEL.md
