# Data retention

Last reviewed: 2026-04-15

Retention values, the data category they bound, and the concrete
enforcement mechanism. If you change a number here, change the
matching variable in `deploy/inventory/group_vars/all.yml` and the
statement on `/privacy.html` in the same PR — otherwise the
published retention claim drifts away from enforcement.

## Retention table

| Data category | Retention | Enforcement mechanism | Source of truth |
|---------------|-----------|----------------------|-----------------|
| journald (system + unit logs) | 90 days | `SystemMaxFiles` + time cap in `journald.conf.j2` | `ja4proxy_journald_max_retention` (group_vars/all.yml:104) |
| Loki log store | 90 days | `table_manager` retention in `loki.yml.j2` | `ja4proxy_loki_retention_days` (group_vars/all.yml:115) |
| Prometheus TSDB | 90 days or 10 GB, whichever first | `--storage.tsdb.retention.time` + `retention.size` | `ja4proxy_prometheus_retention_days` / `_size` (group_vars/all.yml:123-124) |
| JA4proxy fingerprint logs | 90 days (aligned with above) | journald rotation on the host unit | journald config |
| HAProxy access logs | 90 days | journald rotation | journald config |
| Evidence tarballs (incident) | Manual — operator decides | `preserve-evidence.sh` writes mode-0600 tarballs; operator deletes | `deploy/scripts/preserve-evidence.sh` |
| Honeypot form submissions | **Never persisted** | Caddy serves static HTML; no backend accepts POST bodies | Caddy config + `/privacy.html` claim |

## Enforcement checks

- `scripts/ci/check_loki_retention.py` — Loki config carries a retention block.
- `scripts/ci/check_prometheus_retention.py` — Prometheus runs with both time + size flags.
- `scripts/ci/check_journald_template.py` — journald config ships the retention cap.
- `scripts/ci/check_privacy_page.py` — privacy page is rendered and deployed.

Together these ensure that if the value drifts here without matching
code changes, CI fails before merge.

## Anonymisation

Chunk 12-B (pending) will HMAC source IPs before any dataset is
shared outside the VM. Until 12-B lands, raw IPs exist only in
journald / Loki with the retention caps above, and the dataset never
leaves the VM except via operator-initiated `scp`.

## Changes since last review

_<Dated list of retention changes. Each change must reference the PR
that updated the matching group_vars value.>_
