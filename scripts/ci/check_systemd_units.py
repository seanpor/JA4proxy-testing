#!/usr/bin/env python3
"""Systemd unit template hygiene (13-I regression).

For every `*.timer.j2` under deploy/templates/:
  1. A matching `*.service.j2` must exist (same stem).
  2. Timer must have a sensible [Timer] section with OnCalendar=,
     OnBootSec=, or OnUnitActiveSec=.
  3. Service must have [Service] and an ExecStart.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TPL_DIR = ROOT / "deploy" / "templates"

errors: list[str] = []
timers = sorted(TPL_DIR.glob("*.timer.j2"))

if not timers:
    print("✓ no timer templates to check")
    sys.exit(0)

for timer in timers:
    stem = timer.name[: -len(".timer.j2")]
    service = TPL_DIR / f"{stem}.service.j2"
    if not service.exists():
        errors.append(
            f"{timer.relative_to(ROOT)}: no matching {stem}.service.j2"
        )
        continue

    t = timer.read_text()
    if "[Timer]" not in t:
        errors.append(f"{timer.relative_to(ROOT)}: missing [Timer] section")
    if not re.search(r"^(OnCalendar|OnBootSec|OnUnitActiveSec)=", t, re.MULTILINE):
        errors.append(
            f"{timer.relative_to(ROOT)}: no OnCalendar/OnBootSec/OnUnitActiveSec"
        )

    s = service.read_text()
    if "[Service]" not in s:
        errors.append(f"{service.relative_to(ROOT)}: missing [Service] section")
    if not re.search(r"^ExecStart=", s, re.MULTILINE):
        errors.append(f"{service.relative_to(ROOT)}: no ExecStart=")

if errors:
    print(f"{len(errors)} systemd unit issue(s):")
    for e in errors:
        print(f"  {e}")
    sys.exit(1)

print(f"✓ {len(timers)} timer(s) have matching service units with valid sections")
