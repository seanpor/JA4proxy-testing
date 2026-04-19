# 1. No build tools on the server

## Status

Accepted

## Context

The target VM is a research honeypot that must be reachable from the
open internet on ports 80 and 443. Any compiler, language toolchain,
or package-build daemon installed on the VM is both a live attack
surface and a live foothold once an attacker lands on the box: Go,
gcc, npm, pip, and similar can be repurposed to compile second-stage
payloads in-place, bypassing egress filters on binary downloads. A
hardened research host should contain only the runtime dependencies it
strictly needs to *serve* traffic.

## Decision

No build tooling is installed on the target VM. Every artifact that
runs on the VM — the JA4proxy binary, the supporting container images,
the honeypot HTML — is produced on a separate build machine and
transferred as a finished deployable unit.

This is encoded in `deploy/roles/01-vm-provisioning` (which installs
only runtime packages) and `deploy/roles/02-artifact-build` (which
runs on the control host, not the target, via `delegate_to:
localhost`). The playbook accepts either
`ja4proxy_build_machine_go_path` (sibling Go checkout on the control
host) or `ja4proxy_prebuilt_binary_path` (already-built static binary)
but never compiles on the target.

## Consequences

- **Positive:** Attack surface on the VM is restricted to runtime
  binaries. A compromised VM cannot silently build secondary tools.
  The host package set stays small enough to audit by eye.
- **Positive:** Reproducibility improves — the build machine is a
  controlled environment (`-trimpath`, `-buildvcs=true` via
  `ja4proxy_go_build_flags`), and the VM never sees the source tree.
- **Negative:** Emergency patches require a round-trip through the
  build machine; there is no `go install` shortcut on the VM.
- **Follow-on:** Phase 18-A (SBOM), 18-C (govulncheck), and 18-D
  (cosign sign/verify) all lean on this split — scanning and signing
  happen on the build side, verification happens before the binary
  starts on the target.
