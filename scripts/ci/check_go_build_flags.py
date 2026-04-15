#!/usr/bin/env python3
"""Assert the Go build invocation carries -trimpath and -buildvcs=true
(14-A regression).

Rationale: without these flags, the emitted binary does not embed the
VCS revision, so `go version -m <binary>` cannot answer "which commit
produced this?". Phase 12 §4 (binary provenance) depends on it.

We don't own the sibling repo's Makefile, so we inject via GOFLAGS.
This check enforces that the build task in role 02 sets GOFLAGS and
that the default var in group_vars carries both flag tokens.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

try:
    import yaml
except ImportError:
    sys.exit("pyyaml not installed. Run: make lint-install")

ROOT = Path(__file__).resolve().parents[2]
BUILD_TASK = ROOT / "deploy" / "roles" / "02-artifact-build" / "tasks" / "build.yml"
GROUP_VARS = ROOT / "deploy" / "inventory" / "group_vars" / "all.yml"

REQUIRED_TOKENS = ("-trimpath", "-buildvcs=true")

errors: list[str] = []

# 1. group_vars/all.yml must declare ja4proxy_go_build_flags with both tokens.
gv = yaml.safe_load(GROUP_VARS.read_text()) or {}
flags_default = gv.get("ja4proxy_go_build_flags", "")
if not isinstance(flags_default, str):
    errors.append(
        f"{GROUP_VARS.relative_to(ROOT)}: ja4proxy_go_build_flags must be a string"
    )
else:
    for tok in REQUIRED_TOKENS:
        if tok not in flags_default:
            errors.append(
                f"{GROUP_VARS.relative_to(ROOT)}: "
                f"ja4proxy_go_build_flags missing `{tok}` "
                f"(got `{flags_default}`)"
            )

# 2. The build-from-source command must reference the flags var (or set
#    GOFLAGS literally containing both tokens). Parse YAML so folded
#    scalars don't trip us up.
docs = list(yaml.safe_load_all(BUILD_TASK.read_text()))
build_cmd: str | None = None


def walk(node) -> None:
    global build_cmd
    if isinstance(node, dict):
        if node.get("name", "").lower().startswith("build ja4proxy binary"):
            cmd_block = node.get("ansible.builtin.command") or node.get("command") or {}
            if isinstance(cmd_block, dict):
                build_cmd = cmd_block.get("cmd", "")
            elif isinstance(cmd_block, str):
                build_cmd = cmd_block
        for v in node.values():
            walk(v)
    elif isinstance(node, list):
        for item in node:
            walk(item)


for doc in docs:
    walk(doc)

if build_cmd is None:
    errors.append(f"{BUILD_TASK.relative_to(ROOT)}: build task not found by name")
else:
    normalised = " ".join(build_cmd.split())
    if "GOFLAGS" not in normalised:
        errors.append(
            f"{BUILD_TASK.relative_to(ROOT)}: build command does not set GOFLAGS "
            f"(expected `GOFLAGS='{{{{ ja4proxy_go_build_flags }}}}'` or literal flags)"
        )
    else:
        # Accept either templated reference or literal presence of both tokens.
        uses_var = "ja4proxy_go_build_flags" in normalised
        has_literal = all(tok in normalised for tok in REQUIRED_TOKENS)
        if not (uses_var or has_literal):
            missing = [t for t in REQUIRED_TOKENS if t not in normalised]
            errors.append(
                f"{BUILD_TASK.relative_to(ROOT)}: build command sets GOFLAGS but "
                f"neither references ja4proxy_go_build_flags nor carries "
                f"literal tokens {missing}"
            )

if errors:
    print(f"{len(errors)} Go build-flag issue(s):")
    for e in errors:
        print(f"  {e}")
    sys.exit(1)

print(
    f"✓ ja4proxy_go_build_flags='{flags_default}' "
    f"and role 02 build task sets GOFLAGS"
)
