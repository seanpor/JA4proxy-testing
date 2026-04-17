# AGENTS.md

Operating contract for any AI agent (Claude Code, Codex, Cursor, etc.) or
human contributor working in this repo. Consume this *in addition* to
`CLAUDE.md` (project guidance) and `README.md` (user-facing docs).

## Pre-merge / pre-push contract — non-negotiable

Before opening a PR to `main`, before merging to `main`, and after merging
to `main`, the following must all be green:

1. **`make lint`** — yamllint, ansible-lint (moderate profile),
   `ansible-playbook --syntax-check`, shellcheck, jinja2 parse, plaintext
   secret scan. Runs in seconds; no VM required.
2. **`make test`** — everything in `make lint` plus structural cross-checks
   (role refs resolve, group_vars coverage, compose template renders,
   digest-pin regex self-test, A1 secrets-path regression, Makefile phony
   audit). Still no VM required.
3. **GitHub Actions CI** (`.github/workflows/ci.yml`) — must report green
   on the PR commit *and* on the post-merge `main` commit. If the
   post-merge run goes red, treat it as a P0: revert or fix-forward
   immediately, do not pile new commits on top.

`main` is branch-protected:
- `lint-and-test` is a required status check (strict: branch must be up
  to date before merge)
- force pushes, deletions, and non-linear history are blocked
- unresolved PR conversations block merge
- admins are not enforced (so you can still push directly in a true
  emergency — but the default path is a PR)

Bootstrap once per clone:

```
make lint-install   # creates .venv-dev/ with pinned ansible-lint, yamllint, jinja2
```

After that, both targets are runnable from a cold shell.

Two Go-side tools are also expected on `$PATH` for full build-time
coverage — both are skip-with-warning if absent, so you can still
deploy without them, but CI on this repo is an offline wiring check
only (neither tool is invoked here):

```
go install github.com/CycloneDX/cyclonedx-gomod/cmd/cyclonedx-gomod@latest  # 18-A SBOM
go install golang.org/x/vuln/cmd/govulncheck@latest                         # 18-C vuln scan
```

## Order of operations for any change

1. Branch off `main` (or `review-fixes` while it's still open).
2. Make the change.
3. `make lint && make test` locally — must pass.
4. Commit, push, open PR.
5. Wait for the GitHub Actions `ci` job to go green on the PR.
6. Merge.
7. Watch the `ci` run on the merge commit to `main`. Confirm green.

If step 3 fails: fix the code or, if a check is genuinely wrong for the
project, update the check (in `scripts/ci/`) or its config (`.yamllint`,
`.ansible-lint`) in the same PR, with a justification line in the commit
message. Don't `--no-verify` past it.

## When you add or change something that needs a new check

If a change introduces a new invariant (a new image short-name, a new
phase role, a new templated variable, a new shell script, a new
secrets-handling code path), add or extend the matching check under
`scripts/ci/` so future regressions fail `make test`. The existing checks
are the worked examples — mirror their structure.

## Things that are out of scope for this repo

- Production K8s/Helm work — that lives in the sibling `JA4proxy4` repo.
- Raising the default `ja4proxy_dial` above 0 — monitor-first is a
  deliberate design constraint (see `CLAUDE.md`).
- Anything before Phase 10 binding a public port or opening UFW for
  80/443 — preserve the locked → verified → live invariant.
