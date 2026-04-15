#!/usr/bin/env python3
"""RUNBOOK incident-response scenarios (15-B regression).

The roadmap requires the eight named scenarios from PHASE_15 §15.4 to
exist in the runbook, each with `Preconditions`, a numbered
procedure, and a rollback note. A scenario can be deleted by
accident; this check makes that failure loud at CI.

Assertions:
  1. docs/phases/RUNBOOK.md has an `## Incident Response Scenarios`
     section heading.
  2. Under it, each of the eight scenarios has a `### <N>. <name>`
     subheading. Names matched case-insensitively on a keyword.
  3. Each scenario block contains `Preconditions`, a numbered step
     ("1."), and `Rollback`.
  4. The VM-compromise scenario references `preserve-evidence.sh`
     (roadmap acceptance criterion) and the LE-request scenario
     references `LE_REQUESTS.md` (cross-link with 11-E).
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RUNBOOK = ROOT / "docs" / "phases" / "RUNBOOK.md"

SCENARIOS = (
    ("SSH lockout", ["ssh", "lockout"]),
    ("Caddy ACME rate-limit", ["acme", "rate"]),
    ("Redis corruption", ["redis", "corrupt"]),
    ("Disk full", ["disk", "full"]),
    ("Grafana password reset", ["grafana", "password"]),
    ("VM compromise", ["vm", "compromise"]),
    ("Law-enforcement request", ["law", "enforcement"]),
    ("DNS misconfig opened UFW", ["dns", "ufw"]),
)

errors: list[str] = []

if not RUNBOOK.exists():
    sys.exit(f"{RUNBOOK.relative_to(ROOT)}: missing")

text = RUNBOOK.read_text()
lower = text.lower()

if "## incident response scenarios" not in lower:
    errors.append("RUNBOOK.md: no `## Incident Response Scenarios` section")

ir_start = lower.find("## incident response scenarios")
ir_body = text[ir_start:] if ir_start >= 0 else ""
ir_lower = ir_body.lower()

# Split into subsection blocks on `### `
blocks = re.split(r"^### ", ir_body, flags=re.MULTILINE)[1:]

for label, keywords in SCENARIOS:
    match = None
    for block in blocks:
        head = block.splitlines()[0].lower() if block else ""
        if all(k in head for k in keywords):
            match = block
            break
    if not match:
        errors.append(f"RUNBOOK.md: scenario missing — `{label}` (keywords {keywords})")
        continue
    if "preconditions" not in match.lower():
        errors.append(f"RUNBOOK.md: `{label}` missing Preconditions")
    if not re.search(r"^\s*1\.\s", match, re.MULTILINE):
        errors.append(f"RUNBOOK.md: `{label}` missing numbered procedure (no `1.` line)")
    if "rollback" not in match.lower():
        errors.append(f"RUNBOOK.md: `{label}` missing Rollback note")
    if label == "VM compromise" and "preserve-evidence.sh" not in match:
        errors.append(
            "RUNBOOK.md: VM compromise scenario must reference preserve-evidence.sh (15-A link)"
        )
    if label == "Law-enforcement request" and "LE_REQUESTS.md" not in match:
        errors.append(
            "RUNBOOK.md: LE request scenario must reference docs/governance/LE_REQUESTS.md"
        )

if errors:
    print(f"{len(errors)} runbook scenario issue(s):")
    for e in errors:
        print(f"  {e}")
    sys.exit(1)

print(f"✓ RUNBOOK.md Incident Response section covers all {len(SCENARIOS)} scenarios")
