#!/usr/bin/env python3
"""Cross-check:

  1. Every `{{ ja4proxy_* }}` reference in templates is defined in
     deploy/inventory/group_vars/all.yml OR is a play-level fact that
     we know is set in site.yml pre_tasks / vars / vars_prompt / loaded
     from the vault.
  2. Every `ja4proxy_docker_image_*` in group_vars has a corresponding
     entry in role 09's digest_image_short mapping — otherwise the
     digest-pin assertion will fail at deploy time.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
GROUP_VARS = ROOT / "deploy" / "inventory" / "group_vars" / "all.yml"
TEMPLATES = ROOT / "deploy" / "templates"
ROLE_09_TASKS = ROOT / "deploy" / "roles" / "09-image-digests" / "tasks" / "main.yml"
SITE_YML = ROOT / "deploy" / "playbooks" / "site.yml"

gv_text = GROUP_VARS.read_text()
defined = set(re.findall(r"^(ja4proxy_[a-z0-9_]+)\s*:", gv_text, re.MULTILINE))

# Play-level facts set in site.yml (from secrets, env overrides, prompts).
play_facts = set(
    re.findall(r"^\s*ja4proxy_[a-z0-9_]+\b", SITE_YML.read_text(), re.MULTILINE)
)
play_facts |= {
    "ja4proxy_domain", "ja4proxy_vm_host", "ja4proxy_ssh_user",
    "ja4proxy_admin_ip", "ja4proxy_ssh_public_key",
    "ja4proxy_build_machine_go_path", "ja4proxy_prebuilt_binary_path",
    "ja4proxy_geoip_file_path",
    # Injected from vault-loaded ja4proxy_secrets:
    "redis_password", "grafana_admin_password", "grafana_password",
    "redis_signing_key", "haproxy_stats_password", "haproxy_stats_user",
    # 13-D: vault-loaded secrets dict used in alertmanager.yml.j2 as
    # `ja4proxy_secrets.smtp_password`. Referenced only in templates;
    # not declared in group_vars.
    "ja4proxy_secrets",
}
known = defined | play_facts

errors: list[str] = []
var_pattern = re.compile(r"\{\{\s*([a-z_][a-z0-9_]*)\b")
for template in TEMPLATES.rglob("*.j2"):
    text = template.read_text()
    for name in var_pattern.findall(text):
        if name.startswith("ja4proxy_") and name not in known:
            errors.append(f"{template.relative_to(ROOT)}: undefined {{{{ {name} }}}}")
        if name in {"redis_password", "grafana_admin_password",
                    "grafana_password", "redis_signing_key",
                    "haproxy_stats_password", "haproxy_stats_user"}:
            # These come from the vault; fine.
            continue

# Role 09 digest map must cover every image variable.
r9 = ROLE_09_TASKS.read_text()
map_match = re.search(
    r"digest_image_short:\s*\n((?:[ ]{6}[a-z_]+:[ ]+\S+\n)+)", r9
)
if not map_match:
    errors.append("role 09: digest_image_short block not found — regex drift?")
    map_keys = set()
else:
    map_keys = set(re.findall(r"^\s+([a-z_]+):\s", map_match.group(1), re.MULTILINE))

image_vars = re.findall(r"^ja4proxy_docker_image_([a-z0-9_]+)\s*:", gv_text, re.MULTILINE)
for short in image_vars:
    if short not in map_keys:
        errors.append(
            f"role 09: digest_image_short is missing entry for '{short}' — "
            "add it or the digest-pin assert will fail at deploy"
        )

if errors:
    print(f"{len(errors)} coverage error(s):")
    for e in errors:
        print(f"  {e}")
    sys.exit(1)

print(f"✓ {len(known)} known vars, all template refs resolved, "
      f"digest map covers {len(image_vars)} image(s)")
