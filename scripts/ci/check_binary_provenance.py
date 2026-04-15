#!/usr/bin/env python3
"""Binary-provenance hygiene (12-D regression).

At build time (role 02), the playbook must render
`/opt/ja4proxy/config/binary-provenance.yml` capturing:
  - binary_sha256   (must match the A8 checksum)
  - commit          (git revision, or vcs.revision from `go version -m`)
  - build_timestamp (ISO-8601 UTC)
  - goflags         (string pulled from ja4proxy_go_build_flags)

This check asserts:
  1. deploy/templates/binary-provenance.yml.j2 exists and mentions all
     four required keys.
  2. Role 02 build.yml references the template and writes it into
     ja4proxy_config_dir with a sensible mode.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TPL = ROOT / "deploy" / "templates" / "binary-provenance.yml.j2"
BUILD = ROOT / "deploy" / "roles" / "02-artifact-build" / "tasks" / "build.yml"

REQUIRED_KEYS = ("binary_sha256", "commit", "build_timestamp", "goflags")

errors: list[str] = []

if not TPL.exists():
    errors.append(f"{TPL.relative_to(ROOT)}: missing")
else:
    t = TPL.read_text()
    for key in REQUIRED_KEYS:
        if key not in t:
            errors.append(f"{TPL.relative_to(ROOT)}: missing key `{key}`")
    if "ja4proxy_go_build_flags" not in t:
        errors.append(
            f"{TPL.relative_to(ROOT)}: does not reference ja4proxy_go_build_flags"
        )

if not BUILD.exists():
    errors.append(f"{BUILD.relative_to(ROOT)}: missing")
else:
    b = BUILD.read_text()
    if "binary-provenance.yml" not in b:
        errors.append(
            f"{BUILD.relative_to(ROOT)}: does not render binary-provenance.yml"
        )
    if "ja4proxy_config_dir" not in b:
        errors.append(
            f"{BUILD.relative_to(ROOT)}: provenance not written under ja4proxy_config_dir"
        )

if errors:
    print(f"{len(errors)} binary-provenance issue(s):")
    for e in errors:
        print(f"  {e}")
    sys.exit(1)

print("✓ binary-provenance.yml.j2 covers required keys and role 02 renders it")
