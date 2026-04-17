#!/usr/bin/env python3
"""Validate 18-C govulncheck wiring in role 02.

We don't invoke govulncheck from CI — the scan runs against the
sibling Go source at deploy time, not in this repo's test harness.
This check is the offline guard that future edits don't silently
drop any link in the chain.

What it validates:

  - deploy/roles/02-artifact-build/tasks/build.yml has a probe,
    warn-on-missing, and run task, all delegated to localhost.
  - The probe uses `failed_when: false` so air-gapped build hosts
    don't hard-fail.
  - The run task uses `chdir: ja4proxy_build_machine_go_path` (the
    scan must read the source tree, not the role's own cwd).
  - The run task is gated on the probe succeeding AND
    ja4proxy_govulncheck_enabled, giving ops an explicit opt-out.
  - group_vars/all.yml declares ja4proxy_govulncheck_enabled: true.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BUILD_YML = ROOT / "deploy" / "roles" / "02-artifact-build" / "tasks" / "build.yml"
GROUP_VARS = ROOT / "deploy" / "inventory" / "group_vars" / "all.yml"


def _task_block(text: str, task_name_fragment: str) -> str:
    """Return the YAML block of the first task whose name contains fragment.

    Crude but reliable: find the task header, then return until the
    next `- name:` or end-of-file.
    """
    m = re.search(rf"- name:[^\n]*{re.escape(task_name_fragment)}[^\n]*\n", text)
    if not m:
        return ""
    start = m.start()
    rest = text[m.end():]
    nxt = re.search(r"\n\s*- name:", rest)
    return text[start: (m.end() + nxt.start()) if nxt else len(text)]


def check_build_yml() -> None:
    text = BUILD_YML.read_text()

    probe = _task_block(text, "Probe for govulncheck")
    warn = _task_block(text, "Warn when govulncheck is not installed")
    run = _task_block(text, "Run govulncheck against Go source tree")

    if not probe:
        sys.exit("build.yml has no `Probe for govulncheck` task")
    if not warn:
        sys.exit("build.yml has no `Warn when govulncheck is not installed` task")
    if not run:
        sys.exit("build.yml has no `Run govulncheck against Go source tree` task")

    required = [
        (probe, "govulncheck -version", "probe invokes `govulncheck -version`"),
        (probe, "delegate_to: localhost", "probe runs on control machine"),
        (probe, "failed_when: false", "probe is soft-fail (air-gapped)"),
        (probe, "register: _govulncheck_probe", "probe registers _govulncheck_probe"),
        (probe, "ja4proxy_govulncheck_enabled", "probe honours the enable flag"),
        (warn, "_govulncheck_probe.rc != 0", "warn gated on probe failure"),
        (run, "govulncheck ./...", "run uses `govulncheck ./...`"),
        (run, "chdir: \"{{ ja4proxy_build_machine_go_path }}\"",
         "run changes dir to the Go source tree"),
        (run, "delegate_to: localhost", "run executes on control machine"),
        (run, "_govulncheck_probe.rc == 0",
         "run gated on probe success (skip on air-gapped)"),
        (run, "ja4proxy_govulncheck_enabled", "run honours the enable flag"),
    ]
    errors = [msg for block, needle, msg in required if needle not in block]
    if errors:
        print("role 02 govulncheck wiring incomplete:")
        for e in errors:
            print(f"  - {e}")
        sys.exit(1)

    # The run task must NOT carry `failed_when: false` — a reachable
    # vuln is exactly what we want to abort the play on.
    if "failed_when: false" in run:
        sys.exit(
            "Run govulncheck task has `failed_when: false` — that would "
            "mask reachable vulnerabilities. Remove it."
        )

    # The run task must come AFTER the build binary step? No — spec puts
    # it BEFORE build, so a vuln stops us spending time cross-compiling.
    # Enforce ordering: probe → warn → run → Build JA4proxy binary.
    positions = {
        "probe": text.find("Probe for govulncheck"),
        "warn": text.find("Warn when govulncheck is not installed"),
        "run": text.find("Run govulncheck against Go source tree"),
        "build": text.find("Build JA4proxy binary (cross-compile"),
    }
    if not (0 < positions["probe"] < positions["warn"] < positions["run"] < positions["build"]):
        sys.exit(
            "govulncheck tasks must be ordered probe → warn → run, all before "
            "`Build JA4proxy binary` so vulns block the build"
        )

    print("✓ role 02 build.yml wires govulncheck with soft-fail probe, opt-out flag, correct order")


def check_group_vars() -> None:
    text = GROUP_VARS.read_text()
    m = re.search(r"^ja4proxy_govulncheck_enabled:\s*(\S+)\s*$", text, re.MULTILINE)
    if not m:
        sys.exit("group_vars/all.yml has no `ja4proxy_govulncheck_enabled:` declaration")
    if m.group(1) not in ("true", "True"):
        sys.exit(
            f"ja4proxy_govulncheck_enabled default is {m.group(1)!r} — "
            "should default to true so the gate is on out-of-the-box"
        )
    print("✓ group_vars/all.yml declares ja4proxy_govulncheck_enabled: true")


def main() -> int:
    check_build_yml()
    check_group_vars()
    return 0


if __name__ == "__main__":
    sys.exit(main())
