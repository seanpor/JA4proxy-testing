#!/usr/bin/env python3
"""security.txt hygiene (11-C regression).

Assert:
  1. deploy/templates/security.txt.j2 exists with Contact:, Expires:,
     Preferred-Languages:, Canonical:.
  2. Role 02 deploys it under caddy/html/.well-known/.
  3. Role 07 smoke-tests /.well-known/security.txt for Contact/Expires.
  4. The template renders to valid text when fed a minimal vars dict
     (no Jinja errors, Contact and Expires appear in output).
"""
from __future__ import annotations

import sys
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, StrictUndefined

ROOT = Path(__file__).resolve().parents[2]
TEMPLATE = ROOT / "deploy" / "templates" / "security.txt.j2"
DEPLOY_TASK = ROOT / "deploy" / "roles" / "02-artifact-build" / "tasks" / "deploy-configs.yml"
VALIDATE_TASK = ROOT / "deploy" / "roles" / "07-validation" / "tasks" / "main.yml"

errors: list[str] = []

if not TEMPLATE.exists():
    errors.append(f"{TEMPLATE.relative_to(ROOT)}: missing")
else:
    raw = TEMPLATE.read_text()
    for needle in ("Contact:", "Expires:", "Preferred-Languages:", "Canonical:"):
        if needle not in raw:
            errors.append(f"{TEMPLATE.relative_to(ROOT)}: missing `{needle}`")

    env = Environment(
        loader=FileSystemLoader(str(TEMPLATE.parent)),
        undefined=StrictUndefined,
        keep_trailing_newline=True,
    )
    try:
        rendered = env.get_template(TEMPLATE.name).render(
            ansible_managed="Ansible managed",
            ja4proxy_domain="example.test",
            ansible_date_time={
                "iso8601": "2026-04-15T12:00:00Z",
                "year": "2026",
            },
        )
    except Exception as exc:
        errors.append(f"{TEMPLATE.relative_to(ROOT)}: render failed: {exc}")
        rendered = ""

    if rendered:
        if "Contact: mailto:" not in rendered:
            errors.append("rendered security.txt: no Contact: mailto: line")
        if "Expires: 2027-" not in rendered:
            errors.append(
                f"rendered security.txt: Expires: should advance year by 1 "
                f"(got: {[line for line in rendered.splitlines() if line.startswith('Expires:')]})"
            )

if DEPLOY_TASK.exists() and "security.txt.j2" not in DEPLOY_TASK.read_text():
    errors.append(f"{DEPLOY_TASK.relative_to(ROOT)}: no deploy task for security.txt.j2")

if VALIDATE_TASK.exists():
    v = VALIDATE_TASK.read_text()
    if ".well-known/security.txt" not in v or "Contact:" not in v or "Expires:" not in v:
        errors.append(
            f"{VALIDATE_TASK.relative_to(ROOT)}: no smoke test for "
            "/.well-known/security.txt with Contact/Expires assertions"
        )

if errors:
    print(f"{len(errors)} security.txt issue(s):")
    for e in errors:
        print(f"  {e}")
    sys.exit(1)

print("✓ security.txt.j2 renders with Contact+Expires; role 02 deploys it; role 07 smoke-tests it")
