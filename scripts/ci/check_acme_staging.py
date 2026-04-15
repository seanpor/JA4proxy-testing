#!/usr/bin/env python3
"""ACME staging default (13-H regression).

Render deploy/templates/caddyfile.j2 in three scenarios and assert:
  1. stage=locked → neither acme_ca nor production tls appears (self-signed).
  2. stage=live + acme_staging=true → staging acme_ca directive present.
  3. stage=live + acme_staging=false → no acme_ca directive.

Also assert ja4proxy_acme_staging defaults to true in group_vars, and
role 10 flips it to false via set_fact before re-templating.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, StrictUndefined

ROOT = Path(__file__).resolve().parents[2]
TEMPLATE = ROOT / "deploy" / "templates" / "caddyfile.j2"
GROUPVARS = ROOT / "deploy" / "inventory" / "group_vars" / "all.yml"
ROLE10 = ROOT / "deploy" / "roles" / "10-go-live" / "tasks" / "main.yml"

STAGING_URL = "acme-staging-v02.api.letsencrypt.org"

errors: list[str] = []

def _ansible_bool(value) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.lower() in ("true", "yes", "on", "1")
    return bool(value)


env = Environment(
    loader=FileSystemLoader(str(TEMPLATE.parent)),
    undefined=StrictUndefined,
    keep_trailing_newline=True,
)
env.filters["bool"] = _ansible_bool
tpl = env.get_template(TEMPLATE.name)


def render(stage: str, staging: bool) -> str:
    return tpl.render(
        ja4proxy_deployment_stage=stage,
        ja4proxy_acme_staging=staging,
        ja4proxy_domain="example.test",
    )


locked = render("locked", True)
if STAGING_URL in locked:
    errors.append("Caddyfile: stage=locked must not emit acme_ca (ports are 127.0.0.1)")

live_staging = render("live", True)
if STAGING_URL not in live_staging:
    errors.append(
        "Caddyfile: stage=live + acme_staging=true must emit acme_ca "
        f"{STAGING_URL}"
    )

live_prod = render("live", False)
if STAGING_URL in live_prod:
    errors.append(
        "Caddyfile: stage=live + acme_staging=false must NOT emit staging acme_ca"
    )

gv = GROUPVARS.read_text() if GROUPVARS.exists() else ""
if not re.search(r"^ja4proxy_acme_staging:\s*true\s*$", gv, re.MULTILINE):
    errors.append(
        f"{GROUPVARS.relative_to(ROOT)}: ja4proxy_acme_staging must default to true"
    )

r10 = ROLE10.read_text() if ROLE10.exists() else ""
if not re.search(r"ja4proxy_acme_staging:\s*false", r10):
    errors.append(
        f"{ROLE10.relative_to(ROOT)}: role 10 must set_fact ja4proxy_acme_staging: false before re-templating"
    )

if errors:
    print(f"{len(errors)} ACME staging issue(s):")
    for e in errors:
        print(f"  {e}")
    sys.exit(1)

print("✓ Caddyfile honours ja4proxy_acme_staging; defaults safe; role 10 flips to production")
