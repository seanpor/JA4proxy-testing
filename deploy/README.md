# JA4proxy — Ansible Automated Deployment

Automated deployment of the JA4proxy research honeypot to an internet-facing Ubuntu VM.

## Prerequisites

- **Ansible 2.14+** on your control machine: `pip install ansible`
- **Go toolchain** (if building from source): `go version`
- **SSH access** to the target VM
- **Alibaba Cloud VM**: Ubuntu 22.04 LTS, minimum `ecs.g7.large` (2 vCPU, 8GB RAM, 40GB ESSD)

## Quick Start

```bash
# 1. Generate secrets (run once, stored in deploy/.vault/secrets.yml)
make secrets

# 2. Deploy everything
make deploy
```

The playbook will prompt for 5 required inputs:

| Input | Description | Example |
|-------|-------------|---------|
| Research domain | DNS name for the honeypot | `test-honeypot.example.com` |
| VM DNS name or IP | How Ansible connects to the VM | `47.254.123.45` |
| SSH user | User for initial connection | `root` |
| Your public IP | For SSH + admin UI allowlists | `1.2.3.4` |
| SSH public key | Full public key string | `ssh-ed25519 AAAA...` |
| Go repo path OR binary path | Build from source or use prebuilt | `/home/user/JA4proxy` |

## Partial Deployments

```bash
make check          # Dry run — see what would change
make provision      # VM provisioning only (Phase 1)
make docker         # Docker Compose only (Phase 4)
make validate       # Smoke tests only (Phase 7)
make harden         # Security hardening only (Phase 8)
```

## Operations

```bash
make status VM_IP=47.254.123.45   # Quick health check via SSH
make destroy VM_IP=47.254.123.45  # Stop all Docker containers
```

## After Deploying

1. **Access Grafana**: `http://<VM_IP>:3000`
   - User: `admin`
   - Password: see `deploy/.vault/secrets.yml`

2. **Access Prometheus**: `http://<VM_IP>:9091`

3. **Monitor logs**: `ssh root@<VM_IP> "journalctl -u ja4proxy -f"`

4. **Change dial setting** (gradually increase enforcement):
   ```bash
   ssh root@<VM_IP> "sed -i 's/dial: 0/dial: 20/' /opt/ja4proxy/config/proxy.yml"
   ssh root@<VM_IP> "kill -SIGHUP \$(pidof ja4proxy)"
   ```

## Idempotency

Safe to re-run:
```bash
make deploy    # Will only change what's different
make check     # Shows what would change without applying
```

## Alibaba Cloud Instance Sizing

| Size | vCPU | RAM | Storage | Use Case |
|------|------|-----|---------|----------|
| `ecs.g7.large` | 2 | 8GB | 40GB ESSD | Starting point, low-moderate traffic |
| `ecs.g7.xlarge` | 4 | 16GB | 60GB ESSD | High traffic, extended log retention |

## Troubleshooting

| Problem | Solution |
|---------|----------|
| SSH connection refused | Verify UFW allows your IP on port 22 |
| Docker pull fails | Check VM has outbound internet access |
| Caddy TLS cert fails | Verify DNS A record points to VM IP |
| JA4proxy won't start | `journalctl -u ja4proxy -n 50` for errors |
| Grafana unreachable | Check UFW allows your IP on port 3000 |
