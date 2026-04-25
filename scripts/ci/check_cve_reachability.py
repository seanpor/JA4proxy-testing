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

Coverage invariant (21-G)
-------------------------
Once probes exist for the four CRITICAL `.trivyignore` entries
(landed across PRs #72-#75), the registry adds a *coverage* gate:
every CRITICAL entry must be defended by some probe. Adding a new
CRITICAL CVE to `.trivyignore` without registering a probe fails
`make test` with the missing CVE ID — turning probe coverage from
convention into mechanical invariant.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

# 21-H: severity classifier lives in a sibling module so check_image_scan.py
# can apply the same source of truth for its expiry-ceiling gate.
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _trivyignore import classify as _classify_trivyignore

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


def _critical_cves_in_trivyignore() -> set[str]:
    """CVE IDs in `.trivyignore` whose severity is CRITICAL. Thin
    wrapper around the shared `_trivyignore.classify()` parser so
    both this gate and check_image_scan.py's 21-H expiry-ceiling gate
    use the same source of truth on borderline severity calls."""
    if not TRIVYIGNORE.exists():
        return set()
    return {
        cve
        for cve, sev in _classify_trivyignore(TRIVYIGNORE.read_text()).items()
        if sev == "CRITICAL"
    }


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


def probe_cve_2025_68121() -> str | None:
    """CVE-2025-68121 — Go 1.25.5 crypto/tls cert-validation flaw in
    `prom/blackbox-exporter:latest`. Allowlist prose: "Blackbox probes
    known targets over HTTPS from the monitoring network; exploit
    requires MITM position on the probe path".

    Reachability assertion (two halves):
      1. `blackbox.yml.j2` declares only the `https_2xx` probe module —
         no `tcp` / `icmp` / `dns` / additional `http` modules that
         could be aimed at attacker-controlled hosts. Allowlist-strict.
      2. The blackbox scrape job in `prometheus.yml.j2` uses
         `static_configs` only — no `file_sd_configs`, `http_sd_configs`,
         `dns_sd_configs`, `consul_sd_configs`, `kubernetes_sd_configs`
         etc. Dynamic discovery would let an attacker who can write to
         the discovery source (file, HTTP endpoint, DNS) feed the
         exporter an attacker-controlled URL — turning "MITM required"
         into "any control of the discovery source"."""
    cve = "CVE-2025-68121"
    if not _trivyignore_has(cve):
        return None

    blackbox = ROOT / "deploy" / "templates" / "blackbox.yml.j2"
    prometheus = ROOT / "deploy" / "templates" / "prometheus.yml.j2"

    if not blackbox.exists():
        return f"{cve}: {blackbox.relative_to(ROOT)} missing — cannot verify claim"
    if not prometheus.exists():
        return f"{cve}: {prometheus.relative_to(ROOT)} missing — cannot verify claim"

    # Blackbox modules: parse and walk.
    try:
        bdoc = yaml.safe_load(blackbox.read_text())
    except yaml.YAMLError as exc:
        return f"{cve}: {blackbox.relative_to(ROOT)} not valid YAML: {exc}"
    if not isinstance(bdoc, dict):
        return f"{cve}: {blackbox.relative_to(ROOT)} did not parse as a mapping"
    modules = list((bdoc.get("modules") or {}).keys())
    expected = {"https_2xx"}
    extra = sorted(set(modules) - expected)
    if extra:
        return (
            f"{cve}: blackbox.yml.j2 declares probe module(s) {extra} "
            f"outside the {sorted(expected)} allowlist — broadening "
            "the surface beyond 'known HTTPS targets'. Either remove "
            "the new module(s), drop the CVE, or extend this probe."
        )

    # Prometheus blackbox scrape job: regex on the rendered template.
    # Jinja directives prevent a clean YAML parse; a regex over the
    # raw text is sufficient because we're checking the *absence* of
    # service-discovery keys, not the structure of any present.
    text = prometheus.read_text()
    blackbox_block = re.search(
        r"(- job_name:\s*['\"]?blackbox[-_a-z]*['\"]?[\s\S]*?)(?=\n\s*- job_name:|\Z)",
        text,
    )
    if not blackbox_block:
        return (
            f"{cve}: prometheus.yml.j2 has no `blackbox*` job_name — "
            "the reachability claim depends on a known scrape config; "
            "if the job is gone the claim should be re-justified."
        )
    block_text = blackbox_block.group(1)
    forbidden_sd = (
        "file_sd_configs", "http_sd_configs", "dns_sd_configs",
        "consul_sd_configs", "kubernetes_sd_configs", "ec2_sd_configs",
        "gce_sd_configs", "azure_sd_configs",
    )
    found_sd = [k for k in forbidden_sd if k in block_text]
    if found_sd:
        return (
            f"{cve}: prometheus.yml.j2 blackbox job uses "
            f"{found_sd} — dynamic service discovery breaks the "
            "'known targets' premise of the MITM-only argument. "
            "Pin targets in static_configs, drop the CVE, or extend "
            "this probe to bound the discovery source."
        )
    if "static_configs" not in block_text:
        return (
            f"{cve}: prometheus.yml.j2 blackbox job has no "
            "static_configs — cannot verify targets are pinned."
        )

    return None


def _caddyfile_directives() -> set[str]:
    """Tokenise the Caddyfile to a flat set of first-token-on-line
    directive names, comment-stripped. Caddyfile syntax has `#` as
    line comment; multi-line strings and braces complicate a full
    parse, but for the *presence* checks the Caddy-CVE probes need —
    "does the directive `reverse_proxy` appear as code?" — first-token
    extraction with comment stripping is sufficient and avoids
    importing a Caddyfile parser."""
    caddyfile = ROOT / "deploy" / "templates" / "caddyfile.j2"
    if not caddyfile.exists():
        return set()
    directives: set[str] = set()
    for raw in caddyfile.read_text().splitlines():
        # Strip `#` comment (Caddyfile uses `#` to EOL).
        code = raw.split("#", 1)[0]
        # First non-whitespace token, sans braces.
        token = code.strip().lstrip("{").lstrip("@").strip().split()
        if token:
            first = token[0].rstrip("{").rstrip(",")
            if first and not first.startswith("{{"):  # skip Jinja
                directives.add(first)
    return directives


def probe_cve_caddy_not_on_public_path() -> str | None:
    """CVE-2026-30836 + CVE-2026-33186 — smallstep/certificates and
    grpc-go inside `caddy:2-alpine`. Allowlist prose: "Caddy's cert
    handling and gRPC surface are not on our public path (HAProxy
    terminates TLS as passthrough; Caddy only serves the static
    honeypot after JA4proxy). Fixes require upstream caddy image
    refresh."

    Reachability assertion: walk the rendered Caddyfile directives
    and confirm none of the dangerous directives that would
    re-enable the vulnerable code paths appear:

      - `pki` (global) / `acme_server` — would turn Caddy into a CA,
        reaching the smallstep/certificates code path that
        CVE-2026-30836 exploits.
      - `reverse_proxy` / `transport` — would make Caddy a gateway
        rather than a static file server; combined with `transport
        http { versions h2c }` it reaches the grpc-go code path that
        CVE-2026-33186 exploits.
      - `grpc` — explicit gRPC support.

    The probe covers both CVEs because they share a single prose
    claim and a single image source. Reports both CVE IDs on
    failure so the operator sees the full scope of the breakage.
    """
    cves = ("CVE-2026-30836", "CVE-2026-33186")
    if not any(_trivyignore_has(c) for c in cves):
        return None

    caddyfile = ROOT / "deploy" / "templates" / "caddyfile.j2"
    if not caddyfile.exists():
        return (
            f"{'/'.join(cves)}: {caddyfile.relative_to(ROOT)} missing — "
            "cannot verify caddy's static-content-only configuration."
        )

    directives = _caddyfile_directives()
    forbidden = {
        "pki": "would turn Caddy into a CA (smallstep/certificates path)",
        "acme_server": "Caddy as ACME server reaches the same CA code path",
        "reverse_proxy": "Caddy as gateway reaches grpc-go via transport h2c",
        "transport": "explicit transport block enables gRPC code path",
        "grpc": "explicit gRPC reverse proxy",
    }
    hits = sorted(set(directives) & set(forbidden))
    if hits:
        details = "; ".join(f"{d!r} ({forbidden[d]})" for d in hits)
        return (
            f"{'/'.join(cves)}: caddyfile.j2 declares forbidden "
            f"directive(s) — {details}. Caddy is now on the public "
            "path for the affected code paths; remove the directive, "
            "drop the CVE(s), or extend this probe to re-justify."
        )

    return None


PROBES = [
    probe_cve_2026_33816,
    probe_cve_2026_31789,
    probe_cve_2025_68121,
    probe_cve_caddy_not_on_public_path,
]


CVE_ID_RE = re.compile(r"CVE-\d{4}-\d+")


def _registry_coverage() -> set[str]:
    """Set of CVE IDs that the probe registry claims to cover. Source
    of truth is each probe's docstring lead-in (text before the first
    em-dash) — same place `main()` reads for reporting."""
    covered: set[str] = set()
    for probe in PROBES:
        lead = (probe.__doc__ or "").split("—", 1)[0]
        covered.update(CVE_ID_RE.findall(lead))
    return covered


def main() -> int:
    errors: list[str] = []
    checked: list[str] = []

    # 21-G coverage invariant: every CRITICAL `.trivyignore` entry must
    # be defended by some probe. Run *before* the probes so a missing
    # probe surfaces even when every existing probe is green.
    critical = _critical_cves_in_trivyignore()
    covered = _registry_coverage()
    uncovered = sorted(critical - covered)
    if uncovered:
        for cve in uncovered:
            errors.append(
                f"{cve}: CRITICAL .trivyignore entry has no reachability "
                "probe in this registry. Add a probe function (one per "
                "CVE or one per shared prose claim) that mechanically "
                "verifies the allowlist's reachability argument, OR drop "
                "the CVE if it should not have been allowlisted."
            )

    for probe in PROBES:
        result = probe()
        # Extract CVE IDs from the docstring lead-in (everything before
        # the first em-dash). A probe may guard one CVE or several
        # (caddy: two CVEs share one prose claim and one config).
        lead = (probe.__doc__ or "").split("—", 1)[0]
        cves = CVE_ID_RE.findall(lead) or ["?"]
        checked.extend(cves)
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
            f"✓ {len(checked)} CVE reachability claim(s) still hold "
            f"(covers all {len(critical)} CRITICAL .trivyignore entries): "
            + ", ".join(checked)
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
