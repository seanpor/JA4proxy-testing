#!/usr/bin/env bash
# deploy/scripts/generate-secrets.sh
#
# Generates all deployment secrets into deploy/.vault/secrets.yml and
# encrypts the result at rest with ansible-vault.
#
# Safe to re-run: decrypts the existing file, generates only missing
# keys, re-encrypts.
#
# Vault password resolution order:
#   1. $ANSIBLE_VAULT_PASSWORD_FILE (if set and non-empty)
#   2. deploy/.vault/.vault-pass (auto-generated on first run if absent)

set -euo pipefail

VAULT_DIR="$(cd "$(dirname "$0")/.." && pwd)/.vault"
SECRETS_FILE="$VAULT_DIR/secrets.yml"
DEFAULT_PASS_FILE="$VAULT_DIR/.vault-pass"
PASS_FILE="${ANSIBLE_VAULT_PASSWORD_FILE:-$DEFAULT_PASS_FILE}"

mkdir -p "$VAULT_DIR"
chmod 700 "$VAULT_DIR"

if [ ! -s "$PASS_FILE" ]; then
    if [ "$PASS_FILE" != "$DEFAULT_PASS_FILE" ]; then
        echo "ERROR: vault password file not found: $PASS_FILE" >&2
        exit 1
    fi
    echo "Generating new vault password → $DEFAULT_PASS_FILE"
    umask 077
    openssl rand -base64 48 | tr -d '\n=' > "$DEFAULT_PASS_FILE"
    chmod 600 "$DEFAULT_PASS_FILE"
fi

is_encrypted() {
    [ -f "$SECRETS_FILE" ] && head -n1 "$SECRETS_FILE" | grep -q '^\$ANSIBLE_VAULT;'
}

WORK="$(mktemp)"
trap 'rm -f "$WORK"' EXIT

if is_encrypted; then
    ansible-vault decrypt --vault-password-file "$PASS_FILE" \
        --output "$WORK" "$SECRETS_FILE"
elif [ -f "$SECRETS_FILE" ]; then
    # Legacy plaintext file — carry contents forward, we re-encrypt below.
    cp "$SECRETS_FILE" "$WORK"
else
    {
        echo "# JA4proxy Research — Auto-generated Secrets"
        echo "# Generated: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
        echo ""
    } > "$WORK"
fi

generate_if_missing() {
    local key="$1"
    if grep -q "^${key}:" "$WORK" 2>/dev/null; then
        echo "  [skip] ${key} — already exists"
    else
        local value
        value=$(openssl rand -base64 32 | tr -d '=' | head -c 40)
        echo "${key}: '${value}'" >> "$WORK"
        echo "  [gen]  ${key}"
    fi
}

echo "=== JA4proxy Secret Generation ==="
echo ""

generate_if_missing "redis_password"
generate_if_missing "grafana_admin_password"
generate_if_missing "grafana_password"
generate_if_missing "redis_signing_key"
generate_if_missing "haproxy_stats_password"

if ! grep -q "^haproxy_stats_user:" "$WORK" 2>/dev/null; then
    echo "haproxy_stats_user: 'haproxy-admin'" >> "$WORK"
    echo "  [gen]  haproxy_stats_user"
fi

ansible-vault encrypt --vault-password-file "$PASS_FILE" \
    --output "$SECRETS_FILE" "$WORK" >/dev/null
chmod 600 "$SECRETS_FILE"

echo ""
echo "Done. Encrypted: $SECRETS_FILE"
echo "Vault password: $PASS_FILE (gitignored — back this up!)"
