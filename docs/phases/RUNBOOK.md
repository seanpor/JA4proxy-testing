# JA4proxy Research — Runbook & Rollback Guide

## Deployment Flow

```
make cloud ALIYUN_ARGS='...'  →  make secrets  →  make deploy
     (VM)                         (passwords)       (everything)
```

## Quick Reference

### Check Status
```bash
make status VM_IP=<ip>
```

### Change Dial Setting
```bash
ssh root@<ip> "sed -i 's/dial: [0-9]*/dial: 20/' /opt/ja4proxy/config/proxy.yml"
ssh root@<ip> "kill -SIGHUP \$(pidof ja4proxy)"
# Verify
curl -s http://127.0.0.1:9090/metrics | grep ja4proxy_dial_current
```

### View Logs
```bash
ssh root@<ip> "journalctl -u ja4proxy -f --no-pager"
ssh root@<ip> "docker compose -f /opt/ja4proxy-docker/docker-compose.yml logs -f"
```

## Rollback Procedures

### Scenario 1: Bad config change
```bash
# If SIGHUP reload broke something:
ssh root@<ip> "systemctl restart ja4proxy"

# If config file is corrupted:
scp deploy/templates/proxy.yml.j2 root@<ip>:/opt/ja4proxy/config/proxy.yml
ssh root@<ip> "systemctl restart ja4proxy"
```

### Scenario 2: Docker Compose stack broken
```bash
# Stop and recreate:
ssh root@<ip> "cd /opt/ja4proxy-docker && docker compose down && docker compose up -d"

# If images are corrupted:
ssh root@<ip> "cd /opt/ja4proxy-docker && docker compose down && docker compose pull && docker compose up -d"
```

### Scenario 3: Full rollback to previous state
```bash
# Re-run Ansible with check mode first:
make check EXTRA_VARS="-e ja4proxy_domain=x -e ja4proxy_vm_host=<ip> ..."

# Then re-deploy:
make deploy EXTRA_VARS="-e ja4proxy_domain=x -e ja4proxy_vm_host=<ip> ..."
```

### Scenario 4: VM compromise
```bash
# 1. Isolate (kill switch)
ssh root@<ip> "ufw default deny incoming && ufw default deny outgoing"
ssh root@<ip> "ufw allow from <admin_ip> to any port 22 proto tcp"
ssh root@<ip> "ufw allow out to any port 53 proto udp"
ssh root@<ip> "ufw --force enable"

# 2. Preserve evidence
ssh root@<ip> "journalctl --no-pager > /tmp/evidence-journal.log"
ssh root@<ip> "docker compose -f /opt/ja4proxy-docker/docker-compose.yml logs > /tmp/evidence-docker.log"
scp root@<ip>:/tmp/evidence-*.* ./evidence/

# 3. Destroy VM via Alibaba Cloud console

# 4. Provision new VM and re-deploy
make cloud ALIYUN_ARGS='--region eu-central-1 ...'
make deploy
```

## Troubleshooting

| Symptom | Diagnosis | Fix |
|---------|-----------|-----|
| SSH connection refused | UFW blocking or SSH not running | Check security group in Alibaba Cloud console |
| `make deploy` fails at "Add target host" | `ja4proxy_vm_host` not set | Pass `-e ja4proxy_vm_host=<ip>` |
| `make deploy` fails at collections install | No internet on control machine | `ansible-galaxy collection install community.general community.docker ansible.posix` |
| Docker pull timeout | Slow network or Docker Hub rate limit | Re-run `make deploy` — images cache on retry |
| Caddy TLS cert fails | DNS not propagated or port 80 blocked | Verify DNS A record → VM IP, UFW allows 80/tcp |
| JA4proxy won't start | Missing GeoIP or bad config | `journalctl -u ja4proxy -n 50` |
| Grafana unreachable | UFW blocking 3000 | `ufw allow from <admin_ip> to any port 3000 proto tcp` |
| Redis not found by JA4proxy | Redis Docker not started | `systemctl start ja4proxy-redis` |
| Prometheus scraping fails | JA4proxy metrics port not bound | `ss -tlnp \| grep 9090` |

## Budget alert setup

The `provision-alibaba-cloud.sh` script prints an indicative monthly
cost estimate and refuses to run without `--confirm`. That's a reminder,
not a hard limit — the Alibaba account itself is what the budget alert
catches.

1. In the Alibaba Cloud console, open **Billing Management → Budgets**.
2. Create a budget named `ja4proxy-research` scoped to the tag or
   resource group that holds the honeypot VM + EIP.
3. Set the monthly amount to ~1.5× the estimate printed by the
   provisioning script (gives headroom for egress spikes from scanners).
4. Add two alert thresholds: **80%** (email only) and **100%** (email +
   SMS if available).
5. Confirm the alert email arrives by triggering a test notification
   before relying on it.

If the budget alert fires, the first action is `make destroy VM_IP=…`
to stop the Docker stack and cut egress; only then diagnose the spike.

## PTR record (reverse DNS) request

A missing or generic PTR record causes abuse reports against the
honeypot IP to be attributed to Alibaba rather than to you. Request
a PTR before go-live:

1. Decide the PTR target — typically `honeypot.<your-domain>` with an
   `abuse@` mailbox already answered on it.
2. Open an Alibaba ticket under **Network → EIP → Reverse DNS** with:
   - EIP address
   - Desired PTR FQDN (matching a forward A record you control)
   - A one-line justification ("security research honeypot; abuse
     contact published in /.well-known/security.txt")
3. Wait for confirmation (usually < 24h) and verify with
   `dig -x <eip>`. The answer must match the FQDN exactly.
4. Only then run `make go-live VM_IP=…`. Abuse reports sent before the
   PTR lands will go to Alibaba's abuse desk, not yours.

## Incident Response Scenarios

Eight named scenarios the operator may realistically face. Each has
**Preconditions**, a numbered **Procedure**, and a **Rollback** note.
The CI check `scripts/ci/check_runbook_scenarios.py` asserts all
eight remain present.

### 1. SSH lockout

**Preconditions.** `ssh root@<ip>` hangs or returns "Connection
refused". UFW is suspected of blocking the admin IP, or the admin IP
has changed, or `ja4proxy_admin_ip` was misconfigured.

**Procedure.**

1. Confirm the symptom from a second network (mobile hotspot) to rule
   out a local egress problem.
2. Open the Alibaba Cloud console → ECS → the honeypot VM →
   **Connect** (VNC). This bypasses UFW entirely.
3. Once logged in locally, check UFW: `ufw status verbose`.
4. Add a rule for your *current* public IP:
   `ufw allow from <new_admin_ip> to any port 22 proto tcp`.
5. Update `ja4proxy_admin_ip` in the deploy inputs so the next
   `make deploy` doesn't revert the console fix.
6. Test SSH from the outside before closing the console session.

**Rollback.** If the new rule itself is wrong, revert via the
console: `ufw delete allow from <new_admin_ip> to any port 22`. The
console session always works — it does not use UFW.

### 2. Caddy ACME rate-limit

**Preconditions.** Let's Encrypt production returns
`urn:ietf:params:acme:error:rateLimited` in Caddy logs; the
honeypot is serving a self-signed cert instead of a valid one. Most
often caused by rapid re-deploys flipping ACME on/off.

**Procedure.**

1. Confirm the rate-limit in Caddy logs:
   `docker compose -f /opt/ja4proxy-docker/docker-compose.yml logs caddy | grep -i ratelimit`.
2. Set `ja4proxy_acme_staging: true` in deploy inputs and re-deploy —
   staging has far laxer limits and validates the config without
   burning production quota.
3. Wait out the rate-limit window (typically 1h per-domain,
   168h for duplicate certs) — do **not** repeatedly re-deploy; every
   attempt re-extends the window.
4. When the window has elapsed, flip `ja4proxy_acme_staging: false`
   and re-run `make go-live` so production ACME is requested exactly
   once.

**Rollback.** Leaving the deployment on staging is safe — clients
see an untrusted cert warning but the probe still works. Revert is
the step-4 flip above.

### 3. Redis corruption

**Preconditions.** Ja4proxy logs show
`redis: connection refused` or `WRONGTYPE` errors; ban lookups
return inconsistent results; the `ja4proxy-redis` unit may be
crash-looping.

**Procedure.**

1. Stop JA4proxy to quiesce writers:
   `systemctl stop ja4proxy`.
2. Inspect: `systemctl status ja4proxy-redis` and
   `journalctl -u ja4proxy-redis -n 100 --no-pager`.
3. If the RDB file is corrupt, stop Redis:
   `systemctl stop ja4proxy-redis`, then move the dump aside:
   `mv /var/lib/ja4proxy-redis/dump.rdb /var/lib/ja4proxy-redis/dump.rdb.corrupt-$(date +%s)`.
4. Start Redis fresh: `systemctl start ja4proxy-redis`. The ban list
   starts empty — acceptable because bans are short-TTL and
   rebuildable from traffic.
5. Start JA4proxy: `systemctl start ja4proxy`.

**Rollback.** The corrupt RDB was renamed, not deleted — restore
with `mv dump.rdb.corrupt-<ts> dump.rdb` and restart Redis. Keep
the corrupt file for post-mortem; delete after diagnosis.

### 4. Disk full

**Preconditions.** `DiskFull` alert fires, or `df -h /` shows < 10%
free. Most often Loki or Prometheus growing past their retention
caps because a timer failed; sometimes journald keeping old rotations.

**Procedure.**

1. Triage: `du -sh /var/lib/docker/volumes/* /var/log/* | sort -h`.
2. If Loki or Prometheus is the culprit, the retention caps already
   exist — verify the service is actually running and enforcing them:
   `docker compose -f /opt/ja4proxy-docker/docker-compose.yml ps`.
3. Force Prometheus to evict early if needed:
   `docker compose restart prometheus` (retention runs on startup).
4. If journald: `journalctl --vacuum-time=30d` to trim.
5. If Docker image layers: `docker image prune -af` (safe — images
   repull on next deploy).
6. Resize the volume via Alibaba console only as a last resort; a
   disk full because retention isn't enforcing is a bug, not a
   capacity problem.

**Rollback.** All the above are additive cleanups. The only
destructive step is `docker image prune`; re-running `make deploy`
repulls every image from its digest pin.

### 5. Grafana password reset

**Preconditions.** Grafana admin login fails; the vault-stored
`grafana_admin_password` has been lost, rotated out of sync, or is
wrong for this deployment.

**Procedure.**

1. Stop Grafana:
   `docker compose -f /opt/ja4proxy-docker/docker-compose.yml stop grafana`.
2. Reset the admin password inside the container's persistent volume:
   `docker run --rm -v ja4proxy-docker_grafana-data:/var/lib/grafana grafana/grafana grafana-cli --homepath=/usr/share/grafana --configOverrides cfg:default.paths.data=/var/lib/grafana admin reset-admin-password '<new-password>'`.
3. Update `grafana_admin_password` in
   `deploy/.vault/secrets.yml` via `make vault-edit`.
4. Start Grafana: `docker compose up -d grafana`.
5. Log in with the new password; rotate via the UI if preferred.

**Rollback.** None required — the old password was unknown by
definition. Keep the new password in `secrets.yml` so the next
deploy doesn't overwrite it.

### 6. VM compromise

**Preconditions.** AIDE fires an unexpected binary change; a
fingerprint in logs matches known post-exploit tooling; outbound
traffic from the VM that isn't ACME or healthchecks.io is observed.

**Procedure.**

1. Isolate immediately:
   ```
   ufw default deny incoming && ufw default deny outgoing
   ufw allow from <admin_ip> to any port 22 proto tcp
   ufw --force enable
   ```
2. Preserve evidence using the packaged helper (do not ad-hoc this):
   `/usr/local/sbin/preserve-evidence.sh` (from 15-A). It writes a
   mode-0600 tarball to `/var/local/ja4proxy-evidence/`. `scp` the
   tarball off before the next step.
3. Destroy the VM via the Alibaba console (do not `apt remove` or
   `docker rm` — those modify evidence).
4. Rotate every credential the VM held: SSH keys, vault password,
   any external webhook URLs (heartbeat, SMTP), and the domain's
   DNS credentials if the registrar password was on the VM.
5. Provision a fresh VM at a new IP:
   `make cloud ALIYUN_ARGS='...' && make deploy && make verify`.
6. File any required disclosures — see
   [`../governance/LE_REQUESTS.md`](../governance/LE_REQUESTS.md)
   if law enforcement is involved.

**Rollback.** Not applicable — compromise is a forward-only
recovery. The old VM is not restored; it is replaced.

### 7. Law-enforcement request

**Preconditions.** A legal instrument (subpoena, warrant, voluntary
request) lands in the security.txt mailbox or via the
`/privacy.html` contact. The operator is the single accountable
party.

**Procedure.**

1. Acknowledge receipt; **do not respond with data at intake**.
2. Follow the procedure in
   [`../governance/LE_REQUESTS.md`](../governance/LE_REQUESTS.md) —
   validate jurisdiction, proportionality, legal instrument.
3. If producing data, run `/usr/local/sbin/preserve-evidence.sh`
   first so the export is itself captured as evidence.
4. HMAC-anonymise where the instrument does not explicitly require
   raw IPs (12-B once available; redact manually until then).
5. Transmit over a channel matched to sensitivity — encrypted email
   or the requesting authority's portal, never cleartext SMTP.
6. Record the request + decision + what was produced; retain per
   the retention policy in `LE_REQUESTS.md` §4.

**Rollback.** Once data has been disclosed, it cannot be recalled.
The only reversible step is refusing production; once produced,
rollback means notifying the data subjects where the legal
instrument permits.

### 8. DNS misconfig opened UFW to the wrong host

**Preconditions.** `make go-live` opened UFW on 80/443 but the A
record actually points somewhere else, or an MX record is the
wildcard catchall, or the PTR was not set. Symptom: traffic to the
honeypot is absent, or abuse reports go to Alibaba instead of us.

**Procedure.**

1. Verify from outside:
   `dig A <domain>` vs `curl -sI https://<domain>` — confirm the
   Host header and TLS SNI land on this VM.
2. If the A record is wrong, close UFW **before** fixing DNS:
   `ufw deny 80/tcp && ufw deny 443/tcp && ufw reload`.
3. Correct the DNS record at the registrar; wait for TTL.
4. Re-run the preflight checks:
   `make check VM_IP=<ip>` — role 10's DNS + MX preflight tasks
   (11-D, 13-G) refuse to open UFW unless the A record resolves to
   this VM.
5. Re-run `make go-live VM_IP=<ip>`; UFW re-opens only after the
   preflight passes.
6. If PTR is missing, follow the **PTR record** section above
   before considering the deployment live.

**Rollback.** Step 2 (close 80/443) is the rollback. Leaving UFW
closed is safe — the honeypot is simply invisible until DNS and UFW
agree.

## Monitoring Schedule

| Frequency | Action | Duration |
|-----------|--------|----------|
| Daily | `make status VM_IP=<ip>` | 1 min |
| Weekly | Review Grafana dashboards, export data | 30 min |
| Monthly | Security audit, dial escalation review | 2 hours |
| Quarterly | Update Docker image digests (`make digests`) | 30 min |
