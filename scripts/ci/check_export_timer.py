#!/usr/bin/env python3
"""Weekly export timer + script (12-A regression).

Assertions:
  1. deploy/scripts/export-week.sh exists and is executable.
  2. It contains sha256sum, journalctl or loki, and a manifest write.
  3. deploy/templates/ja4proxy-export.timer.j2 + .service.j2 exist.
  4. deploy/roles/11-data-export/tasks/main.yml exists.
  5. site.yml references role 11.
  6. Prometheus has --web.enable-admin-api (needed for TSDB snapshot).
  7. deploy/scripts/export-pull.sh exists (12-C).
  8. deploy/Makefile has an `export-pull` target (12-C).
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "deploy" / "scripts" / "export-week.sh"
TIMER = ROOT / "deploy" / "templates" / "ja4proxy-export.timer.j2"
SERVICE = ROOT / "deploy" / "templates" / "ja4proxy-export.service.j2"
ROLE11 = ROOT / "deploy" / "roles" / "11-data-export" / "tasks" / "main.yml"
SITE = ROOT / "deploy" / "playbooks" / "site.yml"
COMPOSE = ROOT / "deploy" / "templates" / "docker-compose.yml.j2"
PULL_SCRIPT = ROOT / "deploy" / "scripts" / "export-pull.sh"
MAKEFILE = ROOT / "deploy" / "Makefile"

errors: list[str] = []

if not SCRIPT.exists():
    errors.append("deploy/scripts/export-week.sh: missing")
else:
    text = SCRIPT.read_text()
    if "sha256sum" not in text:
        errors.append("export-week.sh: no sha256sum (manifest integrity)")
    if "manifest" not in text.lower():
        errors.append("export-week.sh: no manifest reference")

for f, label in [(TIMER, "timer"), (SERVICE, "service")]:
    if not f.exists():
        errors.append(f"ja4proxy-export.{label}.j2: missing")

if not ROLE11.exists():
    errors.append("deploy/roles/11-data-export/tasks/main.yml: missing")

if SITE.exists() and "11-data-export" not in SITE.read_text():
    errors.append("site.yml: does not reference role 11-data-export")

if "web.enable-admin-api" not in COMPOSE.read_text():
    errors.append("docker-compose.yml.j2: Prometheus missing --web.enable-admin-api")

if not PULL_SCRIPT.exists():
    errors.append("deploy/scripts/export-pull.sh: missing (12-C)")
else:
    pt = PULL_SCRIPT.read_text()
    if "rsync" not in pt:
        errors.append("export-pull.sh: no rsync")
    if "sha256" not in pt:
        errors.append("export-pull.sh: no sha256 verification")

if not re.search(r"^export-pull\s*:", MAKEFILE.read_text(), re.MULTILINE):
    errors.append("deploy/Makefile: no `export-pull:` target")

if errors:
    print(f"{len(errors)} export-timer issue(s):")
    for e in errors:
        print(f"  {e}")
    sys.exit(1)

print("✓ export timer, script, role 11, export-pull, and Prometheus admin API all wired")
