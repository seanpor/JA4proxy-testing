#!/usr/bin/env python3
"""Phase 21-A pilot: turn `.trivyignore` prose into mechanical assertions.

Each CRITICAL entry in `.trivyignore` carries a written reachability
argument — e.g. "this deployment only configures Prometheus + Loki
data sources, not Postgres" — that explains why the CVE is not
exploitable in our configuration. Today those arguments are asserted,
not tested. Phase 21-A converts them, one CVE at a time, from human
prose into static checks against the configuration that backs them.

Failure mode this guards
------------------------
Configuration drift silently invalidates an allowlisted CVE's
reachability argument. Example: someone adds a Postgres data source
to Grafana six months from now. The `.trivyignore` entry for
CVE-2026-33816 (jackc/pgx Postgres-driver memory-safety flaw) still
sits there, prose still says "not Postgres", expiry still in the
future — but the CVE is now reachable. Without this check, that drift
goes unnoticed until the next manual review (or, more likely,
until the CVE expires and someone re-justifies based on stale text).

Static, not live
----------------
The Phase 21-A scope language ("attempts the exploit path from an
external position") was aspirational. A live-probe implementation
needs the deployed VM, network access from CI, and per-CVE exploit
machinery — heavy, flaky, and VM-coupled. The static probes here
test the *configuration that enables reachability*: if the
configuration permits the precondition, the prose claim is dead;
if it forbids it, the claim survives another day. Cheaper, runs
offline, lives in `make test`. Live probing remains a separate
effort if/when it becomes load-bearing.

Pilot scope
-----------
One probe: CVE-2026-33816 (Grafana Postgres datasource). The probe
function structure is deliberately extensible — additional CVEs
land as small follow-up PRs, each adding one function.
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
TRIVYIGNORE = ROOT / ".trivyignore"


def _trivyignore_has(cve: str) -> bool:
    """True iff `cve` is currently allowlisted (uncommented line)."""
    if not TRIVYIGNORE.exists():
        return False
    for raw in TRIVYIGNORE.read_text().splitlines():
        line = raw.strip()
        if line == cve:
            return True
    return False


def probe_cve_2026_33816() -> str | None:
    """CVE-2026-33816 — Grafana jackc/pgx Postgres-driver memory-safety
    flaw. Allowlist prose: "exploit requires Grafana to connect to an
    attacker-controlled Postgres server; this deployment only configures
    Prometheus + Loki data sources … not Postgres".

    Reachability assertion: walk the Grafana datasources provisioning
    template and confirm no datasource declares `type: postgres`. The
    expected set is `{prometheus, loki}`; any other type is flagged so
    a future addition (mysql, mssql, *anything*) forces a deliberate
    decision rather than silently widening the attack surface."""
    cve = "CVE-2026-33816"
    if not _trivyignore_has(cve):
        return None  # not allowlisted → no claim to defend

    template = ROOT / "deploy" / "templates" / "grafana-datasources.yml.j2"
    if not template.exists():
        return f"{cve}: {template.relative_to(ROOT)} missing — cannot verify claim"

    try:
        doc = yaml.safe_load(template.read_text())
    except yaml.YAMLError as exc:
        return f"{cve}: {template.relative_to(ROOT)} not valid YAML: {exc}"

    if not isinstance(doc, dict):
        return f"{cve}: {template.relative_to(ROOT)} did not parse as a mapping"

    sources = doc.get("datasources") or []
    types = [str((s or {}).get("type", "")).lower() for s in sources]

    expected = {"prometheus", "loki"}
    unexpected = sorted(set(types) - expected - {""})
    if unexpected:
        return (
            f"{cve}: grafana-datasources.yml.j2 declares datasource "
            f"type(s) {unexpected} outside the {sorted(expected)} "
            "allowlist — the 'no Postgres datasource' reachability "
            "argument no longer holds. Either remove the new "
            "datasource, drop the CVE from .trivyignore, or "
            "extend this probe to re-justify."
        )

    if "postgres" in types:
        return (
            f"{cve}: grafana-datasources.yml.j2 contains a postgres "
            "datasource — the allowlist's reachability argument is "
            "false. Remove the datasource or drop the CVE."
        )

    return None


def probe_cve_2026_31789() -> str | None:
    """CVE-2026-31789 — Grafana OpenSSL libcrypto3/libssl3 heap buffer
    overflow on 32-bit systems. Allowlist prose: "Our Grafana deploys
    to amd64 only (Alibaba ECS instance family); the 32-bit code path
    is not reachable".

    Reachability assertion: walk `docker-compose.yml.j2` and confirm no
    service pins a 32-bit Docker platform. Default Docker behaviour
    matches the host architecture, and every Alibaba ECS family this
    deployment targets (the provisioning script's default and the
    families the README mentions) is 64-bit. Pinning `linux/386`,
    `linux/arm/v6` or `linux/arm/v7` on any service would override
    that and pull a 32-bit Grafana — re-enabling the OpenSSL 32-bit
    code path. We allowlist *no* `platform:` directive at all rather
    than blocklist 32-bit values, so any future pin (even a 64-bit
    one) forces a deliberate decision rather than silently widening
    the surface."""
    cve = "CVE-2026-31789"
    if not _trivyignore_has(cve):
        return None

    compose = ROOT / "deploy" / "templates" / "docker-compose.yml.j2"
    if not compose.exists():
        return f"{cve}: {compose.relative_to(ROOT)} missing — cannot verify claim"

    # We don't try to YAML-parse the template (it has Jinja directives
    # the loader would choke on). A regex over `platform:` lines is
    # sufficient: the compose grammar only uses that key at the
    # service level, so any match means a service-level platform
    # override.
    platform_lines = []
    for lineno, raw in enumerate(compose.read_text().splitlines(), start=1):
        stripped = raw.strip()
        if stripped.startswith("#") or not stripped:
            continue
        # `platform:` at any indent — service-level only key in compose.
        if re.match(r"platform\s*:", stripped):
            platform_lines.append((lineno, stripped))

    if platform_lines:
        joined = "; ".join(f"line {ln}: `{txt}`" for ln, txt in platform_lines)
        return (
            f"{cve}: docker-compose.yml.j2 declares platform override(s) "
            f"({joined}). The 'amd64 only / 32-bit code path unreachable' "
            "reachability argument depends on Docker pulling host-arch "
            "images by default. Remove the platform pin, drop the CVE, "
            "or extend this probe to allowlist a known-64-bit value."
        )

    return None


PROBES = [probe_cve_2026_33816, probe_cve_2026_31789]


def main() -> int:
    errors: list[str] = []
    checked: list[str] = []
    for probe in PROBES:
        result = probe()
        cve = probe.__doc__.split("—", 1)[0].strip().split()[-1]
        checked.append(cve)
        if result is not None:
            errors.append(result)

    if errors:
        print(f"{len(errors)} CVE reachability claim(s) violated:")
        for e in errors:
            print(f"  ✗ {e}")
        return 1

    if not checked:
        print("✓ no CVE reachability probes registered")
    else:
        print(
            f"✓ {len(checked)} CVE reachability claim(s) still hold: "
            + ", ".join(checked)
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
