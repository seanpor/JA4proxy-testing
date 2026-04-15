#!/usr/bin/env python3
"""Go-live preflight tasks (11-D + 13-G regression).

Assert that deploy/roles/10-go-live/tasks/main.yml contains:
  - A `dig +short MX {{ ja4proxy_domain }}` preflight (11-D) with
    an assertion on stdout and the `ja4proxy_skip_mx_preflight`
    escape hatch.
  - A `dig +short A {{ ja4proxy_domain }}` preflight (13-G) with
    the `ja4proxy_skip_dns_preflight` escape hatch.

Can't actually resolve DNS in CI — this just ensures the tasks exist
so a future refactor can't silently delete them.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TASK = ROOT / "deploy" / "roles" / "10-go-live" / "tasks" / "main.yml"

errors: list[str] = []

if not TASK.exists():
    errors.append(f"{TASK.relative_to(ROOT)}: missing")
else:
    text = TASK.read_text()
    for marker, why in (
        ("dig +short MX", "no MX dig preflight command"),
        ("_abuse_mx_preflight", "MX preflight result register removed"),
        ("_abuse_mx_preflight.stdout", "MX preflight assertion removed"),
        ("ja4proxy_skip_mx_preflight", "MX escape hatch removed"),
        ("dig +short A", "no A dig preflight command (13-G)"),
        ("_domain_a_preflight", "A preflight result register removed"),
        ("ja4proxy_skip_dns_preflight", "A escape hatch removed"),
    ):
        if marker not in text:
            errors.append(f"{TASK.relative_to(ROOT)}: {why} (missing `{marker}`)")

if errors:
    print(f"{len(errors)} preflight issue(s):")
    for e in errors:
        print(f"  {e}")
    sys.exit(1)

print("✓ role 10 still runs MX preflight with override before opening ports")
