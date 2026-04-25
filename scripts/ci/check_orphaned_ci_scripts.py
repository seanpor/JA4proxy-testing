#!/usr/bin/env python3
"""Phase 21-I: orphan-check gate.

Fails CI if any `scripts/ci/check_*.py` file exists on disk but is
never invoked by `make test` or `make lint` (transitively, including
prerequisite chains).

Why:
  21-E ensures CI doesn't run anything the local pre-push contract
  can't reproduce. 21-I closes the symmetric gap from the other side:
  a contributor adds `check_new_thing.py`, forgets to wire a
  `test-new-thing` target into `make test`, and the file ships dead.
  The check exists, the angry reviewer reads its name in the tree
  and assumes it gates something, and CI runs forever without it.

  Today every check_*.py happens to be wired. This gate makes that
  property mechanical so it doesn't quietly stop being true.

Method:
  1. List every `scripts/ci/check_*.py` file.
  2. Ask `make` itself for the dry-run command surface of `test` and
     `lint` (`make -n`). The dry-run is authoritative: it traces
     prereq chains that a regex over the Makefile cannot, and it
     follows targets defined in deploy/Makefile too.
  3. Diff. Anything on disk and not in the dry-run output fails.

Offline:
  No network. Falls back to a warning + exit 0 if `make` itself is
  not on PATH (mirrors 21-B's `gh` fallback) so a bare-checkout
  developer loop doesn't go red on a missing tool.

Self-exemption:
  This file deliberately invokes itself only via the Makefile, not
  directly — the gate gates itself.
"""
from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CHECKS_DIR = ROOT / "scripts" / "ci"


def _on_disk() -> set[str]:
    return {p.name for p in CHECKS_DIR.glob("check_*.py")}


def _make_dryrun_text(targets: list[str]) -> str | None:
    if shutil.which("make") is None:
        return None
    out = []
    for t in targets:
        r = subprocess.run(
            ["make", "-n", t],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
        )
        # `make -n` may exit non-zero if a downstream recipe would
        # fail at runtime; the stdout we got before that is still
        # the authoritative command surface for our purposes.
        out.append(r.stdout)
    return "\n".join(out)


def main() -> int:
    on_disk = _on_disk()
    if not on_disk:
        sys.exit("scripts/ci/ has no check_*.py files — repo layout broken")

    dryrun = _make_dryrun_text(["test", "lint"])
    if dryrun is None:
        print(
            "✓ orphan-check gate: `make` not on PATH — skipping (dev "
            "loop tolerated; CI installs make)"
        )
        return 0

    orphans = sorted(name for name in on_disk if name not in dryrun)
    if orphans:
        print(f"{len(orphans)} orphan check_*.py file(s) on disk but not invoked by `make test`/`make lint`:")
        for o in orphans:
            print(f"  ✗ scripts/ci/{o}")
        print(
            "Either wire each into a Makefile target reachable from "
            "`make test` (or `make lint`) — see the existing "
            "`test-<name>:` targets for the pattern — or delete the "
            "file. A check that nothing runs is governance theatre."
        )
        return 1

    print(f"✓ orphan-check gate: {len(on_disk)} check_*.py file(s), all invoked from `make test`/`make lint`")
    return 0


if __name__ == "__main__":
    sys.exit(main())
