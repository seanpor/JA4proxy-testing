#!/usr/bin/env python3
"""Alert rules file hygiene (13-E + 13-F regression).

Assertions:
  1. deploy/files/prometheus/alert-rules.yml exists and is valid YAML.
  2. The five 13-E rules exist: JA4proxyDown, HAProxyDown, RedisDown,
     NoTrafficLastHour, DiskFull.
  3. The two 13-F rules exist: CertExpiringSoon, HoneypotProbeFailing.
  4. Every rule has `expr`, `for`, and `labels.severity`.
"""
from __future__ import annotations

import sys
from pathlib import Path

try:
    import yaml
except ImportError:
    sys.exit("pyyaml not installed. Run: make lint-install")

ROOT = Path(__file__).resolve().parents[2]
RULES = ROOT / "deploy" / "files" / "prometheus" / "alert-rules.yml"

REQUIRED = {
    "CertExpiringSoon",
    "HoneypotProbeFailing",
    "JA4proxyDown",
    "HAProxyDown",
    "RedisDown",
    "NoTrafficLastHour",
    "DiskFull",
}

errors: list[str] = []

if not RULES.exists():
    sys.exit(f"{RULES.relative_to(ROOT)}: missing")

doc = yaml.safe_load(RULES.read_text())
if not isinstance(doc, dict) or "groups" not in doc:
    sys.exit(f"{RULES.relative_to(ROOT)}: no top-level `groups:` key")

found: dict[str, dict] = {}
for group in doc["groups"]:
    for rule in group.get("rules", []):
        name = rule.get("alert")
        if name:
            found[name] = rule

missing = REQUIRED - set(found)
if missing:
    errors.append(f"missing alert(s): {', '.join(sorted(missing))}")

for name in REQUIRED & set(found):
    rule = found[name]
    if "expr" not in rule:
        errors.append(f"{name}: missing `expr`")
    if "for" not in rule:
        errors.append(f"{name}: missing `for`")
    labels = rule.get("labels") or {}
    if "severity" not in labels:
        errors.append(f"{name}: missing `labels.severity`")

if errors:
    print(f"{len(errors)} alert-rules issue(s):")
    for e in errors:
        print(f"  {e}")
    sys.exit(1)

print(f"✓ alert-rules.yml has all {len(REQUIRED)} required alerts with expr/for/severity")
