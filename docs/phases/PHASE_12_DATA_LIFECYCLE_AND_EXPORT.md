# Phase 12: Data Lifecycle and Research Export

## Purpose

The research value of this project is the **data it emits**. Today, data accumulates on the VM in Prometheus, Loki, journald, and Redis. We need to:
- enforce retention (90 days);
- extract data for research;
- anonymize IPs with a stable but secret salt;
- produce a signed, durable artefact.

## Deliverables

### 1. Retention enforcement

**journald**: Deploy `/etc/systemd/journald.conf` with `MaxRetentionSec=90d` and `SystemMaxUse=2G`.
**Loki**: Enable `retention_deletes_enabled` and `retention_period: 2160h`.
**Prometheus**: Set `--storage.tsdb.retention.time=90d`.

### 2. Export pipeline (weekly)

1. **VM Side**: A systemd timer triggers `export-week.sh`.
   - Snapshot Prometheus (`/api/v1/admin/tsdb/snapshot`).
   - Extract Loki logs (`logcli query`).
   - Package into a `research-bundle-<YYYY-WW>.tar.gz`.
2. **Control Side**: `make export-pull` pulls the bundle.
   - **Transformation**: Convert raw JSONL/CSV to Parquet for long-term analysis.
   - **Anonymization**: Apply `anonymise.py` using a stable `ja4proxy_hmac_salt` from `.vault/secrets.yml`.
   - **Integrity**: Sign the manifest with `cosign sign-blob`.

### 3. Stable Anonymization
Instead of throwing away the salt, we store it in the vault. This allows us to correlate the same anonymous identifier for a single IP across multiple weekly exports, which is critical for identifying "returning attackers" while still protecting the raw PII.

### 4. Manifest Signing
The weekly export manifest will be signed using the same `cosign` infrastructure as the binary. This ensures that the research data hasn't been tampered with between the VM and the researcher's workstation.

## Acceptance criteria

```
[ ] /etc/systemd/journald.conf contains MaxRetentionSec=90d
[ ] ja4proxy_hmac_salt exists in deploy/.vault/secrets.yml
[ ] make export-pull produces a signed manifest.yml
[ ] anonymise.py preserves cross-week correlation for the same IP
```
