#!/usr/bin/env python3
"""16-C: Validate every .json file in the repo parses cleanly."""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SKIP_DIRS = {".git", ".venv", ".venv-dev", "node_modules"}

errors: list[str] = []
checked = 0

for f in sorted(REPO.rglob("*.json")):
    if any(d in f.parts for d in SKIP_DIRS):
        continue
    checked += 1
    try:
        json.loads(f.read_text(encoding="utf-8-sig"))
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        errors.append(f"{f.relative_to(REPO)}: {exc}")

if errors:
    print("JSON validation failures:")
    for e in errors:
        print(f"  {e}")
    sys.exit(1)

print(f"✓ {checked} JSON files validated")
