#!/usr/bin/env python3
"""Secrets rotation role (13-J regression).

Assertions:
  1. deploy/roles/12-secrets-rotation/tasks/main.yml exists.
  2. deploy/roles/12-secrets-rotation/defaults/main.yml exists.
  3. deploy/playbooks/rotate.yml exists, references role 12.
  4. deploy/Makefile has a `rotate` target.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ROLE = ROOT / "deploy" / "roles" / "12-secrets-rotation"
PLAYBOOK = ROOT / "deploy" / "playbooks" / "rotate.yml"
MAKEFILE = ROOT / "deploy" / "Makefile"

errors: list[str] = []

if not (ROLE / "tasks" / "main.yml").exists():
    errors.append("deploy/roles/12-secrets-rotation/tasks/main.yml: missing")
if not (ROLE / "defaults" / "main.yml").exists():
    errors.append("deploy/roles/12-secrets-rotation/defaults/main.yml: missing")

if not PLAYBOOK.exists():
    errors.append("deploy/playbooks/rotate.yml: missing")
else:
    text = PLAYBOOK.read_text()
    if "12-secrets-rotation" not in text:
        errors.append("deploy/playbooks/rotate.yml: does not reference role 12-secrets-rotation")

if not re.search(r"^rotate\s*:", MAKEFILE.read_text(), re.MULTILINE):
    errors.append("deploy/Makefile: no `rotate:` target")

if errors:
    print(f"{len(errors)} secrets-rotation issue(s):")
    for e in errors:
        print(f"  {e}")
    sys.exit(1)

print("✓ secrets-rotation role, playbook, and Makefile target present")
