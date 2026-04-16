#!/usr/bin/env python3
"""Anonymisation script + tests (12-B regression).

Assertions:
  1. deploy/scripts/anonymise.py exists.
  2. deploy/scripts/test_anonymise.py exists and passes.
  3. docs/governance/ANONYMISATION.md exists with Last reviewed line.
"""
from __future__ import annotations

import datetime
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ANON = ROOT / "deploy" / "scripts" / "anonymise.py"
TEST = ROOT / "deploy" / "scripts" / "test_anonymise.py"
DOC = ROOT / "docs" / "governance" / "ANONYMISATION.md"

errors: list[str] = []

if not ANON.exists():
    errors.append("deploy/scripts/anonymise.py: missing")
if not TEST.exists():
    errors.append("deploy/scripts/test_anonymise.py: missing")
else:
    result = subprocess.run(
        [sys.executable, str(TEST)],
        capture_output=True, text=True, timeout=30,
    )
    if result.returncode != 0:
        errors.append(f"test_anonymise.py failed:\n{result.stdout}\n{result.stderr}")

if not DOC.exists():
    errors.append("docs/governance/ANONYMISATION.md: missing")
else:
    text = DOC.read_text()
    m = re.search(r"^#?\s*Last reviewed:\s*(\d{4}-\d{2}-\d{2})", text, re.MULTILINE)
    if not m:
        errors.append("ANONYMISATION.md: missing `Last reviewed:` line")
    else:
        age = (datetime.date.today() - datetime.date.fromisoformat(m.group(1))).days
        if age > 365:
            errors.append(f"ANONYMISATION.md: Last reviewed is {age} days old (>365)")

if errors:
    print(f"{len(errors)} anonymisation issue(s):")
    for e in errors:
        print(f"  {e}")
    sys.exit(1)

print("✓ anonymise.py exists, tests pass, ANONYMISATION.md present and fresh")
