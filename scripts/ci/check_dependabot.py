#!/usr/bin/env python3
"""18-F: Assert .github/dependabot.yml stays valid and covers the
ecosystems we care about. The Dependabot spec itself says no CI
hook is needed, but a 5-line offline guard stops an accidental
deletion from going unnoticed.
"""
from __future__ import annotations

import sys
from pathlib import Path

try:
    import yaml
except ImportError:
    sys.exit("pyyaml not installed. Run: make lint-install")

ROOT = Path(__file__).resolve().parents[2]
CONFIG = ROOT / ".github" / "dependabot.yml"

REQUIRED_ECOSYSTEMS = {"pip", "github-actions"}


def main() -> int:
    if not CONFIG.exists():
        sys.exit(f"missing: {CONFIG.relative_to(ROOT)}")

    try:
        doc = yaml.safe_load(CONFIG.read_text())
    except yaml.YAMLError as e:
        sys.exit(f"{CONFIG.relative_to(ROOT)} is not valid YAML: {e}")

    if doc.get("version") != 2:
        sys.exit(f"{CONFIG.relative_to(ROOT)} must declare version: 2")

    updates = doc.get("updates")
    if not isinstance(updates, list) or not updates:
        sys.exit(f"{CONFIG.relative_to(ROOT)} has no `updates:` entries")

    ecosystems = {u.get("package-ecosystem") for u in updates}
    missing = REQUIRED_ECOSYSTEMS - ecosystems
    if missing:
        sys.exit(
            f"{CONFIG.relative_to(ROOT)} missing required ecosystems: "
            f"{sorted(missing)} (have: {sorted(ecosystems)})"
        )

    for u in updates:
        eco = u.get("package-ecosystem")
        sched = u.get("schedule", {}).get("interval")
        if sched not in ("daily", "weekly", "monthly"):
            sys.exit(f"{eco}: schedule.interval {sched!r} is not a valid cadence")

    print(f"✓ .github/dependabot.yml: {len(updates)} ecosystems, covers {sorted(REQUIRED_ECOSYSTEMS)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
