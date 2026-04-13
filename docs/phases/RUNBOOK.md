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

## Monitoring Schedule

| Frequency | Action | Duration |
|-----------|--------|----------|
| Daily | `make status VM_IP=<ip>` | 1 min |
| Weekly | Review Grafana dashboards, export data | 30 min |
| Monthly | Security audit, dial escalation review | 2 hours |
| Quarterly | Update Docker image digests (`make digests`) | 30 min |
