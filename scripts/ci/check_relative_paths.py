#!/usr/bin/env python3
"""17-D: Verify every {{ playbook_dir }}/../... path in roles resolves to a real file."""
from __future__ import annotations

import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
ROLES = REPO / "deploy" / "roles"
# playbook_dir = deploy/playbooks
PLAYBOOK_DIR = REPO / "deploy" / "playbooks"

# Match {{ playbook_dir }}/../../path or {{ playbook_dir }}/../path
PATH_RE = re.compile(r"\{\{\s*playbook_dir\s*\}\}(/[^\s\"']+)")

errors: list[str] = []
checked = 0

for yml in sorted(ROLES.rglob("*.yml")):
    for lineno, line in enumerate(yml.read_text().splitlines(), 1):
        for m in PATH_RE.finditer(line):
            rel = m.group(1)
            resolved = (PLAYBOOK_DIR / ("." + rel)).resolve()
            checked += 1
            # Skip .vault paths (generated at runtime, gitignored)
            if ".vault" in str(resolved):
                continue
            if not resolved.exists():
                role_rel = yml.relative_to(REPO)
                errors.append(f"{role_rel}:{lineno}: {m.group(0)} -> {resolved} (not found)")

if errors:
    print("Broken playbook_dir relative paths:")
    for e in errors:
        print(f"  {e}")
    sys.exit(1)

print(f"✓ {checked} playbook_dir relative paths verified")
