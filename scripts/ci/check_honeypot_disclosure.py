#!/usr/bin/env python3
"""Honeypot disclosure page hygiene (11-A regression).

Assert:
  1. deploy/files/honeypot-notice.html exists and contains `abuse@`,
     `privacy@`, and a "honeypot" identifier so the page is
     self-describing.
  2. Role 02 deploys it into the caddy/html directory.
  3. The landing page (templates/honeypot-index.html) links to it.
  4. Role 07 smoke-tests the page for the two contact markers.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
NOTICE = ROOT / "deploy" / "files" / "honeypot-notice.html"
INDEX = ROOT / "deploy" / "templates" / "honeypot-index.html"
DEPLOY_TASK = ROOT / "deploy" / "roles" / "02-artifact-build" / "tasks" / "deploy-configs.yml"
VALIDATE_TASK = ROOT / "deploy" / "roles" / "07-validation" / "tasks" / "main.yml"

errors: list[str] = []

if not NOTICE.exists():
    errors.append(f"{NOTICE.relative_to(ROOT)}: missing")
else:
    text = NOTICE.read_text()
    for needle in ("abuse@", "privacy@", "honeypot"):
        if needle.lower() not in text.lower():
            errors.append(f"{NOTICE.relative_to(ROOT)}: missing `{needle}`")

if INDEX.exists() and "honeypot-notice.html" not in INDEX.read_text():
    errors.append(f"{INDEX.relative_to(ROOT)}: landing page does not link to /honeypot-notice.html")

if DEPLOY_TASK.exists() and "honeypot-notice.html" not in DEPLOY_TASK.read_text():
    errors.append(f"{DEPLOY_TASK.relative_to(ROOT)}: no task deploys honeypot-notice.html")

if VALIDATE_TASK.exists():
    v = VALIDATE_TASK.read_text()
    if "honeypot-notice.html" not in v or "abuse@" not in v or "privacy@" not in v:
        errors.append(
            f"{VALIDATE_TASK.relative_to(ROOT)}: missing smoke test for "
            "honeypot-notice.html with abuse@/privacy@ assertions"
        )

if errors:
    print(f"{len(errors)} honeypot disclosure issue(s):")
    for e in errors:
        print(f"  {e}")
    sys.exit(1)

print("✓ honeypot-notice.html present, linked, deployed, smoke-tested")
