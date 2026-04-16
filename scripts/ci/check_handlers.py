#!/usr/bin/env python3
"""17-A/C: Verify every notify: in every role resolves to a defined handler."""
from __future__ import annotations

import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
ROLES = REPO / "deploy" / "roles"

errors: list[str] = []

for role_dir in sorted(ROLES.iterdir()):
    if not role_dir.is_dir():
        continue
    tasks_file = role_dir / "tasks" / "main.yml"
    if not tasks_file.exists():
        continue

    # Collect notify targets from tasks
    notifies: list[str] = []
    for line in tasks_file.read_text().splitlines():
        m = re.match(r"\s+notify:\s+(.+)", line)
        if m:
            notifies.append(m.group(1).strip())

    if not notifies:
        continue

    # Collect defined handler names
    handlers_file = role_dir / "handlers" / "main.yml"
    defined: set[str] = set()
    if handlers_file.exists():
        for line in handlers_file.read_text().splitlines():
            m = re.match(r"- name:\s+(.+)", line)
            if m:
                defined.add(m.group(1).strip())

    # Check each notify resolves
    for notify in notifies:
        if notify not in defined:
            errors.append(
                f"{role_dir.name}: notify '{notify}' has no handler "
                f"(defined: {sorted(defined) if defined else 'none'})"
            )

if errors:
    print("Handler resolution failures:")
    for e in errors:
        print(f"  {e}")
    sys.exit(1)

print("✓ all notify targets resolve to defined handlers")
