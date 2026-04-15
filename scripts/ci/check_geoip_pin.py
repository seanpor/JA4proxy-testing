#!/usr/bin/env python3
"""GeoIP source integrity (14-C regression).

Assert:
  1. group_vars declares `ja4proxy_geoip_expected_sha256` (may be empty
     string — empty = skip check).
  2. role 02 geoip.yml references the variable so it can't be silently
     bypassed.

Rationale: IP2Location LITE downloads rotate. Yesterday's research
result isn't reproducible from today's data if we don't pin.
"""
from __future__ import annotations

import sys
from pathlib import Path

try:
    import yaml
except ImportError:
    sys.exit("pyyaml not installed. Run: make lint-install")

ROOT = Path(__file__).resolve().parents[2]
GROUP_VARS = ROOT / "deploy" / "inventory" / "group_vars" / "all.yml"
GEOIP_TASK = ROOT / "deploy" / "roles" / "02-artifact-build" / "tasks" / "geoip.yml"

errors: list[str] = []

gv = yaml.safe_load(GROUP_VARS.read_text()) or {}
if "ja4proxy_geoip_expected_sha256" not in gv:
    errors.append(
        f"{GROUP_VARS.relative_to(ROOT)}: "
        "missing `ja4proxy_geoip_expected_sha256` (may be empty string)"
    )
else:
    val = gv["ja4proxy_geoip_expected_sha256"]
    if val and (not isinstance(val, str) or not all(c in "0123456789abcdef" for c in val) or len(val) != 64):
        errors.append(
            f"{GROUP_VARS.relative_to(ROOT)}: "
            f"`ja4proxy_geoip_expected_sha256` must be empty or 64 hex chars "
            f"(got `{val}`)"
        )

if "ja4proxy_geoip_expected_sha256" not in GEOIP_TASK.read_text():
    errors.append(
        f"{GEOIP_TASK.relative_to(ROOT)}: "
        "does not reference ja4proxy_geoip_expected_sha256 — pin unused"
    )

if errors:
    print(f"{len(errors)} GeoIP pin issue(s):")
    for e in errors:
        print(f"  {e}")
    sys.exit(1)

print("✓ ja4proxy_geoip_expected_sha256 declared and referenced by role 02")
