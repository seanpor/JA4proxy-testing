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

Local actions (`uses: ./local/path`) are exempted. So are Docker-image
references (`uses: docker://...`), which are pinned separately by 18-B.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WORKFLOW_DIR = ROOT / ".github" / "workflows"

SHA_RE = re.compile(r"^[0-9a-f]{40}$")
# `uses:` line (may be indented, may quote the value)
USES_RE = re.compile(
    r"""^\s*-?\s*uses:\s*['"]?(?P<ref>[^'"#\s]+)['"]?\s*(?P<comment>\#.*)?$"""
)


def check_file(path: Path) -> list[str]:
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
        # Strip any sub-action path (github/codeql-action/upload-sarif → github/codeql-action).
        _ = repo
        if not SHA_RE.match(at):
            errors.append(
                f"{path.name}:{lineno}: `{ref}` pins to tag/branch {at!r}, not a 40-char commit SHA"
            )
            continue
        if not comment or not re.match(r"#\s*v?\d", comment):
            errors.append(
                f"{path.name}:{lineno}: `{ref}` missing trailing `# <version>` comment (got {comment!r})"
            )
    return errors


def main() -> int:
    if not WORKFLOW_DIR.is_dir():
        sys.exit(f"missing workflows dir: {WORKFLOW_DIR.relative_to(ROOT)}")

    all_errors: list[str] = []
    files = sorted(WORKFLOW_DIR.glob("*.yml")) + sorted(WORKFLOW_DIR.glob("*.yaml"))
    if not files:
        sys.exit("no workflow files found under .github/workflows/")

    for f in files:
        all_errors.extend(check_file(f))

    if all_errors:
        print("workflow action pins not compliant (18-E):")
        for e in all_errors:
            print(f"  - {e}")
        sys.exit(1)

    total_uses = 0
    for f in files:
        total_uses += sum(1 for ln in f.read_text().splitlines() if USES_RE.match(ln))
    print(f"✓ all {total_uses} `uses:` refs across {len(files)} workflow(s) are SHA-pinned with version comments")
    return 0


if __name__ == "__main__":
    sys.exit(main())
