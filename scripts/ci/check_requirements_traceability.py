#!/usr/bin/env python3
"""18-H: docs/REQUIREMENTS.md traceability.

Assertions:
  1. docs/REQUIREMENTS.md exists at the documented path.
  2. It carries a `Last reviewed: YYYY-MM-DD` line within the last
     365 days (mirrors THREAT_MODEL + governance freshness gates).
  3. Every `F-NN` and `NF-NN` requirement row has at least one
     backtick-quoted satisfier path containing a `/`.
  4. Every such satisfier path resolves to a file or directory that
     actually exists in the repo. Renaming a cited role/template/script
     without updating the table fails this check (the 18-H acceptance).
  5. Requirement IDs are unique within their family (no duplicate
     F-01s, no duplicate NF-03s).
  6. Phase 20 P0-3 hardening: selected requirements also get a
     *behaviour* assertion — a required substring must be found in a
     named satisfier file, so that a cosmetic "the file exists but
     does nothing" satisfier fails the check. See BEHAVIOUR_ASSERTS.

Backticked tokens without a `/` are treated as inline code (e.g.
`SIGHUP`, `make test`) and ignored.

Run with `--self-test` to execute a negative regression: each
BEHAVIOUR_ASSERTS entry is re-run against a synthetically emptied
copy of the cited file and must fail. This guards against the
checker silently regressing back to pure existence checks.
"""
from __future__ import annotations

import datetime
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DOC = ROOT / "docs" / "REQUIREMENTS.md"

ID_RE = re.compile(r"^\s*\|\s*(F-\d{2}|NF-\d{2})\s*\|", re.MULTILINE)
ROW_RE = re.compile(r"^\s*\|\s*(F-\d{2}|NF-\d{2})\s*\|(.*)$", re.MULTILINE)
BACKTICK_RE = re.compile(r"`([^`]+)`")

# Phase 20 P0-3: per-requirement behavioural assertions. Each tuple is
# (req_id, repo-relative file, required substring, human-readable why).
# A missing substring fails the check — proof that the satisfier's
# mechanism, not just its filename, is present.
BEHAVIOUR_ASSERTS: list[tuple[str, str, str, str]] = [
    (
        "NF-04",
        "deploy/roles/03-ja4proxy-deploy/tasks/main.yml",
        "cosign verify-blob",
        "NF-04 claims cosign-verified provenance; the deploy role must "
        "invoke `cosign verify-blob` before starting the service.",
    ),
    (
        "NF-04",
        "deploy/inventory/group_vars/all.yml",
        "-trimpath",
        "NF-04 claims reproducible build flags; "
        "`ja4proxy_go_build_flags` in group_vars must contain "
        "`-trimpath` (it is injected via GOFLAGS by role 02).",
    ),
    (
        "NF-05",
        "scripts/ci/scan_images.sh",
        "--exit-code 1",
        "NF-05 claims the Trivy scan fails on HIGH/CRITICAL; the "
        "wrapper must invoke Trivy with `--exit-code 1`.",
    ),
    (
        "NF-05",
        "deploy/roles/09-image-digests/tasks/main.yml",
        "expected-image-digests.yml",
        "NF-05 claims pin-file enforcement; role 09 must load "
        "`deploy/expected-image-digests.yml` and assert the live "
        "pulled digest matches.",
    ),
    # The three checks below together prove the Phase 20 P0-2 assertion
    # block is actually wired — not just that the filename appears in a
    # comment. Loading via include_vars + indexing both sides of the
    # comparison + calling `ansible.builtin.assert` are each necessary;
    # dropping any of them silently neuters the gate.
    (
        "NF-05",
        "deploy/roles/09-image-digests/tasks/main.yml",
        "ja4proxy_expected_digests",
        "NF-05 P0-2: role 09 must load the pin file into the "
        "`ja4proxy_expected_digests` fact (via include_vars) so the "
        "assertion has both sides to compare.",
    ),
    (
        "NF-05",
        "deploy/roles/09-image-digests/tasks/main.yml",
        "resolved_digests[item]",
        "NF-05 P0-2: the assertion must index the live `resolved_digests` "
        "dict per-image. Without this, the gate does not compare the "
        "*pulled* digest against the pin.",
    ),
    (
        "NF-05",
        "deploy/roles/09-image-digests/tasks/main.yml",
        "ansible.builtin.assert",
        "NF-05 P0-2: the digest-match check must use "
        "`ansible.builtin.assert` so a mismatch aborts the play. A "
        "`debug` or conditional log would allow tag-mutation to slip "
        "through silently.",
    ),
]


def _run_behaviour_asserts(overrides: dict[str, str] | None = None) -> list[str]:
    """Check each BEHAVIOUR_ASSERTS entry. `overrides` lets --self-test
    inject a synthetic empty body for a given path without touching
    the working tree."""
    errors: list[str] = []
    for req_id, rel, needle, why in BEHAVIOUR_ASSERTS:
        target = ROOT / rel
        if overrides and rel in overrides:
            body = overrides[rel]
        elif not target.exists():
            errors.append(f"{req_id}: behaviour satisfier `{rel}` is missing")
            continue
        else:
            body = target.read_text()
        if needle not in body:
            errors.append(
                f"{req_id}: behaviour assertion failed — `{needle}` not "
                f"found in `{rel}`. {why}"
            )
    return errors


def _self_test() -> int:
    """Negative regression: emptying each cited file must trip the
    corresponding behaviour assertion."""
    failures: list[str] = []
    for _req_id, rel, needle, _why in BEHAVIOUR_ASSERTS:
        errs = _run_behaviour_asserts(overrides={rel: ""})
        if not any(needle in e and rel in e for e in errs):
            failures.append(
                f"self-test: emptying `{rel}` did not trip the `{needle}` "
                f"assertion — checker is too permissive"
            )
    if failures:
        print(f"{len(failures)} self-test failure(s):")
        for f in failures:
            print(f"  {f}")
        return 1
    print(
        f"✓ self-test: all {len(BEHAVIOUR_ASSERTS)} behaviour assertion(s) "
        f"trip when their satisfier is emptied"
    )
    return 0


def main() -> int:
    if "--self-test" in sys.argv[1:]:
        return _self_test()

    errors: list[str] = []

    if not DOC.exists():
        sys.exit(f"missing: {DOC.relative_to(ROOT)} (18-H)")

    text = DOC.read_text()

    # 2. Freshness.
    m = re.search(r"^Last reviewed:\s*(\d{4}-\d{2}-\d{2})", text, re.MULTILINE)
    if not m:
        errors.append("missing or malformed `Last reviewed: YYYY-MM-DD` line")
    else:
        try:
            last = datetime.date.fromisoformat(m.group(1))
            age = (datetime.date.today() - last).days
            if age > 365:
                errors.append(f"Last reviewed {last} is {age} days old (>365)")
            if age < 0:
                errors.append(f"Last reviewed {last} is in the future")
        except ValueError as exc:
            errors.append(f"Last reviewed unparseable: {exc}")

    # 3 + 4 + 5. Walk each requirement row.
    seen_ids: set[str] = set()
    rows_found = 0
    for match in ROW_RE.finditer(text):
        req_id, rest = match.group(1), match.group(2)
        rows_found += 1

        if req_id in seen_ids:
            errors.append(f"{req_id}: duplicate ID")
        seen_ids.add(req_id)

        # The ID is in column 1; satisfiers are in the *last* pipe-delimited
        # cell. Split on `|`, strip empty trailing cell from a closing pipe.
        cells = [c.strip() for c in rest.split("|")]
        if cells and cells[-1] == "":
            cells = cells[:-1]
        if not cells:
            errors.append(f"{req_id}: row has no requirement / satisfier cells")
            continue
        satisfier_cell = cells[-1]

        tokens = BACKTICK_RE.findall(satisfier_cell)
        paths = [t for t in tokens if "/" in t]
        if not paths:
            errors.append(
                f"{req_id}: no backticked satisfier path containing `/` "
                f"in last cell"
            )
            continue

        for raw in paths:
            # Reject absolute paths and parent-escapes — satisfiers must be
            # repo-relative.
            if raw.startswith("/") or ".." in Path(raw).parts:
                errors.append(f"{req_id}: satisfier `{raw}` must be repo-relative")
                continue
            target = ROOT / raw
            if not target.exists():
                errors.append(f"{req_id}: satisfier `{raw}` does not exist")

    if rows_found == 0:
        errors.append("no F-NN or NF-NN rows parsed — table format broken?")

    errors.extend(_run_behaviour_asserts())

    if errors:
        print(f"{len(errors)} requirements-traceability issue(s):")
        for e in errors:
            print(f"  {e}")
        return 1

    print(
        f"✓ docs/REQUIREMENTS.md: {rows_found} requirements, all satisfier "
        f"paths resolve, fresh (<365d), {len(BEHAVIOUR_ASSERTS)} behaviour "
        f"assertion(s) pass"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
