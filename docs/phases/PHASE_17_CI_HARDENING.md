# Phase 17 — CI hardening and bug fixes

Last reviewed: 2026-04-16

Fixes real bugs found during the Phase 16 review audit and adds
high-value CI checks that catch deploy-time failures offline.

---

## 17-A — Fix missing handlers in roles 11 and 12

**Bug.** Role 11 (data-export) notifies `reload systemd` twice; role 12
(secrets-rotation) notifies `restart ja4proxy` and
`restart compose stack`. Neither role has a `handlers/main.yml` — the
playbook will fail at deploy time when the handler fires.

**Files.**
- `deploy/roles/11-data-export/handlers/main.yml` — create with
  `reload systemd` handler (`systemd: daemon_reload=yes`).
- `deploy/roles/12-secrets-rotation/handlers/main.yml` — create with
  `restart ja4proxy` and `restart compose stack` handlers.

**CI hook.** New `scripts/ci/check_handlers.py`: scan every role's
`tasks/main.yml` for `notify:` lines, verify the named handler exists
in that role's `handlers/main.yml` (or a playbook-level handler).

**Acceptance.** `make test-handlers` passes; `ansible-playbook
--syntax-check` still green.

---

## 17-B — Remove duplicate files

**Bug.** 8 files exist as identical copies in two locations:

- `deploy/files/grafana-dashboards/*.json` (7 files) duplicated in
  `deploy/roles/05-data-collection/files/grafana-dashboards/`
- `deploy/files/scripts/health-check.sh` duplicated in
  `deploy/roles/06-operational-security/files/scripts/`

One copy is authoritative; the other is dead weight that will silently
diverge on the next edit.

**Files.** Remove the `deploy/files/` copies (the role copies are what
Ansible actually deploys). Update any references.

**CI hook.** New `scripts/ci/check_duplicate_files.py`: hash every file
under `deploy/files/` and `deploy/roles/*/files/`, flag identical pairs.

**Acceptance.** `make test-duplicates` passes with zero duplicates.

---

## 17-C — Handler cross-reference validation

**Scope.** CI check that every `notify:` in every role resolves to a
defined handler, and every defined handler is notified by at least one
task (dead handler = cleanup signal).

**Files.**
- `scripts/ci/check_handlers.py` (created in 17-A, extended here if
  17-A only covers the fix).

**Acceptance.** Deliberately adding a bogus `notify: fake` to a role
causes `make test-handlers` to fail.

---

## 17-D — Relative path validation

**Scope.** Several roles use `src: "{{ playbook_dir }}/../scripts/..."`.
A CI check should resolve these paths (substituting the known playbook
directory) and verify the target files exist.

**Files.**
- `scripts/ci/check_relative_paths.py`

**Acceptance.** Renaming a referenced script without updating the role
causes `make test-relative-paths` to fail.

---

## 17-E — Docker Compose dependency DAG validation

**Scope.** Render `docker-compose.yml.j2` with sample vars and verify
every `depends_on:` target names a service that exists in the same
compose file.

**Files.**
- Extend `scripts/ci/render_compose.py` (already renders the template)
  to parse `depends_on:` and cross-check against the service list.

**Acceptance.** Adding `depends_on: [nonexistent]` to a service causes
`make test-compose` to fail.

---

## 17-F — Markdown internal link validation

**Scope.** Parse all `.md` files for relative links
(markdown link syntax) and verify the target file exists. Anchor
links are validated where feasible.

**Files.**
- `scripts/ci/check_markdown_links.py`

**Acceptance.** A broken relative link causes
`make test-markdown-links` to fail.

---

## Deferred (not in this phase)

- PromQL expression validation — hard to do offline, low risk.
- Unused variable detection — rare problem in practice.
- Port conflict detection — no actual conflicts found.
- Grafana dashboard schema validation — dashboards fixable via UI.
- `changed_when` enforcement on shell/command tasks — ansible-lint
  partially covers this already.
