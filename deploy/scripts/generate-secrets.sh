#!/usr/bin/env bash
# deploy/scripts/generate-secrets.sh
#
# Generates all deployment secrets into deploy/.vault/secrets.yml
# Safe to re-run — will NOT overwrite existing values.
#
# Usage: bash deploy/scripts/generate-secrets.sh

set -euo pipefail

# Canonical location — must match the path loaded by deploy/playbooks/site.yml
# (include_vars: "{{ playbook_dir }}/../.vault/secrets.yml"), i.e. deploy/.vault/.
VAULT_DIR="$(cd "$(dirname "$0")/.." && pwd)/.vault"
SECRETS_FILE="$VAULT_DIR/secrets.yml"

mkdir -p "$VAULT_DIR"

# Helper: generate a secret only if the key doesn't already exist in the file
generate_if_missing() {
    local key="$1"
    local value
    value=$(openssl rand -base64 32 | tr -d '=' | head -c 40)

    if [ -f "$SECRETS_FILE" ] && grep -q "^${key}:" "$SECRETS_FILE" 2>/dev/null; then
        echo "  [skip] ${key} — already exists"
    else
        echo "${key}: '${value}'" >> "$SECRETS_FILE"
        echo "  [gen]  ${key}"
    fi
}

echo "=== JA4proxy Secret Generation ==="
echo ""

if [ -f "$SECRETS_FILE" ]; then
    echo "Secrets file exists at: $SECRETS_FILE"
else
    echo "# JA4proxy Research — Auto-generated Secrets" > "$SECRETS_FILE"
    echo "# Generated: $(date -u +%Y-%m-%dT%H:%M:%SZ)" >> "$SECRETS_FILE"
    echo "" >> "$SECRETS_FILE"
    echo "Created new secrets file at: $SECRETS_FILE"
fi

generate_if_missing "redis_password"
generate_if_missing "grafana_admin_password"
generate_if_missing "grafana_password"
generate_if_missing "redis_signing_key"
generate_if_missing "haproxy_stats_password"
generate_if_missing "haproxy_stats_user"

# Generate a default haproxy stats user if not set
if [ -f "$SECRETS_FILE" ] && ! grep -q "^haproxy_stats_user:" "$SECRETS_FILE" 2>/dev/null; then
    # Use a fixed default username (the password is random)
    echo "haproxy_stats_user: 'haproxy-admin'" >> "$SECRETS_FILE"
    echo "  [gen]  haproxy_stats_user"
fi

echo ""
echo "Done. Review: $SECRETS_FILE"
echo "⚠️  This file is gitignored — do NOT commit it."
