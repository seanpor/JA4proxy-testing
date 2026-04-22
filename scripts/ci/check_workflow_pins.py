#!/usr/bin/env python3
"""18-E: Every `uses: org/repo@...` in .github/workflows/*.yml must
be pinned to a 40-char commit SHA — not a tag, not a branch.

Scorecard's `Pinned-Dependencies` check grades the same thing; this
offline guard catches regressions in the same PR that introduces
them, instead of waiting for the weekly Scorecard run.

Pattern expected (recommended by GitHub and OpenSSF):

    uses: actions/checkout@<40-hex-sha>  # v4.3.1

The trailing `# <version>` comment is required so a human or
Dependabot can tell what release the SHA resolves to without
another API call.

Phase 20 P1-7 hardening: when the `gh` CLI is available and
authenticated, also verify that each SHA actually resolves to the
tag in the trailing comment. Without this, a PR with a mismatched
comment (`actions/checkout@<any-hex> # v99.99.99`) slips through.
Offline mode (no `gh`, or `--offline` flag, or CI_OFFLINE=1 env)
prints a single info line and skips the tag-resolution step so that
`make test` keeps working on a laptop with no network.

Local actions (`uses: ./local/path`) are exempted. So are Docker-image
references (`uses: docker://...`), which are pinned separately by 18-B.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WORKFLOW_DIR = ROOT / ".github" / "workflows"

SHA_RE = re.compile(r"^[0-9a-f]{40}$")
# `uses:` line (may be indented, may quote the value)
USES_RE = re.compile(
    r"""^\s*-?\s*uses:\s*['"]?(?P<ref>[^'"#\s]+)['"]?\s*(?P<comment>\#.*)?$"""
)
# Extract the version token from a trailing comment like `# v4.3.1` or
# `# v1` or `# 2.1.0`. Captures the token verbatim for tag lookup.
COMMENT_VERSION_RE = re.compile(r"#\s*(v?\d[\w.\-]*)")


def _gh_available(offline: bool) -> bool:
    if offline or os.environ.get("CI_OFFLINE") == "1":
        return False
    return shutil.which("gh") is not None


_tag_cache: dict[tuple[str, str], str | None] = {}


def _resolve_tag_sha(owner_repo: str, tag: str) -> str | None:
    """Return the commit SHA that owner_repo's `tag` refers to, or None
    if gh says no such tag. Caches per (repo, tag). An annotated tag
    (object.type == 'tag') is dereferenced to its underlying commit."""
    key = (owner_repo, tag)
    if key in _tag_cache:
        return _tag_cache[key]
    try:
        out = subprocess.run(
            ["gh", "api", f"repos/{owner_repo}/git/ref/tags/{tag}"],
            capture_output=True, text=True, timeout=15, check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        _tag_cache[key] = None
        return None
    if out.returncode != 0:
        _tag_cache[key] = None
        return None
    try:
        payload = json.loads(out.stdout)
    except json.JSONDecodeError:
        _tag_cache[key] = None
        return None
    obj = payload.get("object") or {}
    sha, obj_type = obj.get("sha"), obj.get("type")
    # Lightweight tag → object.type == "commit". Annotated tag → "tag";
    # dereference one more step to get the underlying commit.
    if obj_type == "tag":
        deref = subprocess.run(
            ["gh", "api", f"repos/{owner_repo}/git/tags/{sha}"],
            capture_output=True, text=True, timeout=15, check=False,
        )
        if deref.returncode == 0:
            try:
                obj2 = (json.loads(deref.stdout).get("object") or {})
                sha = obj2.get("sha", sha)
            except json.JSONDecodeError:
                pass
    _tag_cache[key] = sha
    return sha


def check_file(path: Path, verify_tags: bool) -> list[str]:
    errors: list[str] = []
    for lineno, raw in enumerate(path.read_text().splitlines(), start=1):
        m = USES_RE.match(raw)
        if not m:
            continue
        ref = m.group("ref")
        comment = (m.group("comment") or "").strip()

        # Local composite action — exempt.
        if ref.startswith("./") or ref.startswith("../"):
            continue
        # Docker image reference — pinned separately.
        if ref.startswith("docker://"):
            continue

        if "@" not in ref:
            errors.append(f"{path.name}:{lineno}: `uses: {ref}` has no @ref — refuse ambiguous pins")
            continue
        repo, at = ref.rsplit("@", 1)
        if not SHA_RE.match(at):
            errors.append(
                f"{path.name}:{lineno}: `{ref}` pins to tag/branch {at!r}, not a 40-char commit SHA"
            )
            continue
        if not comment or not re.match(r"#\s*v?\d", comment):
            errors.append(
                f"{path.name}:{lineno}: `{ref}` missing trailing `# <version>` comment (got {comment!r})"
            )
            continue

        if verify_tags:
            # Strip any sub-action path, e.g.
            # github/codeql-action/upload-sarif → github/codeql-action.
            owner_repo = "/".join(repo.split("/", 2)[:2])
            tag_match = COMMENT_VERSION_RE.search(comment)
            if not tag_match:
                continue
            tag = tag_match.group(1)
            resolved = _resolve_tag_sha(owner_repo, tag)
            if resolved is None:
                errors.append(
                    f"{path.name}:{lineno}: `{owner_repo}` tag `{tag}` did not "
                    f"resolve via gh (rate limit / deleted tag / auth gap?)"
                )
            elif resolved.lower() != at.lower():
                errors.append(
                    f"{path.name}:{lineno}: `{ref}` comment says `{tag}` but "
                    f"`{owner_repo}` {tag} resolves to {resolved} — mismatched pin"
                )
    return errors


def main() -> int:
    offline = "--offline" in sys.argv[1:]
    verify_tags = _gh_available(offline=offline)

    if not WORKFLOW_DIR.is_dir():
        sys.exit(f"missing workflows dir: {WORKFLOW_DIR.relative_to(ROOT)}")

    all_errors: list[str] = []
    files = sorted(WORKFLOW_DIR.glob("*.yml")) + sorted(WORKFLOW_DIR.glob("*.yaml"))
    if not files:
        sys.exit("no workflow files found under .github/workflows/")

    for f in files:
        all_errors.extend(check_file(f, verify_tags=verify_tags))

    if all_errors:
        print("workflow action pins not compliant (18-E):")
        for e in all_errors:
            print(f"  - {e}")
        sys.exit(1)

    total_uses = 0
    for f in files:
        total_uses += sum(1 for ln in f.read_text().splitlines() if USES_RE.match(ln))
    mode = (
        "with SHA↔tag verification" if verify_tags
        else "(offline — tag verification skipped)"
    )
    print(
        f"✓ all {total_uses} `uses:` refs across {len(files)} workflow(s) "
        f"are SHA-pinned with version comments {mode}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
