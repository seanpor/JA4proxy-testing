#!/bin/bash
# ─────────────────────────────────────────────────────────────
# Alibaba Cloud ECS Instance Provisioning for JA4proxy Research
# ─────────────────────────────────────────────────────────────
#
# Prerequisites:
#   - Alibaba Cloud CLI (aliyun) installed and configured
#   - Credentials in ~/.aliyun/config.json or env vars
#
# Usage:
#   bash deploy/scripts/provision-alibaba-cloud.sh \
#     --region eu-central-1 \
#     --zone eu-central-1a \
#     --instance-type ecs.g7.large \
#     --ssh-key-name my-key-pair \
#     --admin-ip 1.2.3.4 \
#     --domain test-honeypot.example.com
#
# This script:
#   1. Creates a VPC and vSwitch (or reuses existing)
#   2. Creates a security group with UFW-like rules
#   3. Launches an Ubuntu 22.04 ECS instance
#   4. Allocates and attaches an EIP (public IP)
#   5. Creates DNS A record (if domain provided)
#   6. Outputs connection details for Ansible
# ─────────────────────────────────────────────────────────────

set -euo pipefail

# ── Defaults ─────────────────────────────────────────────────
REGION="eu-central-1"
ZONE=""
INSTANCE_TYPE="ecs.g7.large"
SSH_KEY_NAME=""
ADMIN_IP=""
DOMAIN=""
INSTANCE_NAME="ja4proxy-research"
IMAGE_ID="ubuntu_22_04_x64_20G_alibase_2024*"
SYSTEM_DISK_SIZE=40
SYSTEM_DISK_CATEGORY="cloud_essd"
VPC_CIDR="172.16.0.0/16"
VSWITCH_CIDR="172.16.0.0/24"

# ── Parse Arguments ──────────────────────────────────────────
while [[ $# -gt 0 ]]; do
    case $1 in
        --region) REGION="$2"; shift 2 ;;
        --zone) ZONE="$2"; shift 2 ;;
        --instance-type) INSTANCE_TYPE="$2"; shift 2 ;;
        --ssh-key-name) SSH_KEY_NAME="$2"; shift 2 ;;
        --admin-ip) ADMIN_IP="$2"; shift 2 ;;
        --domain) DOMAIN="$2"; shift 2 ;;
        --instance-name) INSTANCE_NAME="$2"; shift 2 ;;
        --disk-size) SYSTEM_DISK_SIZE="$2"; shift 2 ;;
        --help) echo "Usage: $0 --region <region> --ssh-key-name <name> --admin-ip <ip>"; exit 0 ;;
        *) echo "Unknown option: $1"; exit 1 ;;
    esac
done

# ── Validate Required Inputs ─────────────────────────────────
if [[ -z "$SSH_KEY_NAME" ]]; then
    echo "❌ --ssh-key-name is required. Create one in the Alibaba Cloud console first."
    exit 1
fi
if [[ -z "$ADMIN_IP" ]]; then
    echo "❌ --admin-ip is required (your public IP for SSH access)."
    exit 1
fi
if [[ -z "$ZONE" ]]; then
    # Auto-detect zone from region
    ZONE="${REGION}a"
    echo "ℹ️  Zone not specified, using: $ZONE"
fi

echo "╔══════════════════════════════════════════════════════╗"
echo "║   JA4proxy — Alibaba Cloud ECS Provisioning          ║"
echo "╚══════════════════════════════════════════════════════╝"
echo ""
echo "Region:        $REGION"
echo "Zone:          $ZONE"
echo "Instance Type: $INSTANCE_TYPE"
echo "SSH Key:       $SSH_KEY_NAME"
echo "Admin IP:      $ADMIN_IP"
echo "Domain:        ${DOMAIN:-'Not set'}"
echo "Disk:          ${SYSTEM_DISK_SIZE}GB ${SYSTEM_DISK_CATEGORY}"
echo ""
read -p "Proceed? (y/N) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Aborted."
    exit 0
fi

# ── Step 1: VPC ──────────────────────────────────────────────
echo ""
echo "── Step 1: VPC ─────────────────────────────────────────────"

VPC_ID=$(aliyun ecs DescribeVpcs \
    --RegionId "$REGION" \
    --VpcName "${INSTANCE_NAME}-vpc" \
    --output cols=VpcId rows=Vpcs.Vpc[] 2>/dev/null || true)

if [[ -z "$VPC_ID" ]]; then
    echo "Creating VPC: ${INSTANCE_NAME}-vpc"
    VPC_RESULT=$(aliyun vpc CreateVpc \
        --RegionId "$REGION" \
        --VpcName "${INSTANCE_NAME}-vpc" \
        --CidrBlock "$VPC_CIDR" \
        --output json)
    VPC_ID=$(echo "$VPC_RESULT" | jq -r '.VpcId')
    echo "✅ VPC created: $VPC_ID"
else
    echo "✅ VPC exists: $VPC_ID"
fi

# ── Step 2: vSwitch ──────────────────────────────────────────
echo ""
echo "── Step 2: vSwitch ───────────────────────────────────────────"

VSWITCH_ID=$(aliyun vpc DescribeVSwitches \
    --RegionId "$REGION" \
    --VpcId "$VPC_ID" \
    --ZoneId "$ZONE" \
    --output cols=VSwitchId rows=VSwitches.VSwitch[] 2>/dev/null || true)

if [[ -z "$VSWITCH_ID" ]]; then
    echo "Creating vSwitch in $ZONE"
    VSWITCH_RESULT=$(aliyun vpc CreateVSwitch \
        --RegionId "$REGION" \
        --VpcId "$VPC_ID" \
        --ZoneId "$ZONE" \
        --CidrBlock "$VSWITCH_CIDR" \
        --VSwitchName "${INSTANCE_NAME}-vswitch" \
        --output json)
    VSWITCH_ID=$(echo "$VSWITCH_RESULT" | jq -r '.VSwitchId')
    echo "✅ vSwitch created: $VSWITCH_ID"
else
    echo "✅ vSwitch exists: $VSWITCH_ID"
fi

# ── Step 3: Security Group ──────────────────────────────────
echo ""
echo "── Step 3: Security Group ─────────────────────────────────────"

SG_ID=$(aliyun ecs DescribeSecurityGroups \
    --RegionId "$REGION" \
    --VpcId "$VPC_ID" \
    --SecurityGroupName "${INSTANCE_NAME}-sg" \
    --output cols=SecurityGroupId rows=SecurityGroups.SecurityGroup[] 2>/dev/null || true)

if [[ -z "$SG_ID" ]]; then
    echo "Creating security group"
    SG_RESULT=$(aliyun ecs CreateSecurityGroup \
        --RegionId "$REGION" \
        --VpcId "$VPC_ID" \
        --SecurityGroupName "${INSTANCE_NAME}-sg" \
        --Description "JA4proxy Research Honeypot" \
        --output json)
    SG_ID=$(echo "$SG_RESULT" | jq -r '.SecurityGroupId')
    echo "✅ Security group created: $SG_ID"

    # Allow SSH from admin IP
    aliyun ecs AuthorizeSecurityGroup \
        --RegionId "$REGION" \
        --SecurityGroupId "$SG_ID" \
        --IpProtocol tcp \
        --PortRange 22/22 \
        --SourceCidrIp "${ADMIN_IP}/32" \
        --Description "SSH from admin" \
        --Policy Accept 2>/dev/null || true

    # Allow HTTP from anywhere (Caddy ACME)
    aliyun ecs AuthorizeSecurityGroup \
        --RegionId "$REGION" \
        --SecurityGroupId "$SG_ID" \
        --IpProtocol tcp \
        --PortRange 80/80 \
        --SourceCidrIp "0.0.0.0/0" \
        --Description "HTTP for ACME" \
        --Policy Accept 2>/dev/null || true

    # Allow HTTPS from anywhere (HAProxy)
    aliyun ecs AuthorizeSecurityGroup \
        --RegionId "$REGION" \
        --SecurityGroupId "$SG_ID" \
        --IpProtocol tcp \
        --PortRange 443/443 \
        --SourceCidrIp "0.0.0.0/0" \
        --Description "HTTPS for HAProxy" \
        --Policy Accept 2>/dev/null || true

    echo "✅ Security group rules added (SSH from admin, HTTP/HTTPS public)"
else
    echo "✅ Security group exists: $SG_ID"
fi

# ── Step 4: Find Image ──────────────────────────────────────
echo ""
echo "── Step 4: Ubuntu 22.04 Image ────────────────────────────────────"

IMAGE_ID=$(aliyun ecs DescribeImages \
    --RegionId "$REGION" \
    --ImageName "ubuntu_22_04*" \
    --ImageOwnerAlias system \
    --PageSize 1 \
    --output cols=ImageId rows=Images.Image[] 2>/dev/null | head -1 || true)

if [[ -z "$IMAGE_ID" ]]; then
    echo "⚠️  Could not auto-detect Ubuntu 22.04 image. Using fallback."
    IMAGE_ID="ubuntu_22_04_x64_20G_alibase_20240101.vhd"
fi
echo "✅ Using image: $IMAGE_ID"

# ── Step 5: Create ECS Instance ─────────────────────────────
echo ""
echo "── Step 5: ECS Instance ─────────────────────────────────────────"

echo "Creating instance: $INSTANCE_NAME"
INSTANCE_RESULT=$(aliyun ecs CreateInstance \
    --RegionId "$REGION" \
    --ZoneId "$ZONE" \
    --InstanceType "$INSTANCE_TYPE" \
    --SecurityGroupId "$SG_ID" \
    --VSwitchId "$VSWITCH_ID" \
    --ImageId "$IMAGE_ID" \
    --InstanceName "$INSTANCE_NAME" \
    --InternetMaxBandwidthOut 0 \
    --SystemDiskCategory "$SYSTEM_DISK_CATEGORY" \
    --SystemDiskSize "$SYSTEM_DISK_SIZE" \
    --KeyPairName "$SSH_KEY_NAME" \
    --IoOptimized optimized \
    --output json)

INSTANCE_ID=$(echo "$INSTANCE_RESULT" | jq -r '.InstanceId')
echo "✅ Instance created: $INSTANCE_ID"

# ── Step 6: Start Instance ──────────────────────────────────
echo ""
echo "── Step 6: Starting Instance ────────────────────────────────────"

echo "Starting instance..."
aliyun ecs StartInstance --InstanceId "$INSTANCE_ID" 2>/dev/null || true

# Wait for instance to be running
echo "Waiting for instance to start (up to 120s)..."
for _ in $(seq 1 24); do
    STATUS=$(aliyun ecs DescribeInstanceStatus \
        --RegionId "$REGION" \
        --output cols=Status rows=InstanceStatuses.InstanceStatus[] 2>/dev/null | head -1 || true)
    if [[ "$STATUS" == "Running" ]]; then
        echo "✅ Instance is running"
        break
    fi
    sleep 5
done

# ── Step 7: Allocate and Attach EIP ─────────────────────────
echo ""
echo "── Step 7: Elastic IP ─────────────────────────────────────────"

echo "Allocating EIP..."
EIP_RESULT=$(aliyun vpc AllocateEipAddress \
    --RegionId "$REGION" \
    --Bandwidth 5 \
    --InternetChargeType PayByTraffic \
    --output json)
EIP_ID=$(echo "$EIP_RESULT" | jq -r '.AllocationId')
EIP_ADDRESS=$(echo "$EIP_RESULT" | jq -r '.EipAddress')
echo "✅ EIP allocated: $EIP_ADDRESS (ID: $EIP_ID)"

echo "Attaching EIP to instance..."
aliyun vpc AssociateEipAddress \
    --RegionId "$REGION" \
    --AllocationId "$EIP_ID" \
    --InstanceId "$INSTANCE_ID" \
    --InstanceType EcsInstance 2>/dev/null || true
echo "✅ EIP attached"

# ── Step 8: DNS (optional) ──────────────────────────────────
if [[ -n "$DOMAIN" ]]; then
    echo ""
    echo "── Step 8: DNS Record ─────────────────────────────────────────"
    echo "ℹ️  Create DNS A record manually:"
    echo "    ${DOMAIN} → ${EIP_ADDRESS}"
    echo "    Or use: aliyun alidns AddDomainRecord --DomainName ..."
    echo ""
fi

# ── Step 9: Output ──────────────────────────────────────────
echo ""
echo "╔══════════════════════════════════════════════════════╗"
echo "║              PROVISIONING COMPLETE                     ║"
echo "╚══════════════════════════════════════════════════════╝"
echo ""
echo "Instance ID:   $INSTANCE_ID"
echo "Public IP:     $EIP_ADDRESS"
echo "Region:        $REGION"
echo "Zone:          $ZONE"
echo "Instance Type: $INSTANCE_TYPE"
echo "SSH Key:       $SSH_KEY_NAME"
echo "Admin IP:      $ADMIN_IP"
echo ""
echo "Next steps:"
echo "  1. Wait 2-3 minutes for cloud-init to finish"
echo "  2. Test SSH: ssh -i ~/.ssh/<key> root@${EIP_ADDRESS}"
echo "  3. Run Ansible:"
echo "     cd JA4proxy-testing"
echo "     make deploy"
echo ""
echo "  Or directly:"
echo "     ansible-playbook -i '${EIP_ADDRESS},' deploy/playbooks/site.yml \\"
echo "       -e 'ja4proxy_ssh_user=root ja4proxy_admin_ip=${ADMIN_IP}' \\"
echo "       -e 'ja4proxy_build_machine_go_path=/path/to/JA4proxy'"
echo ""

# Save connection details for Ansible. Key path is resolved at play time
# by site.yml (JA4PROXY_SSH_PRIVATE_KEY env → id_ed25519 → id_rsa), so we
# don't bake a specific key into the inventory file.
cat > deploy/inventory/hosts.ini << EOF
# Auto-generated by provision-alibaba-cloud.sh
[ja4proxy_vm]
${EIP_ADDRESS} ansible_user=root ansible_python_interpreter=/usr/bin/python3
EOF

echo "✅ Inventory updated: deploy/inventory/hosts.ini"

# Pre-pin the VM's SSH host key into ~/.ssh/known_hosts so Ansible's
# StrictHostKeyChecking=accept-new records the real key on first run
# rather than a MITM'd replacement. We poll because cloud-init may still
# be bringing sshd up.
echo ""
echo "Pinning SSH host key..."
mkdir -p "$HOME/.ssh"
touch "$HOME/.ssh/known_hosts"
chmod 600 "$HOME/.ssh/known_hosts"

# Remove any stale entry (e.g. a previous VM that reused the same EIP).
ssh-keygen -R "$EIP_ADDRESS" >/dev/null 2>&1 || true

for _ in $(seq 1 30); do
    if ssh-keyscan -T 5 -t ed25519,rsa "$EIP_ADDRESS" 2>/dev/null \
        | tee -a "$HOME/.ssh/known_hosts" \
        | grep -q "^$EIP_ADDRESS "; then
        echo "✅ Host key pinned for $EIP_ADDRESS"
        break
    fi
    sleep 2
done
