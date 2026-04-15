#!/usr/bin/env python3
"""Assert every target defined in the root Makefile is declared .PHONY.

Real-file targets (sentinels like $(VENV)/.installed) are exempt — they
correspond to actual files on disk that make should stat for freshness.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MAKEFILE = ROOT / "Makefile"

text = MAKEFILE.read_text()

phony: set[str] = set()
for line in text.splitlines():
    m = re.match(r"^\.PHONY:\s*(.+)$", line)
    if m:
        phony.update(m.group(1).split())

# A target line: "name: deps" at column 0, name is a simple identifier.
# Match `name:` or `name: deps`, but NOT make assignments like
# `NAME := value`, `NAME = value`, `NAME ?= value`, `NAME += value`.
target_re = re.compile(r"^([A-Za-z][A-Za-z0-9_-]*)\s*:(?![=])(?!\s*=)")
targets: set[str] = set()
for line in text.splitlines():
    if line.startswith("\t"):
        continue
    m = target_re.match(line)
    if m:
        targets.add(m.group(1))

missing = sorted(targets - phony)
if missing:
    print("targets not declared .PHONY:")
    for t in missing:
        print(f"  {t}")
    sys.exit(1)

print(f"✓ all {len(targets)} Makefile targets are .PHONY")
