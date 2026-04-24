#!/usr/bin/env python3
"""Phase 21-B: digest-pin freshness gate.

Fails CI if the `digest-update.yml` workflow has not completed
successfully within the configured freshness window (default 14d).

Context:
  Phase 18-G added a weekly workflow that queries Docker Hub for the
  live digest of each pinned image and opens a PR on drift. Phase 20
  P0-2 wired the pin file into role 09 as a deploy-time assertion,
  giving the file real teeth.

  However, the workflow refresh itself is best-effort: if the cron is
  disabled, the token expires, or the workflow breaks silently, the
  pin file ages and the Phase 20 assertion starts blocking deploys
  against stale digests without any upstream signal.

  This check converts the "weekly refresh" from best-effort to
  load-bearing — if the workflow hasn't reported a successful run in
  14 days (= 2 missed weekly fires), CI goes red and forces a human
  look.

Why the workflow's last-success, not the pin file's mtime:
  A successful run with zero digest drift leaves the file untouched
  but proves the refresh mechanism is alive. Mtime would raise false
  alarms in quiet periods when Docker Hub hasn't moved.

Online vs offline:
  This check hits `gh api` for the workflow run history. When `gh`
  is unauthenticated (CI without a `GH_TOKEN`, airgapped dev loop)
  the 60/h unauthenticated rate limit makes the call unreliable.
  Pass `--offline` or set `CI_OFFLINE=1` to skip with a warning —
  same pattern as `check_workflow_pins.py`.
"""
from __future__ import annotations

import argparse
import datetime
import json
import os
import shutil
import subprocess
import sys

WORKFLOW_FILE = "digest-update.yml"
DEFAULT_MAX_AGE_DAYS = 14


def _gh_available() -> bool:
    return shutil.which("gh") is not None


def _repo_slug() -> str | None:
    """`<owner>/<name>` from the current git remote, or None if we
    cannot determine it."""
    try:
        out = subprocess.check_output(
            ["gh", "repo", "view", "--json", "nameWithOwner", "--jq", ".nameWithOwner"],
            stderr=subprocess.DEVNULL,
            text=True,
        )
        return out.strip() or None
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None


def _latest_success(slug: str, workflow: str) -> dict | None:
    """Latest successful run of `workflow` on `slug`, or None."""
    # `-f key=value` sends form data (POST body); the runs endpoint needs
    # query string instead, so embed params directly in the URL.
    try:
        out = subprocess.check_output(
            [
                "gh", "api",
                f"/repos/{slug}/actions/workflows/{workflow}/runs"
                f"?status=completed&per_page=10",
                "--jq",
                '[.workflow_runs[] | select(.conclusion=="success")][0] // empty',
            ],
            stderr=subprocess.DEVNULL,
            text=True,
        )
    except subprocess.CalledProcessError:
        return None
    out = out.strip()
    if not out:
        return None
    try:
        return json.loads(out)
    except json.JSONDecodeError:
        return None


def _parse_iso(ts: str) -> datetime.datetime:
    return datetime.datetime.fromisoformat(ts.replace("Z", "+00:00"))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--max-age-days",
        type=int,
        default=DEFAULT_MAX_AGE_DAYS,
        help=f"Fail if the latest success is older than this (default {DEFAULT_MAX_AGE_DAYS}).",
    )
    ap.add_argument(
        "--offline",
        action="store_true",
        help="Skip the gh-api check with a warning (dev loop / airgap).",
    )
    args = ap.parse_args()

    if args.offline or os.environ.get("CI_OFFLINE") == "1":
        print("⚠ check_digest_freshness: offline mode — skipping")
        return 0

    if not _gh_available():
        print("⚠ check_digest_freshness: `gh` CLI not on PATH — skipping")
        return 0

    slug = _repo_slug()
    if not slug:
        print("⚠ check_digest_freshness: could not determine repo slug — skipping")
        return 0

    run = _latest_success(slug, WORKFLOW_FILE)
    if run is None:
        print(
            f"✗ check_digest_freshness: no successful run of "
            f"`{WORKFLOW_FILE}` on {slug} — is the workflow enabled?"
        )
        return 1

    updated = _parse_iso(run["updated_at"])
    now = datetime.datetime.now(datetime.timezone.utc)
    age_days = (now - updated).days

    if age_days > args.max_age_days:
        print(
            f"✗ check_digest_freshness: latest success of "
            f"`{WORKFLOW_FILE}` is {age_days}d old "
            f"(> {args.max_age_days}d ceiling). Run #{run['run_number']} "
            f"completed {updated.isoformat()}. Check the workflow is "
            f"enabled and the cron is firing."
        )
        return 1

    print(
        f"✓ digest-update.yml last success: {age_days}d ago "
        f"(run #{run['run_number']}, {updated.date()}; ceiling {args.max_age_days}d)"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
