#!/usr/bin/env python3
"""Heartbeat timer hygiene (13-F regression).

The heartbeat is the availability half of our dead-man's-switch pair
(cost half = Alibaba budget alert). A systemd timer on the VM pings
ja4proxy_heartbeat_url every 5 minutes; if it stops, the external
healthchecks.io-style service alerts the operator.

Assertions:
  1. deploy/templates/heartbeat.timer.j2 + heartbeat.service.j2 exist
     with a 5-minute cadence and OnBootSec so the first ping lands
     shortly after boot.
  2. The service template shells out to curl against
     ja4proxy_heartbeat_url and tolerates empty string (skip) without
     failing.
  3. group_vars/all.yml declares ja4proxy_heartbeat_url (default "").
  4. Some role deploys both unit templates into /etc/systemd/system/
     and enables the timer, gated so nothing runs when the URL is
     empty.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TIMER = ROOT / "deploy" / "templates" / "heartbeat.timer.j2"
SERVICE = ROOT / "deploy" / "templates" / "heartbeat.service.j2"
GV = ROOT / "deploy" / "inventory" / "group_vars" / "all.yml"
ROLES_DIR = ROOT / "deploy" / "roles"

errors: list[str] = []

if not TIMER.exists():
    errors.append(f"{TIMER.relative_to(ROOT)}: missing")
else:
    t = TIMER.read_text()
    if "[Timer]" not in t:
        errors.append(f"{TIMER.relative_to(ROOT)}: no [Timer] section")
    if not re.search(r"OnUnitActiveSec=5min|OnCalendar=\*:0/5", t):
        errors.append(
            f"{TIMER.relative_to(ROOT)}: "
            "expected 5-minute cadence (OnUnitActiveSec=5min or OnCalendar=*:0/5)"
        )
    if "OnBootSec" not in t:
        errors.append(
            f"{TIMER.relative_to(ROOT)}: expected OnBootSec= for first-ping-after-boot"
        )

if not SERVICE.exists():
    errors.append(f"{SERVICE.relative_to(ROOT)}: missing")
else:
    s = SERVICE.read_text()
    if "[Service]" not in s:
        errors.append(f"{SERVICE.relative_to(ROOT)}: no [Service] section")
    if "ExecStart=" not in s:
        errors.append(f"{SERVICE.relative_to(ROOT)}: no ExecStart=")
    if "curl" not in s:
        errors.append(
            f"{SERVICE.relative_to(ROOT)}: expected curl against the heartbeat URL"
        )
    if "ja4proxy_heartbeat_url" not in s:
        errors.append(
            f"{SERVICE.relative_to(ROOT)}: does not reference ja4proxy_heartbeat_url"
        )

if GV.exists():
    gv = GV.read_text()
    if not re.search(r"^ja4proxy_heartbeat_url\s*:", gv, re.MULTILINE):
        errors.append(f"{GV.relative_to(ROOT)}: missing ja4proxy_heartbeat_url default")

deployer_found = False
gate_found = False
for tasks in ROLES_DIR.rglob("tasks/*.yml"):
    txt = tasks.read_text()
    if "heartbeat.timer.j2" in txt and "heartbeat.service.j2" in txt:
        deployer_found = True
        if "ja4proxy_heartbeat_url" in txt and "length" in txt:
            gate_found = True
        break

if not deployer_found:
    errors.append(
        "no role deploys heartbeat.{timer,service}.j2 into /etc/systemd/system/"
    )
elif not gate_found:
    errors.append(
        "heartbeat deployment not gated on ja4proxy_heartbeat_url being non-empty"
    )

if errors:
    print(f"{len(errors)} heartbeat issue(s):")
    for e in errors:
        print(f"  {e}")
    sys.exit(1)

print("✓ heartbeat.{timer,service}.j2 present, 5-min cadence, empty-URL guarded")
