#!/usr/bin/env python3
"""Validate 18-A SBOM emission.

Two halves:

  1. Drive `render_compose.py --sbom` into a temp file and assert the
     output is a well-formed CycloneDX 1.5 document with one component
     per service in the rendered compose template.

  2. Assert `deploy/roles/02-artifact-build/tasks/build.yml` wires
     cyclonedx-gomod for both the from-source and prebuilt paths, and
     gates the emission on tool presence so air-gapped build hosts
     don't hard-fail.
"""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RENDER = ROOT / "scripts" / "ci" / "render_compose.py"
BUILD_YML = ROOT / "deploy" / "roles" / "02-artifact-build" / "tasks" / "build.yml"

EXPECTED_IMAGES = {
    "haproxy",
    "redis",
    "caddy",
    "grafana/grafana",
    "grafana/loki",
    "grafana/promtail",
    "prom/prometheus",
    "prom/alertmanager",
    "prom/blackbox-exporter",
}


def check_compose_sbom() -> None:
    with tempfile.TemporaryDirectory() as td:
        out = Path(td) / "compose.cdx.json"
        r = subprocess.run(
            [sys.executable, str(RENDER), "--sbom", str(out)],
            capture_output=True, text=True, cwd=str(ROOT),
        )
        if r.returncode != 0:
            sys.exit(f"render_compose.py --sbom failed:\n{r.stdout}\n{r.stderr}")
        if not out.exists():
            sys.exit("render_compose.py did not write the SBOM file")

        try:
            sbom = json.loads(out.read_text())
        except json.JSONDecodeError as e:
            sys.exit(f"SBOM is not valid JSON: {e}")

    if sbom.get("bomFormat") != "CycloneDX":
        sys.exit(f"SBOM bomFormat is not CycloneDX: {sbom.get('bomFormat')!r}")
    if sbom.get("specVersion") != "1.5":
        sys.exit(f"SBOM specVersion is not 1.5: {sbom.get('specVersion')!r}")
    if not isinstance(sbom.get("serialNumber"), str) or not sbom["serialNumber"].startswith("urn:uuid:"):
        sys.exit("SBOM serialNumber missing or not urn:uuid:")
    if not isinstance(sbom.get("metadata"), dict):
        sys.exit("SBOM metadata block missing")
    if not isinstance(sbom["metadata"].get("timestamp"), str):
        sys.exit("SBOM metadata.timestamp missing")

    components = sbom.get("components")
    if not isinstance(components, list) or not components:
        sys.exit("SBOM components list is empty or missing")

    names = {c["name"] for c in components if "name" in c}
    missing = EXPECTED_IMAGES - names
    if missing:
        sys.exit(f"SBOM is missing expected images: {sorted(missing)}")

    for c in components:
        if c.get("type") != "container":
            sys.exit(f"component {c.get('name')!r} has type {c.get('type')!r}, expected 'container'")
        if "version" not in c or not c["version"]:
            sys.exit(f"component {c.get('name')!r} has no version")
        if not c.get("purl", "").startswith("pkg:docker/"):
            sys.exit(f"component {c.get('name')!r} has non-docker purl: {c.get('purl')!r}")
        if "bom-ref" not in c:
            sys.exit(f"component {c.get('name')!r} has no bom-ref")

    print(f"✓ compose SBOM: CycloneDX 1.5, {len(components)} components, expected images all present")


def check_build_yml_wiring() -> None:
    text = BUILD_YML.read_text()
    expected = [
        ("cyclonedx-gomod version",
         "control-machine probe for cyclonedx-gomod"),
        ("cyclonedx-gomod mod",
         "from-source SBOM generation (cyclonedx-gomod mod)"),
        ("cyclonedx-gomod bin",
         "prebuilt-binary SBOM generation (cyclonedx-gomod bin)"),
        ("ja4proxy.cdx.json",
         "SBOM output filename"),
        ("Copy binary SBOM to target",
         "task that ships SBOM to the deployed config dir"),
        ("failed_when: false",
         "soft-fail on probe so air-gapped builds don't break"),
    ]
    missing = [msg for needle, msg in expected if needle not in text]
    if missing:
        print("build.yml missing expected 18-A wiring:")
        for m in missing:
            print(f"  - {m}")
        sys.exit(1)

    # Probe must be a delegate_to: localhost task (SBOM tooling lives on
    # the build machine, not the target).
    probe_block = text.split("Probe for cyclonedx-gomod", 1)[-1].split("- name:", 1)[0]
    if "delegate_to: localhost" not in probe_block:
        sys.exit("cyclonedx-gomod probe is not delegate_to: localhost")

    print("✓ role 02 build.yml wires cyclonedx-gomod for both paths with soft-fail probe")


def main() -> int:
    check_compose_sbom()
    check_build_yml_wiring()
    return 0


if __name__ == "__main__":
    sys.exit(main())
