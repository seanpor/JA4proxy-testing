#!/usr/bin/env python3
"""Self-test for the digest-pinning replacement in role 09 AND
the 18-G expected-image-digests.yml pin file.

Two halves:

  1. Reconstruct the same regex role 09 builds via Jinja2's
     regex_escape and apply it to a fake pre-pin compose snippet.
     Assert every service line is rewritten from tag form to digest
     form, the task is idempotent, and no un-pinned lines remain.

  2. (18-G extension) Parse deploy/expected-image-digests.yml and
     assert: every line matches `<short>: "<image>:<tag>@sha256:<64hex>"`,
     short-names match role 09's digest_image_short map exactly,
     no duplicate keys, and update_digests.py's SHORT_TO_REPO map
     agrees on the same set of short-names.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ROLE09 = ROOT / "deploy" / "roles" / "09-image-digests" / "tasks" / "main.yml"
PIN_FILE = ROOT / "deploy" / "expected-image-digests.yml"
UPDATE_SCRIPT = ROOT / "scripts" / "ci" / "update_digests.py"


def check_role09_regex() -> dict[str, str]:
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
    return mapping


def check_pin_file(role09_mapping: dict[str, str]) -> None:
    if not PIN_FILE.exists():
        sys.exit(f"{PIN_FILE.relative_to(ROOT)} missing — needed by 18-G")

    pin_line_re = re.compile(
        r'^(?P<short>[a-z_]+):\s*"(?P<image>[^"]+):(?P<tag>[^"@]+)'
        r'@sha256:(?P<hex>[0-9a-f]{64}|0{64})"\s*$'
    )

    pins: dict[str, str] = {}
    for lineno, raw in enumerate(PIN_FILE.read_text().splitlines(), start=1):
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        m = pin_line_re.match(raw)
        if not m:
            sys.exit(
                f"{PIN_FILE.name}:{lineno}: line does not match "
                f'`<short>: "<image>:<tag>@sha256:<64hex|sentinel>"`:\n  {raw!r}'
            )
        short = m.group("short")
        if short in pins:
            sys.exit(f"{PIN_FILE.name}:{lineno}: duplicate short-name {short!r}")
        pins[short] = m.group("image")

    pin_shorts = set(pins)
    role09_shorts = set(role09_mapping)
    if pin_shorts != role09_shorts:
        only_pin = pin_shorts - role09_shorts
        only_role = role09_shorts - pin_shorts
        msg = ["pin file short-names disagree with role 09 digest_image_short:"]
        if only_pin:
            msg.append(f"  - in pin file but not role 09: {sorted(only_pin)}")
        if only_role:
            msg.append(f"  - in role 09 but not pin file: {sorted(only_role)}")
        sys.exit("\n".join(msg))

    # Pin entry's `<image>` must equal role 09's mapped short-name
    # (so the same Docker Hub repo is referenced from both sides).
    for short, image in pins.items():
        if image != role09_mapping[short]:
            sys.exit(
                f"{PIN_FILE.name}: pin for {short!r} uses image {image!r} "
                f"but role 09 maps it to {role09_mapping[short]!r}"
            )

    print(f"✓ {PIN_FILE.name} parses, {len(pins)} pin(s) match role 09 short-names")


def check_update_script_map(role09_mapping: dict[str, str]) -> None:
    """update_digests.py's SHORT_TO_REPO must list the same short-names
    as role 09 — otherwise the weekly refresh would drift silently."""
    text = UPDATE_SCRIPT.read_text()
    block = re.search(
        r"SHORT_TO_REPO\s*=\s*\{\s*\n((?:\s*\"[a-z_]+\":\s*\"[^\"]+\",\s*\n)+)\s*\}",
        text,
    )
    if not block:
        sys.exit(f"could not locate SHORT_TO_REPO map in {UPDATE_SCRIPT.name}")
    script_shorts = set(re.findall(r'"([a-z_]+)":\s*"', block.group(1)))
    role09_shorts = set(role09_mapping)
    if script_shorts != role09_shorts:
        only_script = script_shorts - role09_shorts
        only_role = role09_shorts - script_shorts
        msg = [
            f"{UPDATE_SCRIPT.name} SHORT_TO_REPO disagrees with role 09 "
            "digest_image_short:"
        ]
        if only_script:
            msg.append(f"  - in script but not role 09: {sorted(only_script)}")
        if only_role:
            msg.append(f"  - in role 09 but not script: {sorted(only_role)}")
        sys.exit("\n".join(msg))
    print(f"✓ update_digests.py SHORT_TO_REPO covers all {len(script_shorts)} role-09 images")


def main() -> int:
    role09_mapping = check_role09_regex()
    check_pin_file(role09_mapping)
    check_update_script_map(role09_mapping)
    return 0


if __name__ == "__main__":
    sys.exit(main())
