#!/usr/bin/env python3
"""Alertmanager wiring (13-D regression).

Alertmanager is what turns alert rules into actual notifications. 13-E
and 13-F already land rules (JA4proxyDown, CertExpiringSoon, etc.);
without 13-D those rules fire into /dev/null.

Assertions:
  1. group_vars declares ja4proxy_docker_image_alertmanager and SMTP
     vars (smarthost / from / to). Empty SMTP values are permitted —
     deployments without a smarthost fall back to heartbeat-only
     monitoring and CI must tolerate the opt-out.
  2. Role 09's digest short-name map includes alertmanager so the
     digest-pinning flow covers it.
  3. docker-compose.yml.j2 has an alertmanager service, bound to
     loopback outside the live stage, volume-mounts the config.
  4. alertmanager.yml.j2 exists and parses as YAML with a `route:` +
     at least one `receivers:` entry.
  5. prometheus.yml.j2 has an `alerting:` block referencing
     alertmanager:9093 so Prometheus can find it.
  6. generate-secrets.sh generates or skips smtp_password (so a
     deployment that wants email delivery has it available, while
     existing deployments without it still succeed).
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

try:
    import yaml
    from jinja2 import Environment
except ImportError:
    sys.exit("pyyaml / jinja2 not installed. Run: make lint-install")

ROOT = Path(__file__).resolve().parents[2]
GV = ROOT / "deploy" / "inventory" / "group_vars" / "all.yml"
ROLE09 = ROOT / "deploy" / "roles" / "09-image-digests" / "tasks" / "main.yml"
COMPOSE = ROOT / "deploy" / "templates" / "docker-compose.yml.j2"
AM = ROOT / "deploy" / "templates" / "alertmanager.yml.j2"
PROM = ROOT / "deploy" / "templates" / "prometheus.yml.j2"
SECRETS_SH = ROOT / "deploy" / "scripts" / "generate-secrets.sh"

errors: list[str] = []

gv_text = GV.read_text()
for key in (
    "ja4proxy_docker_image_alertmanager",
    "ja4proxy_alertmanager_smtp_smarthost",
    "ja4proxy_alertmanager_from",
    "ja4proxy_alertmanager_to",
):
    if not re.search(rf"^{re.escape(key)}\s*:", gv_text, re.MULTILINE):
        errors.append(f"group_vars/all.yml: missing {key}")

role09 = ROLE09.read_text()
if "alertmanager:" not in role09 or "prom/alertmanager" not in role09:
    errors.append("role 09: digest_image_short map does not include alertmanager → prom/alertmanager")
if "'alertmanager'" not in role09:
    errors.append("role 09: resolved_digests short-name list does not include 'alertmanager'")

compose_text = COMPOSE.read_text()
if not re.search(r"^\s{2}alertmanager:\s*$", compose_text, re.MULTILINE):
    errors.append("docker-compose.yml.j2: no `alertmanager:` service block")
if "127.0.0.1:9093:9093" not in compose_text:
    errors.append("docker-compose.yml.j2: alertmanager not loopback-bound outside live stage")
if "alertmanager.yml" not in compose_text:
    errors.append("docker-compose.yml.j2: alertmanager service does not mount alertmanager.yml")

if not AM.exists():
    errors.append("alertmanager.yml.j2: missing")
else:
    gv = yaml.safe_load(gv_text) or {}
    ctx = {
        **gv,
        "ja4proxy_secrets": {"smtp_password": "sample"},
        "smtp_password": "sample",
    }
    try:
        rendered = Environment().from_string(AM.read_text()).render(**ctx)
        doc = yaml.safe_load(rendered)
    except Exception as e:
        errors.append(f"alertmanager.yml.j2: render/parse failed: {e}")
        doc = None
    if isinstance(doc, dict):
        if "route" not in doc:
            errors.append("alertmanager.yml.j2: no top-level `route:`")
        recs = doc.get("receivers") or []
        if not recs:
            errors.append("alertmanager.yml.j2: no `receivers:` entries")

prom_text = PROM.read_text()
if not re.search(r"^alerting\s*:", prom_text, re.MULTILINE):
    errors.append("prometheus.yml.j2: no `alerting:` block")
if "alertmanager:9093" not in prom_text:
    errors.append("prometheus.yml.j2: `alerting:` does not target alertmanager:9093")

sh = SECRETS_SH.read_text()
if "smtp_password" not in sh:
    errors.append("generate-secrets.sh: does not handle smtp_password")

if errors:
    print(f"{len(errors)} alertmanager issue(s):")
    for e in errors:
        print(f"  {e}")
    sys.exit(1)

print("✓ Alertmanager wired: compose service, config template, Prometheus alerting block, secret")
