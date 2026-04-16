#!/usr/bin/env python3
"""12-B: Anonymise a JA4proxy export directory.

Runs on the control machine (not the VM). Takes an export directory
and a per-run salt, produces an anonymised copy where:

  - IPv4 addresses → HMAC-SHA-256(salt, ip), truncated to 16 hex chars
  - IPv6 addresses → HMAC-SHA-256(salt, /64 prefix), truncated to 16 hex
  - PII patterns (email, phone) → [REDACTED] (line preserved for context)

Usage:
    python3 anonymise.py <export-dir> <output-dir> --salt <salt>
"""
from __future__ import annotations

import argparse
import hashlib
import hmac
import re
import shutil
import sys
from pathlib import Path

# IPv4: dotted-quad
IPV4_RE = re.compile(r"\b(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})\b")

# IPv6: require at least 3 colon-separated groups AND either a `::`
# or 5+ groups to avoid false-positives on JA4 fingerprint hashes
# (e.g. "8daaf6152771" looks like hex but isn't an IPv6 address).
IPV6_RE = re.compile(
    r"\b("
    # Full form: 6+ colon-separated groups
    r"[0-9a-fA-F]{1,4}(?::[0-9a-fA-F]{1,4}){5,7}"
    r"|"
    # Compressed form with :: (must have at least one group on each side or at boundary)
    r"[0-9a-fA-F]{0,4}(?::[0-9a-fA-F]{0,4})*::[0-9a-fA-F]{0,4}(?::[0-9a-fA-F]{0,4})*"
    r")\b"
)

# PII patterns: email addresses, phone numbers
PII_RE = re.compile(
    r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}"  # email
    r"|\+?\d[\d\s\-()]{7,}\d",  # phone
    re.IGNORECASE,
)

# Binary file extensions to copy without scrubbing
BINARY_EXTS = {".gz", ".tar", ".zst", ".snap", ".db", ".wal"}


def hmac_hash(salt: bytes, value: str) -> str:
    """HMAC-SHA-256, truncated to 16 hex chars."""
    return hmac.new(salt, value.encode(), hashlib.sha256).hexdigest()[:16]


def anonymise_ipv4(salt: bytes, ip: str) -> str:
    """Replace an IPv4 address with its HMAC."""
    return hmac_hash(salt, ip)


def anonymise_ipv6(salt: bytes, addr: str) -> str:
    """Replace an IPv6 address with the HMAC of its /64 prefix."""
    parts = addr.split(":")
    prefix = ":".join(parts[:4]) if len(parts) >= 4 else addr
    return hmac_hash(salt, prefix)


def anonymise_line(salt: bytes, line: str) -> str:
    """Anonymise a single line. PII is replaced with [REDACTED],
    IPs are replaced with their HMAC."""
    line = PII_RE.sub("[REDACTED]", line)
    line = IPV4_RE.sub(lambda m: anonymise_ipv4(salt, m.group(1)), line)
    line = IPV6_RE.sub(lambda m: anonymise_ipv6(salt, m.group(1)), line)
    return line


def anonymise_file(salt: bytes, src: Path, dst: Path) -> None:
    """Anonymise a single file."""
    if src.suffix in BINARY_EXTS:
        shutil.copy2(src, dst)
        return

    try:
        text = src.read_text(errors="replace")
    except UnicodeDecodeError:
        shutil.copy2(src, dst)
        return

    out_lines = []
    for line in text.splitlines(keepends=True):
        out_lines.append(anonymise_line(salt, line))
    dst.write_text("".join(out_lines))


def main() -> int:
    parser = argparse.ArgumentParser(description="Anonymise a JA4proxy export")
    parser.add_argument("export_dir", type=Path, help="Input export directory")
    parser.add_argument("output_dir", type=Path, help="Output anonymised directory")
    parser.add_argument("--salt", required=True, help="Per-run HMAC salt")
    args = parser.parse_args()

    if not args.export_dir.is_dir():
        print(f"ERROR: {args.export_dir} is not a directory", file=sys.stderr)
        return 1

    if args.output_dir.exists():
        print(f"ERROR: {args.output_dir} already exists", file=sys.stderr)
        return 1

    salt = args.salt.encode()
    args.output_dir.mkdir(parents=True)

    for src in sorted(args.export_dir.rglob("*")):
        if not src.is_file():
            continue
        rel = src.relative_to(args.export_dir)
        dst = args.output_dir / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        anonymise_file(salt, src, dst)
        print(f"  {rel}")

    print(f"\nAnonymised export: {args.output_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
