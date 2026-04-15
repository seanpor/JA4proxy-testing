#!/usr/bin/env python3
"""Fail if plaintext secrets appear to be committed.

Scans tracked files for:
  - Vault files that escaped .gitignore (deploy/.vault/secrets.yml).
  - High-entropy-looking assignments of redis_password / grafana_password /
    haproxy_stats_password outside the generate-secrets.sh script and the
    include_vars loader.
  - Private-key headers.
"""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

tracked = subprocess.check_output(
    ["git", "ls-files"], cwd=ROOT, text=True
).splitlines()

errors: list[str] = []

# 1. Any tracked path under .vault/ or named secrets.yml is a fail.
for rel in tracked:
    if "/.vault/" in f"/{rel}" and not rel.endswith(".gitkeep"):
        errors.append(f"{rel}: vault path is tracked — should be gitignored")
    if rel.endswith("/secrets.yml") or rel == "secrets.yml":
        errors.append(f"{rel}: secrets.yml is tracked")

# 2. Private-key headers in any tracked file.
KEY_MARKERS = (
    b"-----BEGIN RSA PRIVATE KEY-----",
    b"-----BEGIN OPENSSH PRIVATE KEY-----",
    b"-----BEGIN EC PRIVATE KEY-----",
    b"-----BEGIN DSA PRIVATE KEY-----",
    b"-----BEGIN PRIVATE KEY-----",
)
for rel in tracked:
    p = ROOT / rel
    if not p.is_file() or p.stat().st_size > 1_000_000:
        continue
    try:
        data = p.read_bytes()
    except OSError:
        continue
    for m in KEY_MARKERS:
        if m in data:
            errors.append(f"{rel}: contains {m.decode()}")

# 3. Hard-coded looking password assignments outside expected files.
ALLOWED_FILES = {
    "deploy/scripts/generate-secrets.sh",
    "deploy/playbooks/site.yml",
    ".github/workflows/ci.yml",
    "scripts/ci/check_secrets.py",
}
PATTERN = re.compile(
    r"(redis_password|grafana_admin_password|grafana_password|"
    r"haproxy_stats_password|redis_signing_key)"
    r"\s*[:=]\s*['\"][^'\"{}$][^'\"\n]{7,}['\"]",
)
for rel in tracked:
    if rel in ALLOWED_FILES or rel.startswith("docs/"):
        continue
    p = ROOT / rel
    if not p.is_file() or p.suffix in (".png", ".jpg", ".pdf"):
        continue
    try:
        text = p.read_text(errors="ignore")
    except OSError:
        continue
    for m in PATTERN.finditer(text):
        line_no = text[: m.start()].count("\n") + 1
        errors.append(f"{rel}:{line_no}: looks like a hard-coded secret ({m.group(1)})")

if errors:
    print(f"{len(errors)} secret-scan finding(s):")
    for e in errors:
        print(f"  {e}")
    sys.exit(1)

print("✓ no plaintext secrets found in tracked files")
