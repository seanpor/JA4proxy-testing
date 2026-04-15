#!/usr/bin/env python3
"""Self-test for the digest-pinning replacement in role 09.

Reconstructs the same regex the role builds via Jinja2's regex_escape
and applies it to a fake pre-pin compose snippet. Asserts:
  - every service line is rewritten from tag form to digest form,
  - the task is idempotent (second application is a no-op),
  - the post-rewrite grep finds zero un-pinned lines.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ROLE09 = ROOT / "deploy" / "roles" / "09-image-digests" / "tasks" / "main.yml"

block = re.search(
    r"digest_image_short:\s*\n((?:[ ]{6}[a-z_]+:[ ]+\S+\n)+)",
    ROLE09.read_text(),
)
if not block:
    sys.exit("could not find digest_image_short map in role 09")

mapping = dict(
    re.findall(r"^\s+([a-z_]+):\s+(\S+)", block.group(1), re.MULTILINE)
)

# A realistic pre-pin compose snippet (indent + image form).
sample = "\n".join(f"    image: {short}:some-tag" for short in mapping.values()) + "\n"
digests = {k: f"{v}@sha256:{'a' * 64}" for k, v in mapping.items()}

out = sample
for key, short in mapping.items():
    pattern = r"^(\s*image:\s+)" + re.escape(short) + r"[:@][^\s]+\s*$"
    out = re.sub(pattern, r"\1" + digests[key], out, flags=re.MULTILINE)

unpinned = [
    ln for ln in out.splitlines()
    if re.match(r"^\s*image:\s+", ln)
    and not re.search(r"@sha256:[0-9a-f]{64}", ln)
]
if unpinned:
    sys.exit("regex failed to pin:\n  " + "\n  ".join(unpinned))

# Idempotency: run again, expect identical output.
out2 = out
for key, short in mapping.items():
    pattern = r"^(\s*image:\s+)" + re.escape(short) + r"[:@][^\s]+\s*$"
    out2 = re.sub(pattern, r"\1" + digests[key], out2, flags=re.MULTILINE)
if out != out2:
    sys.exit("regex not idempotent — second run changed the file")

print(f"✓ digest regex pins all {len(mapping)} images and is idempotent")
