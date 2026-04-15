#!/usr/bin/env python3
"""Loki retention hygiene (13-B regression).

Assert that deploy/templates/loki.yml.j2 declares:
  - table_manager.retention_deletes_enabled: true
  - table_manager.retention_period: <value> (typically derived from
    ja4proxy_loki_retention_days)

Without these, Loki accumulates logs indefinitely and the 90-day
retention claim in the privacy page is false.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TEMPLATE = ROOT / "deploy" / "templates" / "loki.yml.j2"

errors: list[str] = []

if not TEMPLATE.exists():
    errors.append(f"{TEMPLATE.relative_to(ROOT)}: missing")
else:
    text = TEMPLATE.read_text()
    if not re.search(r"^table_manager:", text, re.MULTILINE):
        errors.append(f"{TEMPLATE.relative_to(ROOT)}: missing `table_manager:` stanza")
    if not re.search(r"retention_deletes_enabled:\s*true", text):
        errors.append(
            f"{TEMPLATE.relative_to(ROOT)}: retention_deletes_enabled must be true"
        )
    if not re.search(r"retention_period:\s*\S+", text):
        errors.append(f"{TEMPLATE.relative_to(ROOT)}: missing retention_period")

if errors:
    print(f"{len(errors)} loki retention issue(s):")
    for e in errors:
        print(f"  {e}")
    sys.exit(1)

print("✓ loki.yml.j2 declares table_manager retention_deletes_enabled + retention_period")
