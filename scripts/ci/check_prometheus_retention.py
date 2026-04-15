#!/usr/bin/env python3
"""Prometheus TSDB retention hygiene (13-C regression).

Assert the docker-compose template passes both
  --storage.tsdb.retention.time
  --storage.tsdb.retention.size
to the Prometheus container, and that the referenced variables are
declared in group_vars/all.yml. Without these, Prometheus retains
samples indefinitely and can fill the disk.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
COMPOSE = ROOT / "deploy" / "templates" / "docker-compose.yml.j2"
GROUPVARS = ROOT / "deploy" / "inventory" / "group_vars" / "all.yml"

errors: list[str] = []

compose_text = COMPOSE.read_text() if COMPOSE.exists() else ""
groupvars_text = GROUPVARS.read_text() if GROUPVARS.exists() else ""

if not re.search(r"--storage\.tsdb\.retention\.time=", compose_text):
    errors.append(f"{COMPOSE.relative_to(ROOT)}: missing --storage.tsdb.retention.time")
if not re.search(r"--storage\.tsdb\.retention\.size=", compose_text):
    errors.append(f"{COMPOSE.relative_to(ROOT)}: missing --storage.tsdb.retention.size")

for var in ("ja4proxy_prometheus_retention_days", "ja4proxy_prometheus_retention_size"):
    if not re.search(rf"^{var}:\s*\S+", groupvars_text, re.MULTILINE):
        errors.append(f"{GROUPVARS.relative_to(ROOT)}: missing `{var}` default")
    if var not in compose_text:
        errors.append(f"{COMPOSE.relative_to(ROOT)}: does not reference `{var}`")

if errors:
    print(f"{len(errors)} prometheus retention issue(s):")
    for e in errors:
        print(f"  {e}")
    sys.exit(1)

print("✓ prometheus TSDB time + size retention bounds declared and wired")
