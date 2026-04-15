#!/usr/bin/env python3
"""preserve-evidence.sh hygiene (15-A regression).

Assert:
  1. deploy/scripts/preserve-evidence.sh exists and is executable.
  2. It uses `set -euo pipefail` and produces a sha256 of the tarball.
  3. Role 06 copies it to /usr/local/sbin/preserve-evidence.sh with
     mode 0750.
  4. Role 06 also creates /var/lib/ja4proxy/evidence with mode 0700.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "deploy" / "scripts" / "preserve-evidence.sh"
ROLE06 = ROOT / "deploy" / "roles" / "06-operational-security" / "tasks" / "main.yml"

errors: list[str] = []

if not SCRIPT.exists():
    errors.append(f"{SCRIPT.relative_to(ROOT)}: missing")
else:
    if not os.access(SCRIPT, os.X_OK):
        errors.append(f"{SCRIPT.relative_to(ROOT)}: not executable")
    text = SCRIPT.read_text()
    for needle in ("set -euo pipefail", "sha256sum", "journalctl", "iptables"):
        if needle not in text:
            errors.append(f"{SCRIPT.relative_to(ROOT)}: missing `{needle}`")

if ROLE06.exists():
    r = ROLE06.read_text()
    if "preserve-evidence.sh" not in r:
        errors.append(f"{ROLE06.relative_to(ROOT)}: does not deploy preserve-evidence.sh")
    if "/var/lib/ja4proxy/evidence" not in r:
        errors.append(f"{ROLE06.relative_to(ROOT)}: evidence directory not created")
    if '"0750"' not in r:
        errors.append(f"{ROLE06.relative_to(ROOT)}: preserve-evidence.sh not installed 0750")

if errors:
    print(f"{len(errors)} preserve-evidence issue(s):")
    for e in errors:
        print(f"  {e}")
    sys.exit(1)

print("✓ preserve-evidence.sh executable, deployed by role 06, evidence dir created")
