#!/usr/bin/env python3
"""Phase 21-D: scheduled-workflow enabled-state gate.

Fails CI if any `schedule:`-bearing workflow under `.github/workflows/`
has `state != "active"` in the GitHub Actions API.

Context:
  GitHub auto-disables scheduled workflows after 60 days of repo
  inactivity (`state = "disabled_inactivity"`). An operator can also
  disable a workflow manually (`state = "disabled_manually"`). Either
  way, the cron silently stops firing, which is exactly the
  "scheduler present, mechanism broken" defect Phase 20 targets.

  21-B (`check_digest_freshness.py`) catches the case where the cron
  fires but produces no successful run in 14 days. It cannot catch
  the case where the workflow is disabled, because a disabled
  workflow with *any* prior successful run still looks fresh. And it
  cannot catch semi-annual workflows like `drill-reminder` which
  legitimately have no runs between April and October.

  21-D fills that gap: if the workflow object's `state` field is not
  `active`, something turned it off. CI goes red immediately — the
  operator either re-enables the workflow or accepts the risk by
  deleting the cron entirely.

Why enumerate scheduled workflows, not all workflows:
  A non-scheduled workflow (e.g. `ci.yml` which only fires on `push`
  / `pull_request`) cannot be auto-disabled by inactivity and is not
  "load-bearing" in the background-cron sense. Gating those would
  produce false positives whenever someone legitimately retires a
  workflow.

Offline behaviour:
  Same pattern as `check_digest_freshness.py` — if `gh` is missing,
  the repo slug can't be resolved, or `--offline` / `CI_OFFLINE=1` is
  set, the check exits 0 with a warning.
"""
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WORKFLOWS_DIR = ROOT / ".github" / "workflows"


def _gh_available() -> bool:
    return shutil.which("gh") is not None


def _repo_slug() -> str | None:
    try:
        out = subprocess.check_output(
            ["gh", "repo", "view", "--json", "nameWithOwner", "--jq", ".nameWithOwner"],
            stderr=subprocess.DEVNULL,
            text=True,
        )
        return out.strip() or None
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None


def _scheduled_workflow_files() -> list[Path]:
    """Workflow files containing a `schedule:` key. Cheap text match is
    sufficient — `schedule:` only appears at the top-level `on:` in
    practice, and a false positive (e.g. in a comment) just means one
    extra API call, not a spurious failure."""
    files: list[Path] = []
    for p in sorted(WORKFLOWS_DIR.glob("*.yml")):
        text = p.read_text()
        if "schedule:" in text:
            files.append(p)
    return files


def _workflow_state(slug: str, filename: str) -> str | None:
    """Return the GitHub `state` field for the workflow, or None on
    API error."""
    try:
        out = subprocess.check_output(
            [
                "gh", "api",
                f"/repos/{slug}/actions/workflows/{filename}",
                "--jq", ".state",
            ],
            stderr=subprocess.DEVNULL,
            text=True,
        )
    except subprocess.CalledProcessError:
        return None
    out = out.strip()
    return out or None


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--offline",
        action="store_true",
        help="Skip the gh-api check with a warning (dev loop / airgap).",
    )
    args = ap.parse_args()

    if args.offline or os.environ.get("CI_OFFLINE") == "1":
        print("⚠ check_workflow_enabled: offline mode — skipping")
        return 0

    if not _gh_available():
        print("⚠ check_workflow_enabled: `gh` CLI not on PATH — skipping")
        return 0

    slug = _repo_slug()
    if not slug:
        print("⚠ check_workflow_enabled: could not determine repo slug — skipping")
        return 0

    files = _scheduled_workflow_files()
    if not files:
        print("⚠ check_workflow_enabled: no scheduled workflows found — nothing to check")
        return 0

    errors: list[str] = []
    reports: list[str] = []
    for path in files:
        name = path.name
        state = _workflow_state(slug, name)
        if state is None:
            errors.append(
                f"✗ {name}: API lookup failed — cannot verify state"
            )
            continue
        if state != "active":
            errors.append(
                f"✗ {name}: state={state!r} (expected 'active'). "
                f"A disabled scheduled workflow silently stops firing; "
                f"re-enable it on the repo's Actions tab or remove the "
                f"cron if it's genuinely retired."
            )
            continue
        reports.append(f"  {name}: active")

    if errors:
        print(f"{len(errors)} scheduled-workflow state issue(s):")
        for e in errors:
            print(f"  {e}")
        return 1

    print(f"✓ {len(reports)} scheduled workflow(s) all active:")
    for r in reports:
        print(r)
    return 0


if __name__ == "__main__":
    sys.exit(main())
