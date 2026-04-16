#!/usr/bin/env python3
"""Render deploy/templates/docker-compose.yml.j2 with sample vars.

Verifies:
  - Jinja2 renders without error under realistic variable inputs.
  - The result is valid YAML (pyyaml parses it).
  - Every service has a top-level `image:` field, and each image matches
    one of our pinned short-names (so role 09 can actually pin them).
  - No {{ placeholder }} leaked through.
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
TEMPLATE = ROOT / "deploy" / "templates" / "docker-compose.yml.j2"
GROUP_VARS = ROOT / "deploy" / "inventory" / "group_vars" / "all.yml"

# Use real defaults where we have them; dummy values for play-level facts.
gv = yaml.safe_load(GROUP_VARS.read_text()) or {}
ctx = {
    **gv,
    "redis_password": "sample-redis-password",
    "grafana_admin_password": "sample-grafana-password",
    "grafana_password": "sample-grafana-password",
    "redis_signing_key": "sample-signing-key",
    "haproxy_stats_password": "sample-stats-password",
    "haproxy_stats_user": "haproxy-admin",
    "ja4proxy_domain": "test-honeypot.example.com",
    "ja4proxy_admin_ip": "203.0.113.10",
}

env = Environment()
tmpl = env.from_string(TEMPLATE.read_text())
try:
    rendered = tmpl.render(**ctx)
except Exception as e:
    sys.exit(f"jinja2 render failed: {e}")

if "{{" in rendered or "}}" in rendered:
    stray = [ln for ln in rendered.splitlines() if "{{" in ln or "}}" in ln]
    sys.exit("stray template placeholders:\n  " + "\n  ".join(stray))

try:
    doc = yaml.safe_load(rendered)
except yaml.YAMLError as e:
    sys.exit(f"rendered compose is not valid YAML: {e}")

if not isinstance(doc, dict) or "services" not in doc:
    sys.exit("rendered compose has no services: block")

# Every service should carry an image: field after render.
missing = [name for name, spec in doc["services"].items()
           if not isinstance(spec, dict) or "image" not in spec]
if missing:
    sys.exit("services missing image: " + ", ".join(missing))

# Every image value should use a short-name that role 09 knows about.
role09 = (ROOT / "deploy" / "roles" / "09-image-digests" / "tasks" / "main.yml").read_text()
map_block = re.search(
    r"digest_image_short:\s*\n((?:[ ]{6}[a-z_]+:[ ]+\S+\n)+)", role09
)
shorts = set()
if map_block:
    shorts = set(re.findall(r"^\s+[a-z_]+:\s+(\S+)", map_block.group(1), re.MULTILINE))

unknown = []
for name, spec in doc["services"].items():
    img = spec["image"]
    short = img.split(":", 1)[0].split("@", 1)[0]
    if short not in shorts:
        unknown.append(f"{name} uses image '{img}' (short={short}) — not in role 09 map")

if unknown:
    print("image short-names not covered by role 09 digest map:")
    for u in unknown:
        print(f"  {u}")
    sys.exit(1)

# Every depends_on target must name an existing service.
service_names = set(doc["services"].keys())
bad_deps = []
for name, spec in doc["services"].items():
    deps = spec.get("depends_on", {})
    # depends_on can be a list or a dict (long form)
    if isinstance(deps, list):
        dep_names = deps
    elif isinstance(deps, dict):
        dep_names = list(deps.keys())
    else:
        continue
    for dep in dep_names:
        if dep not in service_names:
            bad_deps.append(f"{name} depends_on '{dep}' — service does not exist")

if bad_deps:
    print("depends_on targets missing from services:")
    for b in bad_deps:
        print(f"  {b}")
    sys.exit(1)

deps_count = sum(
    len(spec.get("depends_on", {}))
    for spec in doc["services"].values()
    if isinstance(spec, dict)
)
print(
    f"✓ compose renders, valid YAML, {len(doc['services'])} services, "
    f"all images pinnable, {deps_count} depends_on edges valid"
)
