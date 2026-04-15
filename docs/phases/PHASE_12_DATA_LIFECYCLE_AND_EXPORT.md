# Phase 12: Data Lifecycle and Research Export

## Purpose

The research value of this project is the **data it emits**, not the proxy itself. Today, data accumulates on the VM in Prometheus (metrics), Loki (logs), journald (raw logs), and Redis (short-lived ban state). Nothing:

- enforces the stated 90-day retention;
- extracts data for research use;
- anonymises IPs before sharing;
- produces a durable artefact independent of the VM's disk.

Any serious research output needs all four.

## Deliverables

### 1. Retention enforcement (deploy)

**journald**: currently only a group_vars knob (`ja4proxy_journald_max_retention: 90d`) with no `/etc/systemd/journald.conf` rendering. Add:

```yaml
- name: Deploy journald config
  ansible.builtin.template:
    src: journald.conf.j2
    dest: /etc/systemd/journald.conf
    mode: "0644"
  notify: Restart systemd-journald
```

where the template sets `Storage=persistent`, `MaxRetentionSec={{ ja4proxy_journald_max_retention }}`, `SystemMaxUse=2G`, `Compress=yes`, `ForwardToSyslog=no`.

**Loki**: add `table_manager.retention_deletes_enabled: true` and `retention_period: 2160h` (90d) to the Loki config template. Verify with `curl -s http://127.0.0.1:3100/loki/api/v1/status/buildinfo` and a Prometheus query on `loki_ingester_chunks_stored_total`.

**Prometheus**: add `--storage.tsdb.retention.time=90d` and `--storage.tsdb.retention.size=5GB` to the Prometheus container command in docker-compose, whichever trips first.

**Redis**: ban TTLs are already set (`ban_duration: 300` in proxy.yml). Add a Prometheus alert if `redis_keyspace_keys{db="db0"}` is growing unboundedly (see PHASE_13).

### 2. Export pipeline (weekly cron)

A scheduled job on the VM that produces a portable research artefact:

```
/opt/ja4proxy-export/
├── <YYYY-WW>/
│   ├── prometheus.snapshot.tar.gz        # via /api/v1/admin/tsdb/snapshot
│   ├── loki-logs.ndjson.gz               # logcli query with time range
│   ├── fingerprints.parquet              # derived: distinct (ja4, ja4x, ja4t) seen
│   └── manifest.yml                      # period, checksums, row counts, binary version
```

Ansible additions:

1. New role `deploy/roles/11-data-export/` (or tasks file under `06-operational-security`).
2. Template a systemd timer `ja4proxy-export.timer` (weekly) and unit `ja4proxy-export.service` invoking a new `deploy/scripts/export-week.sh`.
3. The script calls:
   - `curl -XPOST http://127.0.0.1:9091/api/v1/admin/tsdb/snapshot` (Prometheus admin API must be enabled via `--web.enable-admin-api`; accept the risk because the port is loopback-only).
   - `logcli query '{job="ja4proxy"}' --since=168h --output=jsonl`.
   - A short Python/awk transform to produce `fingerprints.parquet` (or `.csv.gz` if we want no Python dependency).
   - Write `manifest.yml` with SHA-256 of each artefact.
4. Rsync pull from control machine via `make export-pull VM_IP=…` (do not push to an external bucket from the VM; researcher-initiated pull keeps the sensitive-egress surface small).

### 3. Anonymisation before sharing

Any dataset leaving the operator's control must pass a scrub. Provide a reusable filter at `deploy/scripts/anonymise.py` (runs on the control machine, not the VM):

- IPv4: keep ASN + country, replace the IP with HMAC-SHA-256 using a per-dataset salt (the salt is thrown away after the run, giving k-anonymity ≥ k-size of the ASN bucket).
- IPv6: same, on the /64.
- User-Agent: keep; they are not PII in this context.
- Anything that looks like an email, phone, or bearer token in honeypot form submissions: drop the entire row. Form submissions are meant to be fake but that has never stopped anyone.

Document in `docs/governance/ANONYMISATION.md` the exact scrub applied per publication, because reviewers will ask.

### 4. Research binary pinning

Each exported artefact must record the JA4proxy commit hash and binary sha256 that produced it. Reproducibility for a 12-month research project is impossible if we can't say *which binary* emitted a given fingerprint. Add to the build step:

```yaml
- name: Record binary provenance
  ansible.builtin.copy:
    content: |
      commit: {{ lookup('pipe', 'git -C ' ~ ja4proxy_build_machine_go_path ~ ' rev-parse HEAD') }}
      sha256: {{ binary_checksum.stdout.split()[0] }}
      built_at: {{ ansible_date_time.iso8601 }}
      goflags: "-trimpath -buildvcs=true"
    dest: /opt/ja4proxy/config/binary-provenance.yml
```

Propagate `binary-provenance.yml` into the export `manifest.yml`.

### 5. Long-term archive

After the weekly pull to the control machine, the operator's existing backup strategy takes over (Borg/restic/Time Machine/whatever). Document in `docs/governance/RETENTION.md` that:

- raw logs are destroyed on the VM at 90 days;
- the weekly export is kept for the life of the research project + 12 months;
- anonymised derivatives (published datasets) are kept indefinitely.

## Acceptance criteria

```
[ ] /etc/systemd/journald.conf on the VM contains MaxRetentionSec={{ retention }}
[ ] Prometheus snapshots via admin API succeed
[ ] Loki retention kicks in on chunks older than retention_period (verify with a synthetic old log)
[ ] systemctl list-timers | grep ja4proxy-export shows a next-run time
[ ] A full `make export-pull` produces a manifest.yml with non-zero row counts and verified checksums
[ ] anonymise.py passes a unit test: known IPs are replaced, ASNs preserved, salt not persisted
```

## Related

- `docs/phases/CRITICAL_REVIEW.md` §C3
- `docs/phases/PHASE_05_DATA_COLLECTION.md` — the "what we collect" side; this phase covers the "how it leaves" side.
- `docs/phases/PHASE_11_LEGAL_ETHICS_AND_HONEYPOT_DISCLOSURE.md` §2 (retention statement must match what journald actually enforces)
