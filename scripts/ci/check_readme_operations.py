#!/usr/bin/env python3
"""README Operations section hygiene (15-D regression).

Assert the README carries an `## Operations` section that states the
on-call posture: abuse-email response window, down-alert response
window, and the stop-before-away expectation. The whole on-call block
stays ≤ 20 lines so it doesn't silently grow into a runbook dupe.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
README = ROOT / "README.md"

REQUIRED_MARKERS = (
    "abuse",
    "3 business days",
    "24 h",
    "RUNBOOK",
)

errors: list[str] = []
text = README.read_text()

if not re.search(r"^## Operations\b", text, re.MULTILINE):
    errors.append(f"{README.name}: missing `## Operations` heading")

m = re.search(r"^### On-call posture\b(.*?)(?=^##\s|^### )", text, re.DOTALL | re.MULTILINE)
if not m:
    errors.append(f"{README.name}: missing `### On-call posture` subsection")
else:
    block = m.group(1)
    lines = [ln for ln in block.splitlines() if ln.strip()]
    if len(lines) > 20:
        errors.append(
            f"{README.name}: On-call posture block is {len(lines)} non-empty "
            "lines — roadmap caps it at 20"
        )
    for marker in REQUIRED_MARKERS:
        if marker.lower() not in block.lower():
            errors.append(f"{README.name}: On-call posture missing `{marker}`")

if errors:
    print(f"{len(errors)} README Operations issue(s):")
    for e in errors:
        print(f"  {e}")
    sys.exit(1)

print("✓ README Operations → On-call posture present and within size budget")
