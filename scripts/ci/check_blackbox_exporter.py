#!/usr/bin/env python3
"""blackbox_exporter + cert-expiry rule hygiene (13-F regression).

Blackbox probes ja4proxy's public HTTPS endpoint so Prometheus can
expose probe_ssl_earliest_cert_expiry — the metric a CertExpiringSoon
alert fires on. Until 13-D/Alertmanager lands, the rule doesn't
deliver; this check only asserts the *configuration* is ready.

Assertions:
  1. group_vars declares ja4proxy_docker_image_blackbox_exporter.
  2. Role 09's digest map covers blackbox_exporter (so the render
     check + digest pin don't fail).
  3. deploy/templates/docker-compose.yml.j2 has a blackbox_exporter
     service, loopback-bound outside the live stage.
  4. deploy/templates/blackbox.yml.j2 exists with an https_2xx module.
  5. deploy/templates/prometheus.yml.j2 scrapes blackbox with a
     target pointing at https://{{ ja4proxy_domain }} and declares
     rule_files:.
  6. deploy/files/prometheus/alert-rules.yml has a CertExpiringSoon
     alert referencing probe_ssl_earliest_cert_expiry.
"""
from __future__ import annotations

import sys
from pathlib import Path

try:
    import yaml
except ImportError:
    sys.exit("pyyaml not installed. Run: make lint-install")

ROOT = Path(__file__).resolve().parents[2]
GV = ROOT / "deploy" / "inventory" / "group_vars" / "all.yml"
ROLE09 = ROOT / "deploy" / "roles" / "09-image-digests" / "tasks" / "main.yml"
COMPOSE = ROOT / "deploy" / "templates" / "docker-compose.yml.j2"
BLACKBOX = ROOT / "deploy" / "templates" / "blackbox.yml.j2"
PROMETHEUS = ROOT / "deploy" / "templates" / "prometheus.yml.j2"
RULES = ROOT / "deploy" / "files" / "prometheus" / "alert-rules.yml"

errors: list[str] = []

gv = GV.read_text()
if "ja4proxy_docker_image_blackbox_exporter" not in gv:
    errors.append(f"{GV.relative_to(ROOT)}: missing ja4proxy_docker_image_blackbox_exporter")

r9 = ROLE09.read_text()
if "blackbox_exporter" not in r9 or "blackbox-exporter" not in r9:
    errors.append(
        f"{ROLE09.relative_to(ROOT)}: blackbox_exporter not wired into digest map "
        "(need both 'blackbox_exporter' key and 'blackbox-exporter' short-name)"
    )

c = COMPOSE.read_text()
if "blackbox_exporter" not in c and "blackbox-exporter" not in c:
    errors.append(f"{COMPOSE.relative_to(ROOT)}: no blackbox exporter service")
if "ja4proxy_docker_image_blackbox_exporter" not in c:
    errors.append(
        f"{COMPOSE.relative_to(ROOT)}: blackbox service missing image var reference"
    )

if not BLACKBOX.exists():
    errors.append(f"{BLACKBOX.relative_to(ROOT)}: missing")
else:
    b = BLACKBOX.read_text()
    if "https_2xx" not in b:
        errors.append(f"{BLACKBOX.relative_to(ROOT)}: no https_2xx module")

p = PROMETHEUS.read_text()
if "rule_files" not in p:
    errors.append(f"{PROMETHEUS.relative_to(ROOT)}: no rule_files: directive")
if "blackbox" not in p.lower():
    errors.append(f"{PROMETHEUS.relative_to(ROOT)}: no blackbox scrape job")
if "ja4proxy_domain" not in p:
    errors.append(
        f"{PROMETHEUS.relative_to(ROOT)}: blackbox target does not use ja4proxy_domain"
    )

if not RULES.exists():
    errors.append(f"{RULES.relative_to(ROOT)}: missing")
else:
    try:
        doc = yaml.safe_load(RULES.read_text())
    except yaml.YAMLError as exc:
        errors.append(f"{RULES.relative_to(ROOT)}: not valid YAML: {exc}")
        doc = None
    if isinstance(doc, dict):
        rules_text = RULES.read_text()
        if "CertExpiringSoon" not in rules_text:
            errors.append(f"{RULES.relative_to(ROOT)}: no CertExpiringSoon alert")
        if "probe_ssl_earliest_cert_expiry" not in rules_text:
            errors.append(
                f"{RULES.relative_to(ROOT)}: CertExpiringSoon does not reference "
                "probe_ssl_earliest_cert_expiry"
            )

if errors:
    print(f"{len(errors)} blackbox/cert-expiry issue(s):")
    for e in errors:
        print(f"  {e}")
    sys.exit(1)

print("✓ blackbox_exporter wired, probe target set, CertExpiringSoon rule declared")
