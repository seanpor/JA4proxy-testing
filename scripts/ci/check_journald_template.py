#!/usr/bin/env python3
"""journald.conf template hygiene (13-A regression).

Assert:
  1. deploy/templates/journald.conf.j2 exists.
  2. It sets Storage=persistent, MaxRetentionSec, SystemMaxUse,
     Compress=yes, ForwardToSyslog=no.
  3. Role 05 references the template (ansible.builtin.template) and
     no longer uses lineinfile on /etc/systemd/journald.conf
     (lineinfile is non-idempotent for multi-directive configs).
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TEMPLATE = ROOT / "deploy" / "templates" / "journald.conf.j2"
TASK = ROOT / "deploy" / "roles" / "05-data-collection" / "tasks" / "main.yml"

REQUIRED_KEYS = (
    "Storage",
    "MaxRetentionSec",
    "SystemMaxUse",
    "Compress",
    "ForwardToSyslog",
)

errors: list[str] = []

if not TEMPLATE.exists():
    errors.append(f"{TEMPLATE.relative_to(ROOT)}: missing")
else:
    text = TEMPLATE.read_text()
    for key in REQUIRED_KEYS:
        if not re.search(rf"^{key}\s*=", text, re.MULTILINE):
            errors.append(
                f"{TEMPLATE.relative_to(ROOT)}: missing `{key}=` directive"
            )

task_text = TASK.read_text() if TASK.exists() else ""
if "journald.conf.j2" not in task_text:
    errors.append(
        f"{TASK.relative_to(ROOT)}: does not reference journald.conf.j2"
    )
if re.search(r"lineinfile:.*\n(?:.*\n)*?\s*path:\s*/etc/systemd/journald\.conf",
             task_text):
    errors.append(
        f"{TASK.relative_to(ROOT)}: still uses lineinfile on "
        "/etc/systemd/journald.conf — use the template instead"
    )

if errors:
    print(f"{len(errors)} journald template issue(s):")
    for e in errors:
        print(f"  {e}")
    sys.exit(1)

print("✓ journald.conf.j2 present with all required directives, "
      "role 05 uses the template")
