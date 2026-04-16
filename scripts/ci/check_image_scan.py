#!/usr/bin/env python3
"""18-B: Assert the Trivy image-scan pipeline is wired end-to-end.

Does not invoke Trivy itself — the scan needs the network and runs in
the `image-scan` GitHub Actions job (and via `make scan-images`
locally). This check is the offline guard that future edits don't
silently drop any link in the chain.

What it validates:

  - scripts/ci/scan_images.sh exists, is executable, sets `set -e`,
    runs Trivy with --severity HIGH,CRITICAL and --ignore-unfixed,
    and sources its image list from render_compose.py --list-images.
  - render_compose.py exposes --list-images and prints one image per
    line (we actually invoke it — no network).
  - The Makefile defines a `scan-images` phony target that calls the
    wrapper.
  - .github/workflows/ci.yml has an `image-scan` job that installs
    Trivy, caches the DB, and invokes `make scan-images`.
"""
from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path

try:
    import yaml
except ImportError:
    sys.exit("pyyaml not installed. Run: make lint-install")

ROOT = Path(__file__).resolve().parents[2]
WRAPPER = ROOT / "scripts" / "ci" / "scan_images.sh"
RENDER = ROOT / "scripts" / "ci" / "render_compose.py"
MAKEFILE = ROOT / "Makefile"
WORKFLOW = ROOT / ".github" / "workflows" / "ci.yml"


def check_wrapper() -> None:
    if not WRAPPER.exists():
        sys.exit(f"missing: {WRAPPER.relative_to(ROOT)}")
    if not os.access(WRAPPER, os.X_OK):
        sys.exit(f"{WRAPPER.relative_to(ROOT)} is not executable")

    text = WRAPPER.read_text()
    required = [
        ("set -euo pipefail", "strict shell mode"),
        ("render_compose.py --list-images", "image source = render_compose"),
        ("trivy image", "invokes trivy image"),
        ("--severity HIGH,CRITICAL", "HIGH/CRITICAL severity filter"),
        ("--ignore-unfixed", "only fail on fixable vulns"),
        ("--exit-code 1", "trivy returns non-zero on findings"),
    ]
    missing = [msg for needle, msg in required if needle not in text]
    if missing:
        print(f"{WRAPPER.relative_to(ROOT)} missing expected flags:")
        for m in missing:
            print(f"  - {m}")
        sys.exit(1)

    print(f"✓ {WRAPPER.relative_to(ROOT)}: executable, strict mode, correct trivy flags")


def check_render_list_images() -> None:
    r = subprocess.run(
        [sys.executable, str(RENDER), "--list-images"],
        capture_output=True, text=True, cwd=str(ROOT),
    )
    if r.returncode != 0:
        sys.exit(f"render_compose.py --list-images failed:\n{r.stdout}\n{r.stderr}")

    lines = [ln for ln in r.stdout.splitlines() if ln.strip()]
    if not lines:
        sys.exit("render_compose.py --list-images produced no output")

    for ln in lines:
        # Images are "name[:tag]" or "namespace/name[:tag]" — colons allowed in tag portion.
        if not re.match(r"^[\w./\-]+(:[\w.\-]+)?$", ln):
            sys.exit(f"render_compose.py emitted malformed image line: {ln!r}")

    if len(lines) != len(set(lines)):
        sys.exit("render_compose.py --list-images emitted duplicates")

    print(f"✓ render_compose.py --list-images: {len(lines)} unique images")


def check_makefile_target() -> None:
    text = MAKEFILE.read_text()
    if not re.search(r"^scan-images:\s*$", text, re.MULTILINE):
        sys.exit("Makefile has no `scan-images:` target")
    if "scripts/ci/scan_images.sh" not in text:
        sys.exit("Makefile scan-images target does not call scan_images.sh")
    if not re.search(r"^\.PHONY:\s.*\bscan-images\b", text, re.MULTILINE):
        sys.exit("Makefile scan-images is not declared .PHONY")
    # And the check itself must be in the test aggregate.
    if "test-image-scan-wired" not in text:
        sys.exit("Makefile missing test-image-scan-wired target")

    print("✓ Makefile: scan-images target present, phony, and calls the wrapper")


def check_workflow() -> None:
    doc = yaml.safe_load(WORKFLOW.read_text())
    jobs = doc.get("jobs", {})
    job = jobs.get("image-scan")
    if not job:
        sys.exit("workflow ci.yml has no `image-scan` job")
    steps = job.get("steps", [])
    step_blob = yaml.safe_dump(steps)
    required = [
        ("actions/checkout", "checkout step"),
        ("actions/setup-python", "setup-python step"),
        ("actions/cache", "Trivy DB cache step"),
        ("trivy/main/contrib/install.sh", "Trivy install step"),
        ("make scan-images", "invokes make scan-images"),
    ]
    missing = [msg for needle, msg in required if needle not in step_blob]
    if missing:
        print("workflow image-scan job missing expected steps:")
        for m in missing:
            print(f"  - {m}")
        sys.exit(1)

    if job.get("timeout-minutes") is None:
        sys.exit("image-scan job has no timeout-minutes (set one to bound Trivy)")

    print("✓ workflow image-scan job: checkout + python + trivy-cache + trivy-install + make scan-images")


def main() -> int:
    check_wrapper()
    check_render_list_images()
    check_makefile_target()
    check_workflow()
    return 0


if __name__ == "__main__":
    sys.exit(main())
