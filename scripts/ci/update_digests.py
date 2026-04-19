#!/usr/bin/env python3
"""18-G: refresh deploy/expected-image-digests.yml against Docker Hub.

For each image in `deploy/templates/docker-compose.yml.j2`, query
the Docker Hub Registry v2 API for the current sha256 digest of
that image's tag, and rewrite the pin file if anything changed.

Pure stdlib — no extra deps. Anonymous pulls only (all our images
are on Docker Hub: redis, haproxy, caddy, prom/*, grafana/*).

Usage:
    python3 scripts/ci/update_digests.py            # rewrite if dirty, exit 0
    python3 scripts/ci/update_digests.py --check    # exit 1 if dirty (don't write)
    python3 scripts/ci/update_digests.py --image redis  # one image only

Exit codes:
    0  — file is clean (or was rewritten in default mode)
    1  — --check and at least one digest differs (operator action needed)
    2  — registry/network failure (soft-fail; pin file is untouched)
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PIN_FILE = ROOT / "deploy" / "expected-image-digests.yml"
GROUP_VARS = ROOT / "deploy" / "inventory" / "group_vars" / "all.yml"

DOCKER_HUB_AUTH = "https://auth.docker.io/token"
DOCKER_HUB_REGISTRY = "https://registry-1.docker.io/v2"

MANIFEST_ACCEPTS = ", ".join([
    "application/vnd.docker.distribution.manifest.v2+json",
    "application/vnd.docker.distribution.manifest.list.v2+json",
    "application/vnd.oci.image.manifest.v1+json",
    "application/vnd.oci.image.index.v1+json",
])

# Same short-name → Docker Hub repo mapping role 09 already encodes,
# duplicated here so the two stay independently auditable. The CI
# check check_digest_regex.py asserts the two maps agree.
SHORT_TO_REPO = {
    "haproxy": "library/haproxy",
    "redis": "library/redis",
    "caddy": "library/caddy",
    "prometheus": "prom/prometheus",
    "grafana": "grafana/grafana",
    "loki": "grafana/loki",
    "promtail": "grafana/promtail",
    "blackbox_exporter": "prom/blackbox-exporter",
    "alertmanager": "prom/alertmanager",
}

# Match a pin line: `short: "name:tag@sha256:hex"`. Quotes optional
# but the file we ship always quotes them.
PIN_LINE_RE = re.compile(
    r'^(?P<short>[a-z_]+):\s*"(?P<image>[^"]+):(?P<tag>[^"@]+)@sha256:(?P<hex>[0-9a-f]{64})"\s*$',
    re.MULTILINE,
)


def _fetch_token(repo: str) -> str:
    """Anonymous pull-scope token from Docker Hub."""
    url = f"{DOCKER_HUB_AUTH}?service=registry.docker.io&scope=repository:{repo}:pull"
    with urllib.request.urlopen(url, timeout=15) as r:
        return json.loads(r.read())["token"]


def _fetch_digest(repo: str, tag: str) -> str:
    """Return sha256:<hex> for the given repo:tag on Docker Hub.

    HEAD-style request: read Docker-Content-Digest header. We use
    a regular GET because urllib's Request.method='HEAD' doesn't
    always survive Hub's redirects; the body is small.
    """
    token = _fetch_token(repo)
    url = f"{DOCKER_HUB_REGISTRY}/{repo}/manifests/{tag}"
    req = urllib.request.Request(url, headers={
        "Authorization": f"Bearer {token}",
        "Accept": MANIFEST_ACCEPTS,
    })
    with urllib.request.urlopen(req, timeout=15) as r:
        digest = r.headers.get("Docker-Content-Digest")
        if not digest or not digest.startswith("sha256:"):
            raise RuntimeError(
                f"Docker Hub did not return a sha256 digest header for "
                f"{repo}:{tag} (got {digest!r})"
            )
        return digest


def _read_pins() -> dict[str, dict]:
    """Parse the pin file into {short: {image, tag, hex, line}}."""
    text = PIN_FILE.read_text()
    pins = {}
    for m in PIN_LINE_RE.finditer(text):
        short = m.group("short")
        pins[short] = {
            "image": m.group("image"),
            "tag": m.group("tag"),
            "hex": m.group("hex"),
            "raw": m.group(0),
        }
    return pins


def _rewrite_pin(short: str, image: str, tag: str, new_digest: str) -> bool:
    """Replace the line for `short` in PIN_FILE. Return True if file changed."""
    text = PIN_FILE.read_text()
    new_line = f'{short}: "{image}:{tag}@{new_digest}"'
    pattern = rf'^{re.escape(short)}:\s*"[^"]+"\s*$'
    new_text, n = re.subn(pattern, new_line, text, flags=re.MULTILINE)
    if n != 1:
        raise RuntimeError(
            f"could not locate exactly one pin line for {short!r} in "
            f"{PIN_FILE} (found {n})"
        )
    if new_text != text:
        # Preserve final newline (yamllint requires it).
        if not new_text.endswith("\n"):
            new_text += "\n"
        PIN_FILE.write_text(new_text)
        return True
    return False


def _resolve_one(short: str) -> dict:
    """Look up the live digest for `short` and return a dict suitable
    for printing + rewriting. Raises on registry error."""
    pins = _read_pins()
    if short not in pins:
        sys.exit(f"unknown image short-name {short!r}; pin file has: {sorted(pins)}")
    pin = pins[short]
    repo = SHORT_TO_REPO.get(short)
    if repo is None:
        sys.exit(f"no Docker Hub repo mapping for short-name {short!r}")
    new_digest = _fetch_digest(repo, pin["tag"])
    return {
        "short": short,
        "repo": repo,
        "tag": pin["tag"],
        "image": pin["image"],
        "old_digest": f"sha256:{pin['hex']}",
        "new_digest": new_digest,
        "changed": new_digest != f"sha256:{pin['hex']}",
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--check",
        action="store_true",
        help="Exit 1 if any digest is stale; never rewrite the file.",
    )
    ap.add_argument(
        "--image",
        metavar="SHORT",
        help="Refresh only this short-name (debugging aid).",
    )
    args = ap.parse_args()

    pins = _read_pins()
    targets = [args.image] if args.image else sorted(pins)
    for short in targets:
        if short not in pins:
            sys.exit(f"unknown image short-name {short!r}")

    results: list[dict] = []
    try:
        for short in targets:
            results.append(_resolve_one(short))
    except (urllib.error.URLError, RuntimeError) as e:
        print(f"⚠ registry lookup failed: {e}", file=sys.stderr)
        print("pin file unchanged.", file=sys.stderr)
        return 2

    dirty = [r for r in results if r["changed"]]

    for r in results:
        marker = "↑" if r["changed"] else "·"
        print(f"  {marker} {r['short']:<18} {r['image']}:{r['tag']}")
        if r["changed"]:
            print(f"    was: {r['old_digest']}")
            print(f"    now: {r['new_digest']}")

    if not dirty:
        print(f"\n✓ all {len(results)} pin(s) already current")
        return 0

    if args.check:
        print(
            f"\n✗ {len(dirty)} pin(s) stale — run "
            "`make update-digests` to refresh and review the diff",
            file=sys.stderr,
        )
        return 1

    for r in dirty:
        _rewrite_pin(r["short"], r["image"], r["tag"], r["new_digest"])
    print(f"\n✓ rewrote {len(dirty)} pin(s) in {PIN_FILE.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
