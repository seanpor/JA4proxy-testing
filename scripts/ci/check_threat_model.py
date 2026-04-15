#!/usr/bin/env python3
"""THREAT_MODEL.md hygiene (TM-A regression).

Assertions:
  1. THREAT_MODEL.md exists at repo root.
  2. It carries a `Last reviewed:` line parseable as YYYY-MM-DD that
     is within the last 365 days. The roadmap's CI hook calls this
     out explicitly so a stale model can't hide behind a green CI.
  3. It contains the required structural sections: the four
     attack-tree targets called out in the roadmap (VM compromise,
     DDoS reflector, DNS/domain hijack, data exfil) and a residual
     risk register.
  4. PHASE_08 STRIDE section links back to THREAT_MODEL.md so
     readers of the phase doc can find the higher-level model.
"""
from __future__ import annotations

import datetime
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TM = ROOT / "THREAT_MODEL.md"
PHASE_08 = ROOT / "docs" / "phases" / "PHASE_08_SECURITY_HARDENING.md"

REQUIRED_SECTIONS = (
    "VM compromise",
    "DDoS reflector",
    "DNS",
    "data exfil",
    "Residual risk",
)

errors: list[str] = []

if not TM.exists():
    errors.append(f"{TM.name}: missing at repo root")
else:
    text = TM.read_text()

    m = re.search(r"^Last reviewed:\s*(\d{4}-\d{2}-\d{2})", text, re.MULTILINE)
    if not m:
        errors.append(
            f"{TM.name}: missing or malformed `Last reviewed: YYYY-MM-DD` line"
        )
    else:
        try:
            last = datetime.date.fromisoformat(m.group(1))
            age = (datetime.date.today() - last).days
            if age > 365:
                errors.append(
                    f"{TM.name}: Last reviewed {last} is {age} days old (>365)"
                )
            if age < 0:
                errors.append(f"{TM.name}: Last reviewed {last} is in the future")
        except ValueError as exc:
            errors.append(f"{TM.name}: Last reviewed unparseable: {exc}")

    for needle in REQUIRED_SECTIONS:
        if needle.lower() not in text.lower():
            errors.append(f"{TM.name}: missing section covering `{needle}`")

if PHASE_08.exists():
    p = PHASE_08.read_text()
    if "THREAT_MODEL.md" not in p:
        errors.append(
            f"{PHASE_08.relative_to(ROOT)}: does not cross-link to THREAT_MODEL.md"
        )

if errors:
    print(f"{len(errors)} threat-model issue(s):")
    for e in errors:
        print(f"  {e}")
    sys.exit(1)

print("✓ THREAT_MODEL.md present, fresh (<365d), required sections, linked from PHASE_08")
