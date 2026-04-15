# Phase 13: Post-Launch Operations

## Purpose

Everything that keeps a live research honeypot from silently dying, silently overspending, or silently losing its TLS cert. None of this is fully in place today.

## Deliverables

### 13.1 Alerting and dead-man's switch

Prometheus and Grafana are deployed without Alertmanager. For a research run that expects to emit data 24/7, silent failure is the worst outcome — we lose both the day's data and the chance to notice.

**Add:**
- Alertmanager container in `docker-compose.yml`, bound to `127.0.0.1:9093`.
- Prometheus `alerting:` block pointing at it.
- Rule file `deploy/files/prometheus/alert-rules.yml` with at minimum:
  - `JA4proxyDown` — `up{job="ja4proxy"} == 0` for 2 m.
  - `HAProxyDown` — analogous.
  - `RedisDown` — analogous.
  - `NoTrafficLastHour` — `rate(ja4proxy_connections_total[1h]) == 0` for 1 h (the dead-man's-switch: if a public VM receives zero traffic for an hour, something is wrong upstream — DNS, UFW, ACME, or the provider null-routed us).
  - `CertExpiringSoon` — `probe_ssl_earliest_cert_expiry - time() < 7*24*3600`. Requires blackbox-exporter; add that to the stack.
  - `DiskFull` — `node_filesystem_avail_bytes{mountpoint="/"} / node_filesystem_size_bytes < 0.10`.
- Alert delivery: email via a minimal SMTP relay (operator's existing provider) or a webhook to the operator's phone. Not Slack-only — Slack goes down exactly when you need it.

**Heartbeat:** a once-per-5-minute push to a dead-man's-switch service (e.g. deadmanssnitch.com, healthchecks.io self-hosted, or a cheap cron on a separate VPS pinging itself). The ping itself is what proves the VM is alive; absence of ping is what pages you. Without this, a VM that's UFW-locked-out-of-itself is invisible to you.

### 13.2 TLS certificate health

Caddy renews Let's Encrypt automatically and on success this phase is boring. We design for the days it fails.

- Add `blackbox_exporter` to the stack, probe `https://<domain>/` with `tls_config.server_name`.
- Alert on `probe_ssl_earliest_cert_expiry - time() < 7*24*3600` as above.
- In `RUNBOOK.md`, add a section "Caddy ACME failure": how to read `docker compose logs caddy`, how to reset the ACME account if rate-limited, how to temporarily fall back to the last known-good cert.

### 13.3 DNS preflight for go-live

Add to the PHASE_10 precondition block:

```yaml
- name: Resolve domain to public IP
  ansible.builtin.command:
    cmd: "dig +short {{ ja4proxy_domain }}"
  delegate_to: localhost
  register: dns_resolved
  changed_when: false

- name: Assert DNS points to the VM
  ansible.builtin.assert:
    that:
      - ja4proxy_vm_host in dns_resolved.stdout_lines
    fail_msg: "{{ ja4proxy_domain }} does not resolve to {{ ja4proxy_vm_host }}."
```

If the A record is missing or stale, abort before touching UFW or LE.

### 13.4 ACME staging mode on first deploy

Phase 4's Caddy config today is all-or-nothing. Add `ja4proxy_acme_staging: true` as the default, with `false` only flipped by PHASE_10 on go-live. Rationale: the staging CA has generous rate limits, so repeated "real" deploys during development don't burn production budget. The cert is browser-invalid but that's fine behind an SSH tunnel.

### 13.5 SSH trust bootstrap (fix for host_key_checking = False)

Remove `host_key_checking = False` from `deploy/ansible.cfg`. Replace the workflow with:

- `provision-alibaba-cloud.sh` captures the VM's SSH host keys as soon as cloud-init posts them (Alibaba ECS exposes them via `GetInstanceConsoleOutput` on some instance types; for others, add a preflight step that runs `ssh-keyscan` with `-T 5` and pins the first observed key to `~/.ssh/known_hosts`, with an explicit operator "does this match?" prompt if there's any existing entry).
- Document the TOFU window: between the VM becoming reachable and the host key being pinned, a MitM is theoretically possible. For a research box this is acceptable if the operator confirms the fingerprint via the cloud console on first connect.

### 13.6 Secrets rotation

- New role `deploy/roles/12-secrets-rotation/` (tagged `rotate`, not in the default playbook). Regenerates Redis password, Grafana admin password, HAProxy stats password; re-deploys dependent configs; restarts the affected containers with zero data loss.
- Make target: `make rotate VM_IP=…`. Quarterly cadence.
- On rotation, `deploy/.vault/secrets.yml` is re-encrypted with `ansible-vault`.

### 13.7 Ansible-vault encryption of secrets at rest

`deploy/scripts/generate-secrets.sh` currently writes plaintext. Extend it:

1. Generate into a temp file.
2. Run `ansible-vault encrypt --vault-id ja4proxy@<pass-file> <temp>`.
3. Move into `deploy/.vault/secrets.yml`.
4. Document in README: operator keeps the vault passphrase in their password manager, not in the repo.

Update `site.yml` `include_vars` accordingly; Ansible handles vault-encrypted `include_vars` transparently if the vault password is supplied.

### 13.8 AIDE scheduling

`aideinit` runs once in role 08 and is then never exercised. Add a systemd timer:

```
/etc/systemd/system/aide-check.timer  — daily 03:30
/etc/systemd/system/aide-check.service — runs `aide --check`, emails operator on non-zero exit
```

Without this, AIDE is a checkbox; with it, it's actually a tripwire.

### 13.9 Cost controls (Alibaba Cloud)

- Provisioning script should print the estimated monthly cost (instance + bandwidth + storage) and require `--confirm` to proceed past it.
- Set a **budget alert** via Alibaba's billing console (manual step, documented in runbook) at 1.5× expected monthly cost.
- **Idle auto-shutdown** (optional): a systemd timer that, if `rate(ja4proxy_connections_total[24h]) == 0`, emails the operator with a "shall we tear down?" prompt. Don't auto-shutdown — a dead signal might be a go-live bug, not genuine idleness.
- Record the **bandwidth** plan on the ECS: pay-as-you-go is easy to overspend; fixed-bandwidth is safer for research that may attract a burst. Default to fixed-bandwidth at 5 Mbit/s unless the research specifically needs high throughput.

### 13.10 Reverse DNS (PTR)

Not strictly operations, but adjacent: request a PTR record for the VM's public IP that points to `<ja4proxy_domain>`. Many mail servers refuse to accept abuse@-replies from IPs without a PTR, so without it the abuse contact path is unreliable.

## Acceptance criteria

```
[ ] Alertmanager is running, a deliberately-failing alert reaches the operator's inbox
[ ] The deadmanssnitch / healthchecks heartbeat is green for 24h
[ ] blackbox_exporter reports cert expiry > 30 days
[ ] DNS preflight step refuses to go live when the A record is stale
[ ] deploy/.vault/secrets.yml is ansible-vault encrypted (file starts with $ANSIBLE_VAULT;)
[ ] systemctl list-timers shows aide-check.timer and ja4proxy-rotate hints (quarterly cron is OK instead)
[ ] host_key_checking is True in ansible.cfg
[ ] The VM's PTR record resolves to ja4proxy_domain
```

## Related

- `docs/phases/CRITICAL_REVIEW.md` §A4, §A5, §A6, §C4
- `docs/phases/PHASE_10_GO_LIVE.md` (imports preconditions from 13.3)
- `docs/phases/RUNBOOK.md` (expand with runbook entries referenced above)
