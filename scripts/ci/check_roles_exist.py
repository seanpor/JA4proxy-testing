#!/usr/bin/env python3
"""Assert every role referenced by deploy/playbooks/site.yml exists on disk."""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PLAYBOOK = ROOT / "deploy" / "playbooks" / "site.yml"

text = PLAYBOOK.read_text()

# Match both `- role: ../roles/NN-foo` and `- name: …\n  role: …`.
role_refs = re.findall(r"-\s+role:\s*([^\s#]+)", text)
if not role_refs:
    sys.exit(f"No role references found in {PLAYBOOK} — parser bug?")

errors = []
for ref in role_refs:
    # Resolve relative to the playbook's directory, as Ansible would.
    resolved = (PLAYBOOK.parent / ref).resolve()
    if not resolved.is_dir():
        errors.append(f"missing role: {ref} (resolved to {resolved})")
    elif not (resolved / "tasks" / "main.yml").is_file():
        errors.append(f"role has no tasks/main.yml: {ref}")

if errors:
    print(f"{len(errors)} role reference error(s):")
    for e in errors:
        print(f"  {e}")
    sys.exit(1)

print(f"✓ {len(role_refs)} role references all resolve")
