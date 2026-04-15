#!/usr/bin/env python3
"""Parse every .j2 template with Jinja2's parser.

Catches undeclared blocks, broken control flow, and unmatched tags
without needing the templates to render against real variables.
"""
from __future__ import annotations

import sys
from pathlib import Path

try:
    from jinja2 import Environment
    from jinja2.exceptions import TemplateSyntaxError
except ImportError:
    sys.exit("jinja2 not installed. Run: make lint-install")

ROOT = Path(__file__).resolve().parents[2]
TEMPLATE_DIRS = [ROOT / "deploy" / "templates", ROOT / "deploy" / "roles"]

env = Environment()
errors: list[str] = []
checked = 0

for root in TEMPLATE_DIRS:
    for path in root.rglob("*.j2"):
        checked += 1
        try:
            env.parse(path.read_text())
        except TemplateSyntaxError as e:
            errors.append(f"{path.relative_to(ROOT)}:{e.lineno}: {e.message}")

if errors:
    print(f"{len(errors)} Jinja2 syntax error(s) across {checked} template(s):")
    for err in errors:
        print(f"  {err}")
    sys.exit(1)

print(f"✓ {checked} template(s) parse cleanly")
