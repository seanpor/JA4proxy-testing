# Phase 14: Ansible CI, Idempotency, and Supply-Chain Hygiene

## Purpose

Today the only way to find out whether a change to a role works is to run it against a real VM. Typos, regex bugs (see `CRITICAL_REVIEW.md` §A2), path mismatches (§A1), and non-idempotent tasks land in production unchecked. This phase introduces the minimum CI scaffolding that would have caught each of those before a deploy.

## Deliverables

### 14.1 Static linting

Add:

- `.ansible-lint` at repo root, ruleset = default minus the few rules we deliberately accept.
- `deploy/.yamllint` for consistent YAML style.
- A `Makefile` target:

```
lint:
	ansible-lint deploy/playbooks/site.yml
	yamllint deploy/
	ansible-playbook --syntax-check deploy/playbooks/site.yml
```

Run in CI; fail the build on any violation.

### 14.2 Dependency pinning

Today:

```yaml
cmd: ansible-galaxy collection install community.general community.docker ansible.posix
```

Replace with `deploy/requirements.yml`:

```yaml
collections:
  - name: community.general
    version: "9.5.0"   # pin to an exact or ~= constraint
  - name: community.docker
    version: "3.12.2"
  - name: ansible.posix
    version: "1.6.2"
```

and in `site.yml`:

```yaml
- name: Install Ansible collections
  ansible.builtin.command:
    cmd: ansible-galaxy install -r {{ playbook_dir }}/../requirements.yml
```

Add a CI check that `ansible-galaxy collection list --format json` matches the lock file. Quarterly, bump deliberately.

### 14.3 Secrets path regression test

Directly addresses `CRITICAL_REVIEW.md` §A1. A one-line shell test in CI:

```bash
test "$(deploy/scripts/generate-secrets.sh --dry-run-path)" = "$(pwd)/deploy/.vault/secrets.yml"
```

Implement `--dry-run-path` in the script so the test doesn't have side-effects. Alternatively, unify the path constant across script and playbook via an environment variable sourced from `deploy/scripts/paths.sh`.

### 14.4 Idempotency test

Run the playbook twice in CI against a disposable target (see 14.6) and fail if the second run reports any `changed=N > 0`. The conventional command:

```bash
ansible-playbook deploy/playbooks/site.yml
ansible-playbook deploy/playbooks/site.yml | tee second.log
grep -E 'changed=([1-9][0-9]*)' second.log && exit 1 || exit 0
```

Idempotency failures are an early warning of tasks that should be `changed_when: false` but aren't, or that lack a `creates:` guard.

### 14.5 Role-level molecule tests (optional, high value)

For the three highest-risk roles (`01-vm-provisioning`, `03-ja4proxy-deploy`, `08-hardening`), add a Molecule scenario that boots a throwaway Docker container (Ubuntu 22.04 image) and runs just that role, then asserts its postconditions.

This will not exercise anything that depends on systemd-in-Docker being reliable (AppArmor, sysctl, Docker-in-Docker) — for those, fall back to 14.6.

### 14.6 End-to-end test against a disposable VM

A CI job (or a `make ci-e2e`) that:

1. Provisions an Alibaba Cloud VM with a short-lived tag `ci-run-<sha>`.
2. Runs the full playbook.
3. Runs `deploy/scripts/verify-local.sh` over SSH.
4. Tears the VM down unconditionally.

Gate this behind a manual approval in CI — it costs money — but make it one click.

### 14.7 Supply-chain checks

In addition to image-digest pinning (PHASE_09), add:

- **Go build hygiene.** `-trimpath -buildvcs=true` and `GOFLAGS='-trimpath -buildvcs=true'` in `deploy/roles/02-artifact-build/tasks/build.yml`. The result is that `go version -m <binary>` on the VM lists the exact commit, module versions, and build settings.
- **Binary checksum comparison, not just generation.** Maintain `deploy/expected-binary-sha256.txt` for prebuilt-binary flows; fail the deploy if `sha256sum` differs. For build-from-source, record the checksum post-build into `binary-provenance.yml` (PHASE_12 §4) rather than pretending to verify something we haven't checked.
- **GeoIP source integrity.** Record the expected sha256 of the GeoIP database in `group_vars/all.yml` and verify on deploy. If the IP2Location LITE download rotates, the operator must consciously re-pin.

### 14.8 Input validation hardening

Addresses `CRITICAL_REVIEW.md` §A7. In `site.yml` `pre_tasks`:

- Resolve SSH private-key path from `$JA4PROXY_SSH_PRIVATE_KEY`, then `~/.ssh/id_ed25519`, then `~/.ssh/id_rsa`, and `stat:` each.
- Fail with a helpful message if none exist or none are usable, rather than failing opaquely inside the connection plugin.

### 14.9 Test matrix

Single-VM research projects don't need a big matrix, but we should at least prove we still work against:

- Ubuntu 22.04 LTS (primary target).
- Ubuntu 24.04 LTS (next LTS — worth testing for the 2026-2027 lifetime of this project).

Run the idempotency test against both.

## Acceptance criteria

```
[ ] `make lint` passes locally and in CI on every push
[ ] requirements.yml exists and CI fails on collection drift
[ ] `make ci-e2e` is one-click green on a fresh branch
[ ] Idempotency test is green (second run: changed=0)
[ ] deploy/expected-binary-sha256.txt exists and is asserted during prebuilt-path deploys
[ ] `ansible-lint --version` pinned in CI image
```

## Related

- `docs/phases/CRITICAL_REVIEW.md` §A1, §A2, §A6, §A7, §A8, §C5
- `docs/phases/PHASE_09_IMAGE_DIGESTS.md` (assertion task that belongs in CI too)
