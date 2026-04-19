#!/usr/bin/env python3
"""Validate 18-D cosign wiring in role 02 (sign) and role 03 (verify).

We don't run cosign from CI — signing happens at deploy time on the
control machine, and verification happens at deploy time too. This
check is the offline guard that future edits don't silently drop
any link in the chain.

What it validates:

  - role 02 build.yml has a cosign probe (delegate_to: localhost,
    soft-fail), warn-on-missing tasks for both `cosign not installed`
    and `private key path unset`, sign-binary, sign-sbom, and copy
    .sig-to-target tasks. All sign tasks are gated on probe success
    AND ja4proxy_cosign_private_key_path being non-empty.

  - role 03 main.yml has a cosign verify probe, warn-on-missing
    tasks for both `public key path unset` and `cosign not installed`,
    a verify task using cosign verify-blob, and an assert task that
    aborts the play when verify returns non-zero. All verify tasks
    are gated on ja4proxy_cosign_public_key_path being non-empty.

  - The verify task lives BEFORE the systemd start step, so a
    tampered binary aborts the play before any service runs.

  - group_vars/all.yml declares both vars defaulting to "" so a
    fresh checkout deploys without ceremony (18-D opt-in).
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BUILD_YML = ROOT / "deploy" / "roles" / "02-artifact-build" / "tasks" / "build.yml"
DEPLOY_YML = ROOT / "deploy" / "roles" / "03-ja4proxy-deploy" / "tasks" / "main.yml"
GROUP_VARS = ROOT / "deploy" / "inventory" / "group_vars" / "all.yml"


def _task_block(text: str, task_name_fragment: str) -> str:
    """Return the YAML block of the first task whose name contains fragment.

    Crude but reliable: find the task header, then return until the
    next `- name:` or end-of-file.
    """
    m = re.search(rf"- name:[^\n]*{re.escape(task_name_fragment)}[^\n]*\n", text)
    if not m:
        return ""
    start = m.start()
    rest = text[m.end():]
    nxt = re.search(r"\n\s*- name:", rest)
    return text[start: (m.end() + nxt.start()) if nxt else len(text)]


def check_build_yml() -> None:
    text = BUILD_YML.read_text()

    probe = _task_block(text, "Probe for cosign on control machine")
    warn_missing = _task_block(text, "Warn when cosign is not installed (18-D)")
    warn_unset = _task_block(text, "Warn when ja4proxy_cosign_private_key_path is unset")
    sign_bin = _task_block(text, "Sign binary with cosign sign-blob")
    sign_sbom = _task_block(text, "Sign SBOM with cosign sign-blob")
    copy_bin_sig = _task_block(text, "Copy binary signature to target")
    copy_sbom_sig = _task_block(text, "Copy SBOM signature to target")

    blocks = {
        "Probe for cosign on control machine (18-D)": probe,
        "Warn when cosign is not installed (18-D)": warn_missing,
        "Warn when ja4proxy_cosign_private_key_path is unset (18-D)": warn_unset,
        "Sign binary with cosign sign-blob (18-D)": sign_bin,
        "Sign SBOM with cosign sign-blob (18-D)": sign_sbom,
        "Copy binary signature to target (18-D)": copy_bin_sig,
        "Copy SBOM signature to target (18-D)": copy_sbom_sig,
    }
    for name, block in blocks.items():
        if not block:
            sys.exit(f"build.yml is missing the `{name}` task")

    required = [
        (probe, "cosign version", "probe invokes `cosign version`"),
        (probe, "delegate_to: localhost", "probe runs on control machine"),
        (probe, "failed_when: false", "probe is soft-fail (no cosign installed)"),
        (probe, "register: _cosign_probe", "probe registers _cosign_probe"),
        (warn_missing, "_cosign_probe.rc != 0", "warn-missing gated on probe failure"),
        (warn_unset, "ja4proxy_cosign_private_key_path", "warn-unset references the private key var"),
        (warn_unset, "| length == 0", "warn-unset triggers when var is empty"),
        (sign_bin, "cosign sign-blob", "sign-binary uses cosign sign-blob"),
        (sign_bin, "ja4proxy_cosign_private_key_path", "sign-binary uses the private key var"),
        (sign_bin, "delegate_to: localhost", "sign-binary runs on control machine"),
        (sign_bin, "_cosign_probe.rc == 0", "sign-binary gated on probe success"),
        (sign_bin, "| length > 0", "sign-binary gated on key path being non-empty"),
        (sign_sbom, "cosign sign-blob", "sign-sbom uses cosign sign-blob"),
        (sign_sbom, "_sbom_src", "sign-sbom uses the SBOM source path from 18-A"),
        (sign_sbom, "_cosign_probe.rc == 0", "sign-sbom gated on probe success"),
        (sign_sbom, "| length > 0", "sign-sbom gated on key path being non-empty"),
        (copy_bin_sig, "ja4proxy.sig", "copy-binary-sig writes ja4proxy.sig on target"),
        (copy_bin_sig, "_cosign_probe.rc == 0", "copy-binary-sig gated on probe success"),
        (copy_bin_sig, "| length > 0", "copy-binary-sig gated on key path being non-empty"),
        (copy_sbom_sig, "ja4proxy.cdx.json.sig", "copy-sbom-sig writes ja4proxy.cdx.json.sig on target"),
        (copy_sbom_sig, "_cosign_probe.rc == 0", "copy-sbom-sig gated on probe success"),
        (copy_sbom_sig, "| length > 0", "copy-sbom-sig gated on key path being non-empty"),
    ]
    errors = [msg for block, needle, msg in required if needle not in block]
    if errors:
        print("role 02 cosign wiring incomplete:")
        for e in errors:
            print(f"  - {e}")
        sys.exit(1)

    # Sign tasks must NOT carry `failed_when: false` — a failed signing
    # operation must abort, otherwise we'd ship unsigned artefacts
    # while pretending they were signed.
    for name, block in (("sign binary", sign_bin), ("sign SBOM", sign_sbom)):
        if "failed_when: false" in block:
            sys.exit(
                f"`{name}` task has `failed_when: false` — that would mask "
                "signing failures and let unsigned artefacts ship. Remove it."
            )

    # Ordering: cosign probe must come AFTER the SBOM is generated
    # (so we can sign it) and BEFORE the copy-to-target steps.
    pos_sbom = text.find("Generate SBOM from Go source tree")
    pos_probe = text.find("Probe for cosign on control machine")
    pos_sign = text.find("Sign binary with cosign sign-blob")
    pos_copy = text.find("Copy binary signature to target")
    if not (0 < pos_sbom < pos_probe < pos_sign < pos_copy):
        sys.exit(
            "cosign tasks must be ordered: SBOM emission → cosign probe → "
            "sign-blob → copy .sig to target"
        )

    print("✓ role 02 build.yml wires cosign sign-blob with soft-fail probe, opt-in key, correct order")


def check_deploy_yml() -> None:
    text = DEPLOY_YML.read_text()

    probe = _task_block(text, "Probe for cosign on control machine (18-D)")
    warn_unset = _task_block(text, "Warn when ja4proxy_cosign_public_key_path is unset")
    warn_missing = _task_block(text, "Warn when cosign is not installed (18-D)")
    verify = _task_block(text, "Verify binary signature with cosign verify-blob")
    assert_task = _task_block(text, "Assert binary signature verified")

    blocks = {
        "Probe for cosign on control machine (18-D)": probe,
        "Warn when ja4proxy_cosign_public_key_path is unset (18-D)": warn_unset,
        "Warn when cosign is not installed (18-D)": warn_missing,
        "Verify binary signature with cosign verify-blob (18-D)": verify,
        "Assert binary signature verified (18-D)": assert_task,
    }
    for name, block in blocks.items():
        if not block:
            sys.exit(f"role 03 main.yml is missing the `{name}` task")

    required = [
        (probe, "cosign version", "probe invokes `cosign version`"),
        (probe, "delegate_to: localhost", "probe runs on control machine"),
        (probe, "failed_when: false", "probe is soft-fail"),
        (probe, "register: _cosign_verify_probe", "probe registers _cosign_verify_probe"),
        (warn_unset, "ja4proxy_cosign_public_key_path", "warn-unset references the public key var"),
        (warn_unset, "| length == 0", "warn-unset triggers when var is empty"),
        (warn_missing, "_cosign_verify_probe.rc != 0", "warn-missing gated on probe failure"),
        (warn_missing, "ja4proxy_cosign_public_key_path", "warn-missing only fires when verify was wanted"),
        (verify, "cosign verify-blob", "verify uses cosign verify-blob"),
        (verify, "ja4proxy_cosign_public_key_path", "verify uses the public key var"),
        (verify, "delegate_to: localhost", "verify runs on control machine"),
        (verify, "_cosign_verify_probe.rc == 0", "verify gated on probe success"),
        (verify, "| length > 0", "verify gated on public key path being non-empty"),
        (verify, "register: _cosign_verify_binary", "verify registers _cosign_verify_binary"),
        (assert_task, "_cosign_verify_binary.rc == 0", "assert checks the verify return code"),
        (assert_task, "fail_msg:", "assert provides an operator-facing fail message"),
        (assert_task, "| length > 0", "assert gated on public key path being non-empty"),
    ]
    errors = [msg for block, needle, msg in required if needle not in block]
    if errors:
        print("role 03 main.yml cosign wiring incomplete:")
        for e in errors:
            print(f"  - {e}")
        sys.exit(1)

    # The verify task must NOT carry `failed_when: false` — a failed
    # verify is exactly what the assert wants to see and abort on.
    if "failed_when: false" in verify:
        sys.exit(
            "Verify binary signature task has `failed_when: false` — "
            "that would mask signature mismatches. Remove it."
        )

    # Ordering: verify + assert MUST land before the systemd start
    # step, so a tampered binary aborts before the service runs.
    pos_assert = text.find("Assert binary signature verified")
    pos_systemd_start = text.find("Enable and start JA4proxy service")
    if not (0 < pos_assert < pos_systemd_start):
        sys.exit(
            "cosign verify+assert must come BEFORE `Enable and start "
            "JA4proxy service` so a tampered binary aborts the deploy"
        )

    print("✓ role 03 main.yml wires cosign verify-blob with assert before systemd start")


def check_group_vars() -> None:
    text = GROUP_VARS.read_text()
    for var in ("ja4proxy_cosign_private_key_path", "ja4proxy_cosign_public_key_path"):
        m = re.search(rf'^{re.escape(var)}:\s*(.+?)\s*$', text, re.MULTILINE)
        if not m:
            sys.exit(f"group_vars/all.yml has no `{var}:` declaration")
        val = m.group(1).strip()
        if val not in ('""', "''"):
            sys.exit(
                f'{var} default is {val!r} — should default to "" so a '
                "fresh checkout is opt-in (no signing/verify by default)"
            )
    print('✓ group_vars/all.yml declares both cosign key vars defaulting to ""')


def main() -> int:
    check_build_yml()
    check_deploy_yml()
    check_group_vars()
    return 0


if __name__ == "__main__":
    sys.exit(main())
