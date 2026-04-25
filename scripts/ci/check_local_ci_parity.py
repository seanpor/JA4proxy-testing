#!/usr/bin/env python3
"""Phase 21-E: local-vs-CI parity audit.

Fails CI if `.github/workflows/ci.yml` runs a check that is not
reachable via the local pre-push contract (`make lint`, `make test`,
`make scan-images`).

Context:
  The repo claims (README, `AGENTS.md`, the top of `Makefile`) that
  `make lint && make test` locally is the pre-push contract and
  `make lint-all` "matches what CI checks end-to-end". If `ci.yml`
  runs any check that the Makefile does not — a `scripts/ci/*.py`
  invocation, a `trivy` invocation, anything substantive — that claim
  silently becomes false: a developer can satisfy the local contract
  and still surprise-red CI.

  Phase 20's P1-8 remediation added a compose-SBOM Trivy scan in the
  `image-scan` job (`ci.yml:91-101`). It was correct to land that
  step — it's what gives the shipped SBOM a consumer — but *only* in
  CI. Locally there is no equivalent in `make scan-images` or
  `make lint-all`, so it's the first instance of the drift this
  checker targets.

Method:
  1. Harvest every `scripts/ci/*.py` filename and every `trivy`
     command referenced from the Makefile (directly or transitively
     through `make` recipes).
  2. Harvest the same tokens from `.github/workflows/ci.yml`'s
     `run:` blocks.
  3. Flag anything in CI that isn't reachable locally.

What this check intentionally does NOT flag:
  - Setup / tooling installs (`pip install`, `apt-get install`,
    `ansible-galaxy`, `curl | sh`). These are environmental, not
    verification steps.
  - Cache / artifact actions. These are infrastructure.
  - Checks *only* in the Makefile but absent from CI. That direction
    is a less serious gap (CI is looser than local) and has its own
    trade-offs; flagging it would constrain CI from legitimately
    dropping flaky checks. If we want the reverse direction, it
    should be its own deliberate gate.

Offline:
  This check is 100% offline (pure text parsing of two repo files);
  no `gh api` calls, no network.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CI_YML = ROOT / ".github" / "workflows" / "ci.yml"
MAKEFILE = ROOT / "Makefile"
DEPLOY_MAKEFILE = ROOT / "deploy" / "Makefile"

SCRIPT_RE = re.compile(r"scripts/ci/([A-Za-z0-9_]+\.py)")
# Intentionally same-line only: `\s+` would span the newline between
# `path: ~/.cache/trivy\n          key: trivy-db-…`, producing a bogus
# `trivy key` token.
TRIVY_RE = re.compile(r"\btrivy[ \t]+(\w+)")


def _extract_tokens(text: str) -> set[str]:
    """Return a set of atomic verification tokens found in `text`.
    Tokens are normalised so the same check invoked two different
    ways (with/without `python3` prefix, different quote style) still
    collides."""
    tokens: set[str] = set()
    for m in SCRIPT_RE.findall(text):
        tokens.add(f"script:{m}")
    for m in TRIVY_RE.findall(text):
        tokens.add(f"trivy:{m}")
    return tokens


def _makefile_tokens() -> set[str]:
    """Union of tokens from the root + deploy Makefiles and the shell
    scripts those Makefiles delegate to (scan_images.sh at minimum)."""
    tokens: set[str] = set()
    for p in (MAKEFILE, DEPLOY_MAKEFILE):
        if p.exists():
            tokens |= _extract_tokens(p.read_text())
    # Follow the Make → shell-wrapper hop: scan_images.sh is how
    # `make scan-images` actually invokes Trivy.
    wrapper = ROOT / "scripts" / "ci" / "scan_images.sh"
    if wrapper.exists():
        tokens |= _extract_tokens(wrapper.read_text())
    return tokens


def _ci_tokens() -> set[str]:
    """Tokens appearing in ci.yml's `run:` surface. We don't try to
    parse YAML — a text scan is sufficient because the regexes already
    match the salient patterns in comments and commands alike, and
    we'd rather over-flag a false positive than silently ignore a
    hidden invocation."""
    return _extract_tokens(CI_YML.read_text())


def main() -> int:
    if not CI_YML.exists():
        sys.exit(f"missing: {CI_YML.relative_to(ROOT)}")
    if not MAKEFILE.exists():
        sys.exit(f"missing: {MAKEFILE.relative_to(ROOT)}")

    mk = _makefile_tokens()
    ci = _ci_tokens()

    ci_only = sorted(ci - mk)
    errors: list[str] = []
    for tok in ci_only:
        kind, name = tok.split(":", 1)
        if kind == "script":
            errors.append(
                f"ci.yml invokes `scripts/ci/{name}` but no Makefile "
                f"target does. Either wire it into `make test` (or "
                f"`make lint-all`) or remove it from CI — the pre-push "
                f"contract currently cannot reproduce this check."
            )
        elif kind == "trivy":
            errors.append(
                f"ci.yml runs `trivy {name}` but no Makefile target "
                f"or `scan_images.sh` invokes `trivy {name}`. The "
                f"`make lint-all` docstring claims CI parity; add the "
                f"equivalent local step or narrow the claim."
            )

    if errors:
        print(f"{len(errors)} local-vs-CI parity issue(s):")
        for e in errors:
            print(f"  ✗ {e}")
        return 1

    script_hits = sum(1 for t in ci if t.startswith("script:"))
    trivy_hits = sum(1 for t in ci if t.startswith("trivy:"))
    if script_hits == 0 and trivy_hits == 0:
        print(
            "✓ ci.yml has no direct scripts/ci/*.py or trivy invocations — "
            "all verification flows through `make lint`/`test`/`scan-images`"
        )
    else:
        print(
            f"✓ ci.yml parity: {script_hits} scripts/ci/*.py + {trivy_hits} "
            f"trivy invocation(s) all reachable from `make lint`/`test`/"
            f"`scan-images`"
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
