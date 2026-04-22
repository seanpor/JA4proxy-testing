# Critical Review — JA4proxy-testing

**Reviewer:** expert pass, 2026-04-15
**Scope reviewed:** `README.md`, `QWEN.md`, `deploy/` (all 10 roles, templates, scripts, playbook), `docs/phases/PHASE_00`–`PHASE_08`, `ANSIBLE_BUILD_PLAN.md`, `DEPLOYMENT_ANALYSIS.md`, `RUNBOOK.md`.

> **Status, 2026-04-22 — remediation complete (A/C series).** Every
> A-series code bug and every C-series missing-phase gap identified
> below has been addressed. The mapping in §G names the doc/PR for
> each; the `Status` block in `GOVERNANCE_ROADMAP.md` is the
> authoritative landing log (now including the Phase 18-J deferral
> entry added 2026-04-22 under Phase 20 P2-12). This document is kept
> as a **historical snapshot** of what the repo looked like on
> 2026-04-15 — do not "fix" the findings here by editing them; track
> any *new* defects in a fresh PR or issue. For currently-open
> governance-theatre follow-ups, see
> `docs/phases/PHASE_20_PHASE_18_REMEDIATION.md`.

This document is deliberately blunt. It identifies defects in the code, gaps between what the docs claim and what the Ansible actually does, and whole areas of work that are missing for an internet-facing research honeypot. Each finding names a file:line or role where possible, and each maps to a remediation in a new or updated phase document.

---

## Executive summary

The project is well-organised and the staged-deploy model (locked → verified → live) is a good design. But:

1. **Several concrete bugs will make the happy-path deploy silently wrong** (secrets path mismatch, digest-pinning regex, AppArmor-without-restart).
2. **Phase documentation stops at Phase 8**, while the codebase has phase-9 and phase-10 roles in production use — i.e. two operational phases are undocumented.
3. **Entire categories of work that are non-negotiable for a public honeypot are absent**: legal posture / GDPR / DPIA, abuse-report handling, research data export, cost controls, alerting and dead-man's-switch monitoring, Ansible CI / idempotency testing, secrets rotation and encryption-at-rest.
4. **"25+ verification checks", "counterfactual logging", and "SHA-256 digest pinning" are claimed but not actually verified end-to-end.** Several are deployment theatre: the artefact is produced but never checked to be doing its job.

The system is probably *safe enough* to deploy privately in locked mode for self-testing. It is **not yet ready to go live on the public internet** without fixing the confirmed bugs and adding the missing governance layer.

---

## A. Confirmed code bugs (fix before any go-live)

### A1. Secrets path mismatch between script and playbook — **breaks every deploy**

- `deploy/scripts/generate-secrets.sh:11` computes `VAULT_DIR="$(cd "$(dirname "$0")/../.." && pwd)/.vault"`.
  - `dirname $0` = `deploy/scripts`, `../..` = repo root, so secrets are written to **`<repo_root>/.vault/secrets.yml`**.
- `deploy/playbooks/site.yml:163` loads secrets from `"{{ playbook_dir }}/../.vault/secrets.yml"`.
  - `playbook_dir` = `deploy/playbooks`, `../.vault` = **`deploy/.vault/secrets.yml`**.
- `.gitignore` only ignores `deploy/.vault/`, so the plaintext secrets file generated at the repo root is **not gitignored** and could be committed.

**Impact:** `make deploy` always runs `generate-secrets.sh` first, which writes to the wrong directory. The subsequent `include_vars` in the playbook will either fail, or load a stale file, or silently load nothing depending on whether `deploy/.vault/secrets.yml` already exists.

**Fix:** change either the script or the playbook to use the same path. Canonical location should be `deploy/.vault/secrets.yml`. Update `.gitignore` to also cover any stray `/.vault/` at the repo root.

### A2. Docker image-digest pinning regex never matches on first run

In `deploy/roles/09-image-digests/tasks/main.yml:68–75`:

```yaml
- name: Update docker-compose.yml with pinned digests
  ansible.builtin.lineinfile:
    path: "{{ ja4proxy_docker_base_dir }}/docker-compose.yml"
    regexp: "^    image: {{ item.value.split(':')[0] }}:"
    line: "    image: {{ item.value }}"
  loop: "{{ resolved_digests | dict2items }}"
```

`item.value` here is a full RepoDigest like `haproxy@sha256:abc…`. `.split(':')[0]` therefore yields `haproxy@sha256`, and the regex becomes `^    image: haproxy@sha256:` — which **cannot match** the existing line `    image: haproxy:2.8-alpine`. On first run nothing is rewritten; on second run (after manual editing) it would match its own output and no-op.

**Impact:** Phase 9 is deployment theatre. The docker-compose.yml keeps using mutable tags. Supply-chain pinning is claimed (README §222, PHASE_08 §8.3) but not achieved.

**Fix:** key the regex off the *service name* or the image short-name (e.g. `item.key`), not off a derived digest prefix. Example: `regexp: "^    image: (haproxy|redis|caddy|prometheus|grafana|loki|promtail)[:@]"` keyed by a mapping. Or use `replace` with a per-service lookup. Add a post-task `grep -c '@sha256:' docker-compose.yml` assertion to prove pinning happened.

### A3. AppArmor profile applied but service never restarted — **confinement not active**

In `deploy/roles/08-hardening/tasks/main.yml:51–57`:

```yaml
- name: Add AppArmor profile to systemd service
  ansible.builtin.lineinfile:
    path: /etc/systemd/system/ja4proxy.service
    regexp: "^AppArmorProfile="
    line: "AppArmorProfile=opt.ja4proxy.bin.ja4proxy"
  notify: Daemon reload systemd
```

- `ja4proxy.service` has already been started in Phase 3 without `AppArmorProfile=`.
- The handler only reloads the unit file on disk; it does **not** restart the running process.
- `systemd` does not apply `AppArmorProfile=` to an already-running PID — it is consulted only at `ExecStart` time.
- There is also no check that the original `ja4proxy.service.j2` template has an `AppArmorProfile=` placeholder line for `lineinfile` to match; if the regex finds no existing line, `lineinfile` appends a new line at EOF which may end up outside the `[Service]` section.

**Impact:** JA4proxy runs unconfined between Phase 3 and the next manual restart. The hardening summary banner lies: `AppArmor: JA4proxy profile loaded` is true at the kernel level, but the target process is not constrained by it.

**Fix:**
1. Put `AppArmorProfile=opt.ja4proxy.bin.ja4proxy` directly in `templates/ja4proxy.service.j2` under `[Service]`.
2. Deploy the AppArmor profile in Phase 2 or 3, *before* the service first starts.
3. Replace the Phase 8 `lineinfile` with a verification task (`systemctl show ja4proxy -p AppArmorProfile | grep -q opt.ja4proxy.bin.ja4proxy`) and fail if absent.
4. If you keep the current ordering, add `notify: Restart ja4proxy` and define that handler.

### A4. SSH host-key checking disabled globally

`deploy/ansible.cfg:5`:

```
host_key_checking = False
```

This disables TOFU on every SSH handshake the playbook performs — not only the first. A MitM between the control machine and the VM is trivially successful on *any* Ansible run. For a security research project this is self-defeating.

**Fix:** leave `host_key_checking = True` (default). On first connection, run `ssh-keyscan <vm_ip> >> ~/.ssh/known_hosts` as part of `provision-alibaba-cloud.sh` after the EIP is allocated (capture the console-output SSH host key if the cloud exposes one, or pin after first manual connect). Document the procedure in the runbook.

### A5. Plaintext secrets file

`deploy/scripts/generate-secrets.sh` writes Redis, Grafana, HAProxy-stats passwords etc. in cleartext YAML. The file is gitignored but otherwise unprotected on the control machine's disk, backups, IDE indexers, and cloud sync.

**Fix:** after generation, encrypt with `ansible-vault encrypt deploy/.vault/secrets.yml` and require `--ask-vault-pass` (or a vault-id file) on every playbook run. Provide a `make unseal` / `make reseal` pair for ergonomics. Document in a new phase on secrets lifecycle.

### A6. Ansible collections installed without version pinning

`deploy/playbooks/site.yml:181`:

```yaml
cmd: ansible-galaxy collection install community.general community.docker ansible.posix
```

No versions, no lock file. Every run may fetch a newer major version and change behaviour underneath you.

**Fix:** create `deploy/requirements.yml` with pinned versions, and invoke `ansible-galaxy install -r deploy/requirements.yml` instead. Check the resulting versions with `ansible-galaxy collection list` and fail if they drift from the lock.

### A7. Hardcoded SSH key path

`deploy/playbooks/site.yml:193` sets `ansible_ssh_private_key_file: "{{ lookup('env', 'HOME') }}/.ssh/id_ed25519"`. No prompt, no env-var override, no fallback. If the operator's key is anywhere else the playbook fails opaquely.

**Fix:** honour `$JA4PROXY_SSH_PRIVATE_KEY` env var and a `vars_prompt` with sensible default; validate the path exists in `pre_tasks`.

### A8. Binary checksum computed but never compared

`deploy/roles/02-artifact-build/tasks/build.yml:29–35` and `78–84` produce a sha256 of the built/prebuilt binary but never compare it to anything. It is security theatre.

**Fix:** either (a) maintain `deploy/expected-binary-sha256.txt` in-repo (for prebuilt binaries) and assert equality, or (b) delete the task — do not keep unused security plumbing that suggests integrity checking is happening.

### A9. `ignore_errors`/opaque failure handling in VM-provisioning

Agent survey flagged an `ignore_errors: true` in `deploy/roles/01-vm-provisioning/tasks/directories.yml`. Any use of `ignore_errors` on an internet-facing box warrants an inline comment explaining why and a compensating verification task. If the silencing is no longer needed, delete it.

---

## B. Claims vs. reality gaps

| Claim | Source | Reality |
|---|---|---|
| "25+ health checks" | README §92, §279 | `deploy/scripts/verify-local.sh` should be counted; the exact number needs auditing, and the figure quoted in the README should be replaced by whatever the script actually does. |
| "Counterfactual logging" is collected data | README §344, PHASE_00 glossary | The config toggle `monitor_mode.counterfactuals: true` is written into `proxy.yml` (role 03), but no Phase 7 validation step actually queries a metric or a log line proving counterfactuals are emitted. If the binary changed and dropped that feature, we would not find out until analysis time. |
| "15+ security hardening flags" on JA4proxy systemd unit | README §208, PHASE_03 | Not verified: no assertion counts the hardening directives in the deployed unit file, nor compares them to a required baseline. |
| Upstream `JA4proxy4` Ansible role is "reused" | PHASE_03 top comment, DEPLOYMENT_ANALYSIS.md | `deploy/roles/03-ja4proxy-deploy/tasks/main.yml:19–33` is an inline debug message admitting the upstream is not wired in, and the role deploys its own inline config. The reuse story is aspirational. |
| "Fail2ban for SSH brute force protection" | README Phase 1 | The role does start/enable fail2ban and deploy a jail.local template, but the role never asserts that the jail is actually active post-deploy (`fail2ban-client status sshd`). |
| "Grafana dashboards (7)" | README §222 | The `files/` directory should contain 7 dashboard JSONs; this needs auditing, and any gap (missing dashboard, placeholder with no panels) should be tracked. |
| "Backup script" (README §228) | README Phase 6 | The docs promise a script; PHASE_06 discussion needs to say whether collected research data is in scope (it is not — only configs) and that the research-data export is a separate concern (see new PHASE_12). |

---

## C. Governance and operational gaps (missing phases)

The following categories are wholly absent from the current phase documentation and largely absent from the deployment. Each maps to a new phase document below.

### C1. Legal, ethics, and abuse handling — **PHASE_11**
- No abuse contact on the honeypot landing page, in WHOIS, or in reverse DNS.
- No acceptable-use / data-controller / privacy statement served from `/.well-known/` or the honeypot HTML.
- No GDPR posture: Alibaba eu-central-1 is in-EU, so Article 6 lawful basis, Article 13 transparency, and ePrivacy implications all apply. Research/"legitimate interests" is defensible but must be documented.
- No DPIA trigger assessment; arguably required because we systematically monitor publicly accessible traffic.
- No IRB/ethics-board approval path documented (needed for most academic publication routes).
- No law-enforcement-request handling procedure.

### C2. Abuse and incident response — **PHASE_15**
- An internet-facing decoy **will** trigger inbound abuse reports (the honeypot may look like a C2, a scanner, or a phishing page to third parties) and outbound complaints from ISPs whose customers land on it. None of this is planned for.
- The "kill switch" in `RUNBOOK.md` is a manual sequence. For a research box with no on-call rotation that is acceptable *if* escalation paths and timelines are written down; right now they are not.
- No evidence-preservation procedure before a forensic takedown (journald dump, `/opt/ja4proxy/` tarball, Prometheus snapshot, disk image).

### C3. Data lifecycle and research export — **PHASE_12**
- No defined mechanism for getting research data *off* the box. The system collects, but the scientific product of the project (datasets, fingerprint catalogues, bot taxonomies) is never described as a deliverable.
- `ja4proxy_journald_max_retention: 90d` is declared in group_vars but no `/etc/systemd/journald.conf` is templated to enforce it. Same concern for Loki's retention.
- No anonymisation / pseudonymisation stage between raw logs and any shared research artefact.

### C4. Post-launch operations — **PHASE_13**
Rolled up because each is short on its own:
- **Cost controls.** Alibaba egress charges can surprise. No budget alarm, no auto-shutdown on idle, no documented monthly-cost expectation test.
- **Alerting / dead-man's switch.** Prometheus + Grafana are deployed but no Alertmanager or equivalent, no paging target, no heartbeat that says "Sean, your honeypot stopped collecting at 03:41 last Thursday". A silent-failure research run wastes the whole experiment.
- **TLS certificate health.** Caddy auto-renews Let's Encrypt, but there is no alert if renewal ever fails. For a domain that holds this experiment together, we need a cert-expiry metric and an alert.
- **DNS preflight for go-live.** Phase 10 issues real LE certs. If the A record is not yet propagated or points elsewhere, we burn LE rate-limit budget. Add a preflight task that resolves the domain and confirms it maps to the VM's public IP before opening UFW 80/443.
- **ACME staging mode** toggle for first-deploy dry runs.
- **Secrets rotation.** Nothing rotates Redis/Grafana/HAProxy-stats passwords on a schedule; there is no documented procedure. Add a role + runbook entry.
- **AIDE check scheduling.** Role 08 runs `aideinit` once and never schedules `aide --check`. Without a cron/systemd-timer comparing against the baseline, AIDE is theatre.
- **journald.conf, Loki retention config, Grafana Alertmanager provisioning** all belong here.

### C5. Ansible CI and idempotency — **PHASE_14**
- No `.ansible-lint`, no `ansible-playbook --syntax-check` step, no Molecule tests, no idempotency check (run playbook twice, assert the second run is a no-op).
- No CI workflow in the repo.
- A typo in any role today is discovered only against a real VM.

### C6. Threat model hygiene
- PHASE_08 includes a STRIDE table but there is no single THREAT_MODEL.md with attack trees, residual-risk register, and named countermeasures cross-linked to roles. This isn't critical for launch but it *is* the thing a reviewer will ask for before any publication.

---

## D. Documentation hygiene

- **Phase docs stop at 08** even though the playbook has roles 09-image-digests and 10-go-live and the Makefile exposes `make digests` and `make go-live`. Fill the gap (see new PHASE_09 and PHASE_10 below).
- **PHASE_00 phase index** still lists "Status: ⏳ Next" for Phase 1. That was accurate at plan time but is now stale — the roles exist and are deployed. Update the index.
- **`QWEN.md`** describes JA4proxy as listening directly on 80/443, which contradicts the actual architecture (HAProxy passthrough on 443, JA4proxy on 8080). Either update it, delete it, or mark it "historical".
- **`docs/DETAILED_DEPLOYMENT_PLAN.md`** and `ANSIBLE_BUILD_PLAN.md` are design-phase artefacts. If they still represent intent, leave a "written before implementation" note at the top; if not, move to `docs/archive/`.
- **RUNBOOK.md** is only 102 lines and only covers rollback. It does not cover: SSH lockout recovery, UFW misconfiguration recovery, Caddy ACME stuck on staging, Redis ban-list corruption, Grafana admin-password reset, log-volume blowout. Each of those is a realistic 2am call.

---

## E. Prioritised remediation roadmap

**Must-fix before any public go-live:**

1. A1 — secrets path mismatch (one-line fix).
2. A2 — digest-pinning regex (rewrite the task).
3. A3 — AppArmor ordering + restart (move directive into the service template).
4. A4 — host-key checking (remove the `host_key_checking = False`, document ssh-keyscan step).
5. A5 — ansible-vault encrypt the secrets file.
6. PHASE_11 — minimum legal disclaimer, abuse contact, privacy statement on the honeypot page; GDPR lawful-basis doc.
7. PHASE_13 cert-renewal + dead-man's-switch alert; otherwise a silent outage is invisible.

**Should-fix before publishing any research based on the data:**

8. A6, A7, A8 — supply-chain / reproducibility hygiene.
9. PHASE_12 — data export pipeline and retention enforcement.
10. PHASE_14 — Ansible CI so changes are lintable and idempotent.

**Nice-to-have for a mature project:**

11. Threat model as a standalone document.
12. PHASE_15 — abuse-report queue and documented IR playbook beyond the rollback runbook.
13. PHASE_10 dry-run with LE staging baked into the default flow.

---

## F. What's already good

Acknowledging the strengths so the review isn't purely negative:

- **Staged deployment model** (locked → verified → live) is a genuinely good design choice and rare in hobbyist-scale work.
- **Idempotent secrets generator** (append-only, skip-if-present) is the right shape, even if the path bug in A1 is a blocker.
- **Role decomposition by phase** with dual tags (`[name, phaseN]`) is well-thought-out and makes partial deploys painless.
- **Monitor-first dial policy (`dial=0`)** with a documented escalation plan is the correct default for a research honeypot.
- **Sysctl + kernel-module lockdown + AIDE + AppArmor** baseline in Phase 8 is more hardened than most production boxes.
- **Separation from `JA4proxy4`** — keeping research honeypot concerns out of the enterprise repo — is architecturally right; the aspirational upstream-role reuse just needs to be wired up honestly.

---

## G. Mapping from findings to documents

| Finding | Addressed in |
|---|---|
| A1 secrets path | `PHASE_14_CI_AND_IDEMPOTENCY.md` §Secrets path regression test; patched note in `PHASE_00`. |
| A2 digest regex | `PHASE_09_IMAGE_DIGESTS.md` — documents the role and the known bug. |
| A3 AppArmor | `PHASE_08_SECURITY_HARDENING.md` patched with "Known issues"; full fix in `PHASE_14`. |
| A4 host key | `PHASE_13_POST_LAUNCH_OPERATIONS.md` §SSH trust bootstrap. |
| A5 plaintext secrets | `PHASE_13` §Secrets lifecycle & rotation. |
| A6 collection pinning | `PHASE_14` §Dependency pinning. |
| A7 SSH path | `PHASE_14` §Input validation. |
| A8 binary checksum | `PHASE_14` §Supply chain. |
| C1 legal | `PHASE_11_LEGAL_ETHICS_AND_HONEYPOT_DISCLOSURE.md`. |
| C2 abuse | `PHASE_15_ABUSE_AND_INCIDENT_RESPONSE.md`. |
| C3 data | `PHASE_12_DATA_LIFECYCLE_AND_EXPORT.md`. |
| C4 ops | `PHASE_13_POST_LAUNCH_OPERATIONS.md`. |
| C5 CI | `PHASE_14_CI_AND_IDEMPOTENCY.md`. |
| C6 threat model | deferred; tracked in `PHASE_00` phase index. |
