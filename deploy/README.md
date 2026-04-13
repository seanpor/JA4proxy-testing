# JA4proxy — Ansible Automated Deployment

Automated deployment of the JA4proxy research honeypot to an internet-facing Ubuntu VM.

## Prerequisites

- **Ansible 2.14+** on your control machine: `pip install ansible`
- **Go toolchain** (if building from source): `go version`
- **SSH access** to the target VM
- **Alibaba Cloud CLI** (`aliyun`) — for VM provisioning: `pip install aliyun-cli`
- **Alibaba Cloud credentials** — set via `aliyun configure` or env vars

### Required Collections (auto-installed on first run)
- `community.general` — UFW, debconf modules
- `community.docker` — Docker Compose v2 module
- `ansible.posix` — sysctl, authorized_key modules

## Quick Start

### Option A: Fresh Alibaba Cloud VM

```bash
# 1. Provision the VM (creates VPC, security group, ECS instance, EIP)
make cloud ALIYUN_ARGS="--region eu-central-1 --instance-type ecs.g7.large --ssh-key-name my-key-pair --admin-ip 1.2.3.4 --domain test-honeypot.example.com"

# 2. Generate secrets (run once)
make secrets

# 3. Deploy everything (LOCKED DOWN — no public ports)
make deploy

# 4. Verify all services locally via SSH tunnel
make verify VM_IP=<ip>

# 5. Open to public internet (go-live)
make go-live VM_IP=<ip>
```

### Option B: Existing VM

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

## Security: Staged Deployment

This deployment uses a **three-stage model** to ensure the system is verified internally before any ports are exposed to the public internet:

| Stage | Port Bindings | TLS | UFW 80/443 | Access Method |
|-------|--------------|-----|------------|---------------|
| **locked** (default) | 127.0.0.1 only | Self-signed | Closed | SSH tunnel |
| **verified** | 127.0.0.1 only | Self-signed | Closed | SSH tunnel (admin confirmed) |
| **live** | 0.0.0.0 (public) | Let's Encrypt | Open | Direct HTTPS |

### How It Works

1. **`make deploy`** deploys in `locked` mode:
   - All Docker ports bound to `127.0.0.1` (not public)
   - Caddy uses self-signed TLS certificates
   - UFW blocks ports 80/443 from the public
   - Only SSH (port 22) and admin-IP-only ports (Grafana, Prometheus) are open

2. **`make verify VM_IP=<ip>`** runs 25+ checks via SSH:
   - All systemd services healthy
   - All Docker containers running
   - Full pipeline works: `curl https://127.0.0.1:443/` → honeypot HTML
   - Network isolation verified (Redis/Loki can't reach internet)
   - Dial=0 (monitor-only) confirmed

3. **`make go-live VM_IP=<ip>`** opens the system:
   - Re-deploys docker-compose.yml with public port bindings
   - Updates Caddyfile for production Let's Encrypt ACME
   - Opens UFW ports 80/443
   - Verifies public HTTPS works

### SSH Tunnel Access (locked mode)

```bash
# Tunnel Grafana to your local machine
ssh -L 3000:127.0.0.1:3000 root@<VM_IP>
# Then open: http://localhost:3000

# Tunnel Prometheus
ssh -L 9091:127.0.0.1:9091 root@<VM_IP>
# Then open: http://localhost:9091

# View logs directly
ssh root@<VM_IP> "journalctl -u ja4proxy -f"
ssh root@<VM_IP> "docker compose -f /opt/ja4proxy-docker/docker-compose.yml logs -f"
```

## Partial Deployments

```bash
make check          # Dry run — see what would change
make cloud          # Provision Alibaba Cloud VM (aliyun CLI required)
make digests        # Pin Docker image SHA-256 digests (supply chain security)
make verify         # Run 25+ local health checks via SSH
make go-live        # Open ports to public (requires VM_IP)
make docker         # Docker Compose only (Phase 4)
make validate       # Smoke tests only (Phase 7)
make harden         # Security hardening only (Phase 8)
```

## CI/CD Usage

```bash
# All inputs via environment variables — no prompts
JA4PROXY_DOMAIN=test.example.com \
JA4PROXY_VM_HOST=47.254.123.45 \
JA4PROXY_ADMIN_IP=1.2.3.4 \
JA4PROXY_SSH_PUBLIC_KEY="ssh-ed25519 AAAA..." \
JA4PROXY_BUILD_MACHINE_GO_PATH=/home/user/JA4proxy \
make ci-deploy
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
