#!/usr/bin/env python3
"""18-B + 18-B-2: Assert the Trivy image-scan pipeline is wired end-to-end.

Does not invoke Trivy itself — the scan needs the network and runs in
the `image-scan` GitHub Actions job (and via `make scan-images`
locally). This check is the offline guard that future edits don't
silently drop any link in the chain.

What it validates:

  - scripts/ci/scan_images.sh exists, is executable, sets `set -e`,
    runs Trivy with --ignore-unfixed, scans HIGH+CRITICAL in a single
    blocking pass (--severity HIGH,CRITICAL --exit-code 1), and sources
    its image list from render_compose.py --list-images.
  - render_compose.py exposes --list-images and prints one image per
    line (we actually invoke it — no network).
  - The Makefile defines a `scan-images` phony target that calls the
    wrapper.
  - .github/workflows/ci.yml has an `image-scan` job that installs
    Trivy, caches the DB, and invokes `make scan-images`.
  - .trivyignore (if present) has a `# expires: YYYY-MM-DD` comment
    immediately preceding every CVE line, and no entry is expired.
    This forces a periodic decision on each allowlisted finding.
"""
from __future__ import annotations

import datetime as dt
import os
import re
import subprocess
import sys
from pathlib import Path

# 21-H: severity classifier shared with check_cve_reachability.py so
# the two gates can't disagree on a borderline severity call.
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _trivyignore import classify as _classify_trivyignore
from _trivyignore import parse_policy_ceilings as _parse_policy_ceilings

try:
    import yaml
except ImportError:
    sys.exit("pyyaml not installed. Run: make lint-install")

# 21-H severity-response ceilings, codifying the .trivyignore header:
#   CRITICAL → fix within 30 days
#   HIGH     → fix within 90 days
# An entry whose `# expires:` is further out than the ceiling
# silently widens the policy. We refuse — re-justify on the policy
# cadence or get the upstream fix.
SEVERITY_MAX_DAYS = {"CRITICAL": 30, "HIGH": 90}

ROOT = Path(__file__).resolve().parents[2]
WRAPPER = ROOT / "scripts" / "ci" / "scan_images.sh"
RENDER = ROOT / "scripts" / "ci" / "render_compose.py"
MAKEFILE = ROOT / "Makefile"
WORKFLOW = ROOT / ".github" / "workflows" / "ci.yml"
IGNOREFILE = ROOT / ".trivyignore"

CVE_RE = re.compile(r"^(CVE-\d{4}-\d{4,})\s*$")
EXPIRES_RE = re.compile(r"^#\s*expires:\s*(\d{4}-\d{2}-\d{2})\s*$")


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
        ("--severity HIGH,CRITICAL", "HIGH+CRITICAL blocking pass"),
        ("--ignore-unfixed", "only fail on fixable vulns"),
        ("--exit-code 1", "returns non-zero on findings"),
        ("--ignorefile", "honours .trivyignore allowlist"),
    ]
    missing = [msg for needle, msg in required if needle not in text]
    if missing:
        print(f"{WRAPPER.relative_to(ROOT)} missing expected flags:")
        for m in missing:
            print(f"  - {m}")
        sys.exit(1)

    # Guard against a silent regression to the old two-pass model where
    # HIGH was informational (`--exit-code 0`). Since 18-B-2 both
    # severities block.
    if "--exit-code 0" in text:
        sys.exit(
            f"{WRAPPER.relative_to(ROOT)}: found `--exit-code 0` — 18-B-2 merged "
            "HIGH into the blocking pass; remove the informational pass"
        )

    print(f"✓ {WRAPPER.relative_to(ROOT)}: executable, strict mode, HIGH+CRITICAL blocking")


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


def check_trivyignore() -> None:
    """Enforce the `# expires: YYYY-MM-DD` convention on .trivyignore.

    Rule: every non-comment, non-blank line (the CVE itself) must be
    immediately preceded — ignoring blank lines only — by at least one
    `# expires: YYYY-MM-DD` comment within the same paragraph-block.
    No entry may be expired as of today.
    """
    if not IGNOREFILE.exists():
        print("✓ .trivyignore: absent (no allowlist — strictest posture)")
        return

    today = dt.date.today()
    errors: list[str] = []
    entries: list[tuple[int, str, dt.date | None]] = []
    pending_expiry: dt.date | None = None
    pending_expiry_line: int | None = None

    # 21-H: severity classification of every uncommented CVE so we can
    # apply the policy ceiling per entry below.
    text = IGNOREFILE.read_text()
    classification = _classify_trivyignore(text)

    # 21-K: cross-check the SEVERITY_MAX_DAYS constant against the
    # `.trivyignore` policy header. The constant is the runtime value
    # (no init-time work in the hot path); this assertion is the
    # drift-killer that catches the case where the header is edited
    # but the constant is stale (or vice versa).
    parsed = _parse_policy_ceilings(text)
    if not parsed:
        sys.exit(
            f"{IGNOREFILE.name}: policy header missing or malformed "
            "— expected lines like `#   CRITICAL → … fix within 30` "
            "and `#   HIGH → … fix within 90`. Restore the header so "
            "the 21-H ceiling constant has a documented source."
        )
    if parsed != SEVERITY_MAX_DAYS:
        sys.exit(
            f"{IGNOREFILE.name}: policy header says "
            f"{parsed!r} but check_image_scan.py SEVERITY_MAX_DAYS "
            f"is {SEVERITY_MAX_DAYS!r}. The two must agree — edit "
            "one to match the other so the documented policy and the "
            "enforced ceiling are the same number."
        )

    for lineno, raw in enumerate(text.splitlines(), start=1):
        line = raw.strip()
        if not line:
            # Blank line resets the block — any pending expiry dies here.
            pending_expiry = None
            pending_expiry_line = None
            continue
        if line.startswith("#"):
            m = EXPIRES_RE.match(line)
            if m:
                try:
                    pending_expiry = dt.date.fromisoformat(m.group(1))
                except ValueError:
                    errors.append(
                        f"{IGNOREFILE.name}:{lineno}: malformed expiry date {m.group(1)!r}"
                    )
                    pending_expiry = None
                else:
                    pending_expiry_line = lineno
            continue
        m = CVE_RE.match(line)
        if not m:
            errors.append(f"{IGNOREFILE.name}:{lineno}: unrecognised entry {line!r}")
            continue
        cve = m.group(1)
        entries.append((lineno, cve, pending_expiry))
        if pending_expiry is None:
            errors.append(
                f"{IGNOREFILE.name}:{lineno}: {cve} has no `# expires: YYYY-MM-DD` comment in its block"
            )
        elif pending_expiry < today:
            errors.append(
                f"{IGNOREFILE.name}:{lineno}: {cve} expired on {pending_expiry.isoformat()} "
                f"(today is {today.isoformat()}) — fix, re-justify with a new expiry, or remove"
            )
        else:
            # 21-H severity-ceiling: CRITICAL fix-within-30, HIGH within-90.
            # 21-J: an UNKNOWN classification is itself a defect — a CVE
            # outside any `=== {CRITICAL,HIGH}s ===` section AND without
            # an explicit `(SEV)` annotation silently bypasses both 21-G
            # coverage enforcement and the 21-H ceiling enforcement.
            # Refuse so the gate's coverage matches its claim.
            severity = classification.get(cve, "UNKNOWN")
            if severity == "UNKNOWN":
                errors.append(
                    f"{IGNOREFILE.name}:{lineno}: {cve} has no severity "
                    "classification (no preceding `=== CRITICALs ===` or "
                    "`=== HIGHs ===` section header, and no inline "
                    "`(CRITICAL)` / `(HIGH)` annotation). Without one, "
                    "21-G coverage and 21-H ceiling enforcement both "
                    "silently skip this entry. Place it under the right "
                    "section header or annotate it inline."
                )
                continue
            ceiling = SEVERITY_MAX_DAYS.get(severity)
            if ceiling is not None:
                window = (pending_expiry - today).days
                if window > ceiling:
                    errors.append(
                        f"{IGNOREFILE.name}:{lineno}: {cve} ({severity}) "
                        f"expires {pending_expiry.isoformat()} — {window}d "
                        f"away, beyond the {ceiling}d {severity} ceiling. "
                        "The .trivyignore header policy is "
                        "'CRITICAL → fix within 30 days, HIGH → fix within "
                        "90 days'; tighten the expiry, fix the CVE, or "
                        "amend the policy."
                    )
        # Don't consume the expiry — multiple CVEs in one block can share it
        # as long as there are no blank lines between them.
        _ = pending_expiry_line

    if errors:
        print(".trivyignore validation failed:")
        for e in errors:
            print(f"  - {e}")
        sys.exit(1)

    if not entries:
        print("✓ .trivyignore: present, no active entries")
        return

    soonest = min((exp for _, _, exp in entries if exp is not None), default=None)
    days = (soonest - today).days if soonest else None
    tail = f"soonest expiry {soonest.isoformat()} ({days}d)" if soonest else ""
    print(f"✓ .trivyignore: {len(entries)} active entries, all with valid non-expired expiries {tail}".rstrip())


def main() -> int:
    check_wrapper()
    check_render_list_images()
    check_makefile_target()
    check_workflow()
    check_trivyignore()
    return 0


if __name__ == "__main__":
    sys.exit(main())
