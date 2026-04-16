#!/usr/bin/env python3
"""Render deploy/templates/docker-compose.yml.j2 with sample vars.

Verifies:
  - Jinja2 renders without error under realistic variable inputs.
  - The result is valid YAML (pyyaml parses it).
  - Every service has a top-level `image:` field, and each image matches
    one of our pinned short-names (so role 09 can actually pin them).
  - No {{ placeholder }} leaked through.

18-A: with `--sbom PATH`, also emit a CycloneDX 1.5 JSON SBOM listing
every rendered image as a component. The SBOM is "intent-level": images
carry tags, not digests (role 09 resolves digests at deploy time).
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

try:
    import yaml
    from jinja2 import Environment
except ImportError:
    sys.exit("pyyaml / jinja2 not installed. Run: make lint-install")

ROOT = Path(__file__).resolve().parents[2]
TEMPLATE = ROOT / "deploy" / "templates" / "docker-compose.yml.j2"
GROUP_VARS = ROOT / "deploy" / "inventory" / "group_vars" / "all.yml"


def render() -> dict:
    gv = yaml.safe_load(GROUP_VARS.read_text()) or {}
    ctx = {
        **gv,
        "redis_password": "sample-redis-password",
        "grafana_admin_password": "sample-grafana-password",
        "grafana_password": "sample-grafana-password",
        "redis_signing_key": "sample-signing-key",
        "haproxy_stats_password": "sample-stats-password",
        "haproxy_stats_user": "haproxy-admin",
        "ja4proxy_domain": "test-honeypot.example.com",
        "ja4proxy_admin_ip": "203.0.113.10",
    }
    env = Environment()
    tmpl = env.from_string(TEMPLATE.read_text())
    try:
        rendered = tmpl.render(**ctx)
    except Exception as e:
        sys.exit(f"jinja2 render failed: {e}")

    if "{{" in rendered or "}}" in rendered:
        stray = [ln for ln in rendered.splitlines() if "{{" in ln or "}}" in ln]
        sys.exit("stray template placeholders:\n  " + "\n  ".join(stray))

    try:
        doc = yaml.safe_load(rendered)
    except yaml.YAMLError as e:
        sys.exit(f"rendered compose is not valid YAML: {e}")

    if not isinstance(doc, dict) or "services" not in doc:
        sys.exit("rendered compose has no services: block")
    return doc


def validate(doc: dict) -> None:
    missing = [name for name, spec in doc["services"].items()
               if not isinstance(spec, dict) or "image" not in spec]
    if missing:
        sys.exit("services missing image: " + ", ".join(missing))

    role09 = (ROOT / "deploy" / "roles" / "09-image-digests" / "tasks" / "main.yml").read_text()
    map_block = re.search(
        r"digest_image_short:\s*\n((?:[ ]{6}[a-z_]+:[ ]+\S+\n)+)", role09
    )
    shorts = set()
    if map_block:
        shorts = set(re.findall(r"^\s+[a-z_]+:\s+(\S+)", map_block.group(1), re.MULTILINE))

    unknown = []
    for name, spec in doc["services"].items():
        img = spec["image"]
        short = img.split(":", 1)[0].split("@", 1)[0]
        if short not in shorts:
            unknown.append(f"{name} uses image '{img}' (short={short}) — not in role 09 map")

    if unknown:
        print("image short-names not covered by role 09 digest map:")
        for u in unknown:
            print(f"  {u}")
        sys.exit(1)

    service_names = set(doc["services"].keys())
    bad_deps = []
    for name, spec in doc["services"].items():
        deps = spec.get("depends_on", {})
        if isinstance(deps, list):
            dep_names = deps
        elif isinstance(deps, dict):
            dep_names = list(deps.keys())
        else:
            continue
        for dep in dep_names:
            if dep not in service_names:
                bad_deps.append(f"{name} depends_on '{dep}' — service does not exist")

    if bad_deps:
        print("depends_on targets missing from services:")
        for b in bad_deps:
            print(f"  {b}")
        sys.exit(1)


def build_sbom(doc: dict) -> dict:
    """Build a CycloneDX 1.5 SBOM from the rendered compose services.

    Images carry tag but not digest — role 09 resolves digests at
    deploy time. A target-side SBOM (future work) can re-emit with
    digests included.
    """
    components = []
    for service_name, spec in sorted(doc["services"].items()):
        img = spec["image"]
        # img is "name:tag" or "name@sha256:..." or "name:tag@sha256:..."
        name_part, _, digest_part = img.partition("@")
        name, _, tag = name_part.partition(":")
        tag = tag or "latest"

        purl_qualifiers = [f"tag={tag}"]
        hashes = []
        if digest_part.startswith("sha256:"):
            digest_hex = digest_part.split(":", 1)[1]
            purl_qualifiers.append(f"digest={digest_part}")
            hashes.append({"alg": "SHA-256", "content": digest_hex})

        # Docker Hub unqualified names (e.g. "haproxy") are namespaced
        # as library/haproxy in purl; namespaced names (e.g.
        # "grafana/loki") are left as-is with %2F-encoded slash handled
        # by the purl spec (we keep "/" for readability; purl parsers
        # accept both).
        purl_name = name if "/" in name else f"library/{name}"
        purl = f"pkg:docker/{purl_name}@{tag}"
        if purl_qualifiers:
            purl = f"pkg:docker/{purl_name}@{tag}?" + "&".join(
                q for q in purl_qualifiers if not q.startswith("tag=")
            )
        # Keep the tag= qualifier in purl even when digest absent, so
        # the SBOM is self-describing without re-reading compose:
        if "digest=" not in purl:
            purl = f"pkg:docker/{purl_name}@{tag}"

        component = {
            "type": "container",
            "bom-ref": f"service:{service_name}",
            "name": name,
            "version": tag,
            "purl": purl,
            "properties": [
                {"name": "compose:service", "value": service_name},
                {"name": "compose:image", "value": img},
            ],
        }
        if hashes:
            component["hashes"] = hashes
        components.append(component)

    return {
        "bomFormat": "CycloneDX",
        "specVersion": "1.5",
        "version": 1,
        "serialNumber": f"urn:uuid:{uuid.uuid4()}",
        "metadata": {
            "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "tools": [
                {"vendor": "JA4proxy-testing", "name": "render_compose.py"}
            ],
            "component": {
                "type": "application",
                "bom-ref": "compose-stack",
                "name": "ja4proxy-compose-stack",
                "description": (
                    "Docker Compose stack for the JA4proxy research honeypot "
                    "(intent-level SBOM; digests resolved at deploy time by role 09)."
                ),
            },
        },
        "components": components,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--sbom",
        metavar="PATH",
        help="Also emit a CycloneDX 1.5 JSON SBOM to PATH.",
    )
    args = ap.parse_args()

    doc = render()
    validate(doc)

    deps_count = sum(
        len(spec.get("depends_on", {}))
        for spec in doc["services"].values()
        if isinstance(spec, dict)
    )
    print(
        f"✓ compose renders, valid YAML, {len(doc['services'])} services, "
        f"all images pinnable, {deps_count} depends_on edges valid"
    )

    if args.sbom:
        sbom = build_sbom(doc)
        out = Path(args.sbom)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(sbom, indent=2) + "\n")
        print(f"✓ compose SBOM written: {out} ({len(sbom['components'])} components)")

    return 0


if __name__ == "__main__":
    sys.exit(main())
