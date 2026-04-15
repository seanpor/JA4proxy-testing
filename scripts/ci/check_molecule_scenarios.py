#!/usr/bin/env python3
"""Molecule scenario hygiene (14-E regression).

For every `molecule/` directory under deploy/roles/, assert the
default scenario has the three files Molecule requires:

  - molecule.yml
  - converge.yml
  - verify.yml

Structural only — running molecule itself requires Docker and extra
pip deps, so that's deferred to `make molecule`.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ROLES = ROOT / "deploy" / "roles"

REQUIRED = ("molecule.yml", "converge.yml", "verify.yml")

errors: list[str] = []
scenarios = 0

for role_dir in sorted(ROLES.iterdir()):
    mol = role_dir / "molecule"
    if not mol.is_dir():
        continue
    for scenario in sorted(mol.iterdir()):
        if not scenario.is_dir():
            continue
        scenarios += 1
        for req in REQUIRED:
            if not (scenario / req).is_file():
                errors.append(
                    f"{(scenario / req).relative_to(ROOT)}: missing"
                )

if errors:
    print(f"{len(errors)} Molecule scenario issue(s):")
    for e in errors:
        print(f"  {e}")
    sys.exit(1)

if scenarios == 0:
    print("✓ no Molecule scenarios defined (none required yet)")
else:
    print(f"✓ {scenarios} Molecule scenario(s), all with required files")
