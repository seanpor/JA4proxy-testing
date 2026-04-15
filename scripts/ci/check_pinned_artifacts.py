#!/usr/bin/env python3
"""Pinned artifact hygiene (14-B regression).

Assert:
  1. deploy/expected-binary-sha256.txt exists, is a single line, and
     parses as `<64-hex>  <name>` (sha256sum -c format).
  2. Role 02 build.yml references the pin file so it can't be silently
     deleted without failing this test too.

Empty/sentinel pin (64 zeros) is allowed — that's the "no binary
pinned yet" state. The playbook skips the assertion in that case so
offline smoke tests still work.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PIN = ROOT / "deploy" / "expected-binary-sha256.txt"
BUILD_TASK = ROOT / "deploy" / "roles" / "02-artifact-build" / "tasks" / "build.yml"

LINE_RE = re.compile(r"^([0-9a-f]{64})\s+(\S+)\s*$")

errors: list[str] = []

if not PIN.exists():
    errors.append(f"{PIN.relative_to(ROOT)}: missing — add one-line sha256sum")
else:
    lines = [ln for ln in PIN.read_text().splitlines() if ln.strip()]
    if len(lines) != 1:
        errors.append(
            f"{PIN.relative_to(ROOT)}: expected exactly 1 non-empty line, "
            f"got {len(lines)}"
        )
    elif not LINE_RE.match(lines[0]):
        errors.append(
            f"{PIN.relative_to(ROOT)}: line does not match `<64-hex>  <name>` "
            f"(got `{lines[0][:80]}`)"
        )

build_text = BUILD_TASK.read_text()
if "expected-binary-sha256.txt" not in build_text:
    errors.append(
        f"{BUILD_TASK.relative_to(ROOT)}: does not reference "
        "expected-binary-sha256.txt — pin would be unused"
    )

if errors:
    print(f"{len(errors)} pinned-artifact issue(s):")
    for e in errors:
        print(f"  {e}")
    sys.exit(1)

print("✓ expected-binary-sha256.txt well-formed and referenced by role 02")
