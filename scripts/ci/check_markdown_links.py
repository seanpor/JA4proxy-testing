#!/usr/bin/env python3
"""17-F: Verify relative links in markdown files point to existing files."""
from __future__ import annotations

import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SKIP_DIRS = {".git", ".venv", ".venv-dev", "node_modules", ".qwen"}

# Match [text](relative/path) but not URLs, anchors-only, or images from URLs
LINK_RE = re.compile(r"\[([^\]]*)\]\(([^)]+)\)")

errors: list[str] = []
checked = 0

for md in sorted(REPO.rglob("*.md")):
    if any(d in md.parts for d in SKIP_DIRS):
        continue
    text = md.read_text(errors="replace")
    for lineno, line in enumerate(text.splitlines(), 1):
        for m in LINK_RE.finditer(line):
            target = m.group(2).strip()
            # Skip URLs
            if target.startswith(("http://", "https://", "mailto:")):
                continue
            # Skip pure anchors
            if target.startswith("#"):
                continue
            # Strip anchor from path#anchor
            path_part = target.split("#")[0]
            if not path_part:
                continue
            # Resolve relative to the markdown file's directory
            resolved = (md.parent / path_part).resolve()
            checked += 1
            if not resolved.exists():
                rel_md = md.relative_to(REPO)
                errors.append(f"{rel_md}:{lineno}: [{m.group(1)}]({target}) -> not found")

if errors:
    print(f"Broken markdown links ({len(errors)}):")
    for e in errors:
        print(f"  {e}")
    sys.exit(1)

print(f"✓ {checked} markdown relative links verified")
