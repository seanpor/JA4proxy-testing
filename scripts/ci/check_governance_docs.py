#!/usr/bin/env python3
"""Governance document skeletons (11-E + 15-C regression).

Assertions:
  1. All ten governance files exist under docs/governance/.
  2. Each carries a `Last reviewed:` line parseable as YYYY-MM-DD and
     within the last 365 days.
  3. docs/governance/README.md indexes the other files by name.
  4. STAKEHOLDERS.yml is valid YAML (15-C).
"""
from __future__ import annotations

import datetime
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
GDIR = ROOT / "docs" / "governance"

REQUIRED = (
    "LAWFUL_BASIS.md",
    "DPIA.md",
    "ROPA.md",
    "RETENTION.md",
    "LE_REQUESTS.md",
    "ETHICS.md",
    "README.md",
    # 15-C additions
    "abuse-reply-template.md",
    "OUTBOUND_REPORTING.md",
    "STAKEHOLDERS.yml",
)

# STAKEHOLDERS.yml must also be valid YAML (15-C acceptance).
YAML_FILES = ("STAKEHOLDERS.yml",)

errors: list[str] = []

if not GDIR.is_dir():
    errors.append(f"{GDIR.relative_to(ROOT)}: directory missing")
else:
    for name in REQUIRED:
        p = GDIR / name
        if not p.exists():
            errors.append(f"docs/governance/{name}: missing")
            continue
        text = p.read_text()
        m = re.search(r"^#?\s*Last reviewed:\s*(\d{4}-\d{2}-\d{2})", text, re.MULTILINE)
        if not m:
            errors.append(
                f"docs/governance/{name}: missing or malformed `Last reviewed: YYYY-MM-DD` line"
            )
            continue
        try:
            last = datetime.date.fromisoformat(m.group(1))
        except ValueError as exc:
            errors.append(f"docs/governance/{name}: Last reviewed unparseable: {exc}")
            continue
        age = (datetime.date.today() - last).days
        if age > 365:
            errors.append(
                f"docs/governance/{name}: Last reviewed {last} is {age} days old (>365)"
            )
        if age < 0:
            errors.append(
                f"docs/governance/{name}: Last reviewed {last} is in the future"
            )

    # 15-C: YAML files must parse.
    try:
        import yaml
    except ImportError:
        yaml = None  # type: ignore[assignment]
    if yaml:
        for yname in YAML_FILES:
            yp = GDIR / yname
            if yp.exists():
                try:
                    yaml.safe_load(yp.read_text())
                except yaml.YAMLError as exc:
                    errors.append(f"docs/governance/{yname}: invalid YAML: {exc}")

    readme = GDIR / "README.md"
    if readme.exists():
        rtext = readme.read_text()
        for name in REQUIRED:
            if name == "README.md":
                continue
            if name not in rtext:
                errors.append(f"docs/governance/README.md: does not reference {name}")

if errors:
    print(f"{len(errors)} governance-doc issue(s):")
    for e in errors:
        print(f"  {e}")
    sys.exit(1)

print("✓ docs/governance/ skeletons present, fresh (<365d), and indexed")
