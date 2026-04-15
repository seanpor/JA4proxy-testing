# VM smoke test — first real deploy

Unit tests (`make lint && make test`) prove the playbook, templates,
and scripts are internally consistent. They cannot prove the thing
actually deploys. This runbook is the minimum-friction first real-VM
exercise — designed to burn ~one hour and ~USD 2–10 of ECS time, and
to confirm A1–A9 fixes hold end-to-end.

**Scope**: locked-state deploy only. Phase 10 (go-live, public ports,
production ACME) is explicitly out of scope for the smoke test.

**Expected outcome**: a VM in the Alibaba eu-central-1 region running
the full stack bound to 127.0.0.1, passing all 25+ `verify-local.sh`
checks, then torn down.

## Pre-flight (control machine)

Run from the repo root on `main`.

```bash
make lint && make test       # must be green before you start
git log -1 --oneline         # record the SHA you're deploying
```

Aliyun CLI:
```bash
aliyun --version             # install via `brew install aliyun-cli` or equivalent
aliyun configure list        # must show a valid AccessKey, region eu-central-1
```

SSH + env:
```bash
test -f ~/.ssh/id_ed25519 || test -f ~/.ssh/id_rsa   # A7 key discovery will find one
export JA4PROXY_ADMIN_IP="$(curl -s https://api.ipify.org)"
echo "$JA4PROXY_ADMIN_IP"    # sanity — this is what UFW allows through for SSH
```

Collections (A6):
```bash
make collections             # pinned install from deploy/requirements.yml
```

## Provision

```bash
make cloud ALIYUN_ARGS="--region eu-central-1 --ssh-key-name <key> --admin-ip $JA4PROXY_ADMIN_IP"
```

Expected:
- ECS instance + EIP provisioned
- `provision-alibaba-cloud.sh` pre-pins the host key via `ssh-keyscan` (A4) → `~/.ssh/known_hosts` gets a new entry
- `deploy/inventory/hosts.ini` is rewritten with the EIP (no hardcoded key path — A7)
- Prints the EIP; record it:

```bash
export VM_IP=<EIP printed by make cloud>
ssh root@$VM_IP 'uname -a'   # confirms the pre-pin: no "host key accepted" prompt
```

## Deploy (locked state)

```bash
make secrets                 # A5: creates deploy/.vault/.vault-pass, encrypts secrets.yml
head -c 20 deploy/.vault/secrets.yml   # must start with "$ANSIBLE_VAULT;"

make deploy
```

Prompts you'll see (or pre-set via `JA4PROXY_*` env):
- `ja4proxy_domain` — use `smoketest.example.com` (resolves nowhere; fine for locked deploy)
- `ja4proxy_vm_host` — `$VM_IP`
- `ja4proxy_ssh_user` — `root`
- `ja4proxy_admin_ip` — `$JA4PROXY_ADMIN_IP`
- `ja4proxy_ssh_public_key` — your public key string (goes into `authorized_keys`)

Watch for:
- **A8 assert**: "JA4proxy binary SHA256 verified: <hex>" — source and target match
- **A3 assert (role 08)**: AppArmor profile is loaded and `/proc/<pid>/attr/current` reports enforce/complain mode
- **A2 assert (role 09)**: every `image:` line in the compose file ends `@sha256:<hex64>` after pin
- **A9**: `nf_conntrack` modprobe should NOT print `ignored` — either succeeds, or the grep on `/proc/modules` follows up

Deploy should finish without any `ignored=1` or `failed=1` totals in the final PLAY RECAP.

## Verify

```bash
make verify VM_IP=$VM_IP     # runs deploy/scripts/verify-local.sh over SSH
```

All 25+ checks should pass. Expected failures in locked state:
- None — locked state is the verify target.
- If anything public-facing (`curl` to `$VM_IP:443` from the control machine) is checked, that should still succeed because HAProxy is bound to 0.0.0.0 inside the VM; UFW blocks it from outside. The check uses SSH → localhost.

Quick manual spot-checks:
```bash
ssh root@$VM_IP 'ss -tlnp | grep -E ":80 |:443 |:8080 |:9090 "'
# all should show 127.0.0.1, not 0.0.0.0 (locked-state invariant)

ssh root@$VM_IP 'systemctl status ja4proxy --no-pager | head -20'
# Active: active (running), AppArmor: ja4proxy profile visible

ssh root@$VM_IP 'ufw status | grep -c "^22/tcp.*ALLOW.*'"$JA4PROXY_ADMIN_IP"'"'
# must be 1 — SSH only from your IP
```

## Teardown

Same session — do not skip. An orphaned ECS instance bills by the minute.

```bash
make destroy VM_IP=$VM_IP    # docker compose down on the VM
```

Release the cloud resources:
```bash
# The provision script logged the instance + EIP IDs. Release in this order:
aliyun ecs StopInstance   --InstanceId <id> --ForceStop true --RegionId eu-central-1
aliyun ecs DeleteInstance --InstanceId <id>                   --RegionId eu-central-1
aliyun vpc  ReleaseEipAddress --AllocationId <eip-id>         --RegionId eu-central-1
# VPC/VSwitch/SecurityGroup can stay for the next run; they're free.
```

Remove the pinned host-key entry so the next smoke test with a recycled EIP doesn't MITM-alarm:
```bash
ssh-keygen -R "$VM_IP"
```

## What this exercise proves

| Fix | Evidence |
|-----|----------|
| A1 secrets path | `deploy/.vault/secrets.yml` exists after `make secrets`; playbook loads it without error |
| A2 digest regex | role 09 runs without "regex not idempotent" / post-assert failures |
| A3 AppArmor    | role 08 procfs check passes; `systemctl status ja4proxy` shows the profile |
| A4 host-key    | no "authenticity of host cannot be established" prompts after the pre-pin |
| A5 vault       | `head -c 20` on `secrets.yml` shows `$ANSIBLE_VAULT;` |
| A6 collections | `make collections` installs only pinned versions |
| A7 ssh key     | deploy proceeds without a hardcoded `~/.ssh/id_ed25519` path |
| A8 checksum    | "JA4proxy binary SHA256 verified" line appears |
| A9 ignore_errors | `nf_conntrack` verification fails loud if module isn't present |

Paste the PLAY RECAP and the post-verify output into the PR comment
of whatever you're testing — that's the receipt that A1–A9 hold on
real hardware.

## Budget sanity

eu-central-1 ecs.t6-c1m1.large + 1 EIP + outbound data ≈ **USD 0.03/hour + USD 0.005/hour EIP + USD 0.08/GB egress**. A full smoke test (provision → deploy → verify → teardown) takes ~30 min of billable time. Well under USD 1 if you don't leave it running.

## When to re-run

- Before merging any PR that touches Phase 0–9 roles or templates.
- After any Ansible-core, community.docker, or community.general version bump.
- Before first-time `make go-live` on a new VM (smoke-test first, then go live on the same VM).
