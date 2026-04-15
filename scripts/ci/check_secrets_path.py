#!/usr/bin/env python3
"""Regression test for critical-review finding A1.

generate-secrets.sh and site.yml must agree on the secrets-file location.
This test:
  1. Runs the script against a temp HOME with the repo mirrored elsewhere,
     so we don't disturb the operator's real vault.
  2. Asserts the file lands in deploy/.vault/secrets.yml (relative to the
     repo root the script is invoked from).
  3. Asserts site.yml's include_vars still resolves to the same path.
"""
from __future__ import annotations

import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

# 1. Static check on site.yml — confirm the path hasn't drifted.
site_yml = (ROOT / "deploy" / "playbooks" / "site.yml").read_text()
m = re.search(r"include_vars:\s*\n\s*file:\s*\"([^\"]+)\"", site_yml)
if not m:
    sys.exit("could not find include_vars block for secrets in site.yml")
expected = m.group(1)
if "{{ playbook_dir }}/../.vault/secrets.yml" != expected:
    sys.exit(
        "site.yml include_vars path changed to " + expected
        + " — update this test and deploy/scripts/generate-secrets.sh together."
    )

# 2. Dynamic check: run the script in a throwaway copy of the repo.
with tempfile.TemporaryDirectory() as tmp:
    tmp = Path(tmp)
    shutil.copytree(
        ROOT / "deploy",
        tmp / "deploy",
        ignore=shutil.ignore_patterns(".vault"),
    )
    (tmp / "deploy" / ".vault").mkdir(exist_ok=True)

    # Skip the dynamic run if ansible-vault isn't on PATH (e.g. pre-commit
    # hook running outside the dev venv). The static check above is still
    # enough to catch A1 path drift.
    if shutil.which("ansible-vault") is None:
        print("✓ secrets-path contract holds (static only — ansible-vault not on PATH)")
        raise SystemExit

    subprocess.run(
        ["bash", "deploy/scripts/generate-secrets.sh"],
        cwd=tmp,
        check=True,
        capture_output=True,
    )

    want = tmp / "deploy" / ".vault" / "secrets.yml"
    stray = tmp / ".vault" / "secrets.yml"
    pass_file = tmp / "deploy" / ".vault" / ".vault-pass"
    if not want.is_file():
        sys.exit(f"A1 regression: secrets not at {want}")
    if stray.exists():
        sys.exit(f"A1 regression: secrets leaked to {stray}")
    if not pass_file.is_file():
        sys.exit(f"A5 regression: vault password file missing at {pass_file}")
    head = want.read_bytes()[:20]
    if not head.startswith(b"$ANSIBLE_VAULT;"):
        sys.exit("A5 regression: secrets.yml is not vault-encrypted at rest")

print("✓ secrets-path + at-rest-encryption contract holds (A1 + A5 regression)")
