#!/usr/bin/env python3
"""Privacy page hygiene (11-B regression).

GDPR Article 13 requires an EU-facing service — decoy or not — to
disclose controller, lawful basis, purposes, retention, recipients,
and data subject rights. The honeypot serves this at /privacy.html.

Assertions:
  1. deploy/templates/privacy.html.j2 exists and renders cleanly with
     sample vars.
  2. Rendered output contains the required section headings.
  3. Rendered output quotes the retention period from
     ja4proxy_loki_retention_days / ja4proxy_prometheus_retention_days.
  4. Role 02 deploys the template to caddy/html/privacy.html.
  5. Role 07 smoke-tests /privacy.html for a data-subject-rights marker.
  6. The landing page links to /privacy.html.
"""
from __future__ import annotations

import sys
from pathlib import Path

try:
    import jinja2
    import yaml
except ImportError:
    sys.exit("pyyaml / jinja2 not installed. Run: make lint-install")

ROOT = Path(__file__).resolve().parents[2]
TPL = ROOT / "deploy" / "templates" / "privacy.html.j2"
INDEX = ROOT / "deploy" / "templates" / "honeypot-index.html"
DEPLOY_TASK = ROOT / "deploy" / "roles" / "02-artifact-build" / "tasks" / "deploy-configs.yml"
VALIDATE_TASK = ROOT / "deploy" / "roles" / "07-validation" / "tasks" / "main.yml"
GROUP_VARS = ROOT / "deploy" / "inventory" / "group_vars" / "all.yml"

REQUIRED_HEADINGS = (
    "Controller",
    "Lawful basis",
    "Purposes",
    "Retention",
    "Recipients",
    "Rights",
)

errors: list[str] = []

if not TPL.exists():
    errors.append(f"{TPL.relative_to(ROOT)}: missing")
else:
    gv = yaml.safe_load(GROUP_VARS.read_text()) or {}
    env = jinja2.Environment(
        loader=jinja2.FileSystemLoader(str(TPL.parent)),
        autoescape=True,
    )
    try:
        rendered = env.get_template(TPL.name).render(
            ansible_managed="ansible managed",
            ja4proxy_domain="example.test",
            ja4proxy_loki_retention_days=gv.get("ja4proxy_loki_retention_days", 90),
            ja4proxy_prometheus_retention_days=gv.get(
                "ja4proxy_prometheus_retention_days", 90
            ),
        )
    except jinja2.TemplateError as exc:
        errors.append(f"{TPL.relative_to(ROOT)}: render failed: {exc}")
        rendered = ""

    for heading in REQUIRED_HEADINGS:
        if heading.lower() not in rendered.lower():
            errors.append(
                f"{TPL.relative_to(ROOT)}: rendered page missing `{heading}`"
            )

    retention = str(gv.get("ja4proxy_loki_retention_days", 90))
    if retention not in rendered:
        errors.append(
            f"{TPL.relative_to(ROOT)}: retention period ({retention} days) "
            "not quoted in rendered page"
        )

    for needle in ("abuse@", "privacy@"):
        if needle not in rendered:
            errors.append(f"{TPL.relative_to(ROOT)}: missing `{needle}` contact")

if INDEX.exists() and "privacy.html" not in INDEX.read_text():
    errors.append(f"{INDEX.relative_to(ROOT)}: landing page does not link to /privacy.html")

if DEPLOY_TASK.exists() and "privacy.html" not in DEPLOY_TASK.read_text():
    errors.append(f"{DEPLOY_TASK.relative_to(ROOT)}: no task deploys privacy.html")

if VALIDATE_TASK.exists():
    v = VALIDATE_TASK.read_text()
    if "privacy.html" not in v:
        errors.append(
            f"{VALIDATE_TASK.relative_to(ROOT)}: missing smoke test for /privacy.html"
        )

if errors:
    print(f"{len(errors)} privacy page issue(s):")
    for e in errors:
        print(f"  {e}")
    sys.exit(1)

print("✓ privacy.html.j2 renders with GDPR sections, deployed, linked, smoke-tested")
