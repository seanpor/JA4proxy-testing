# Data anonymisation

Last reviewed: 2026-04-16

Documents the anonymisation method applied before any honeypot data
is shared outside the VM.

## Method

HMAC-SHA-256 keyed by a per-run salt, truncated to 16 hex characters.
The salt is generated fresh for each export and is **not** stored
with the anonymised output — this makes re-identification from the
output alone computationally infeasible.

| Data type | Transformation |
|-----------|---------------|
| IPv4 address | `HMAC-SHA-256(salt, ip)[:16]` |
| IPv6 address | `HMAC-SHA-256(salt, /64 prefix)[:16]` — host part discarded |
| Email addresses | Line dropped entirely |
| Phone numbers | Line dropped entirely |
| Binary files (.gz, .tar, .db, .wal) | Copied without scrubbing |
| Everything else | Passed through unchanged |

## Why HMAC, not hash?

A plain SHA-256 of an IPv4 address is trivially reversible via a
lookup table (2^32 entries). HMAC with a per-run salt makes
precomputation infeasible. Truncation to 16 hex chars (64 bits)
is sufficient for collision resistance within a single export.

## Why /64 for IPv6?

The /64 prefix identifies the network; the host part identifies the
device. Hashing on the /64 means two devices on the same network get
the same anonymised identifier — appropriate for traffic analysis
without device-level tracking.

## Limitations

- Anonymisation does not cover data already in Prometheus TSDB
  snapshots (binary format). If the snapshot contains IP labels, they
  survive. Future work: scrub label values in the snapshot or exclude
  IP-containing series.
- The PII regex is heuristic. Non-standard email or phone formats
  may survive.
- ASN numbers and geolocation data are preserved — these are
  aggregate identifiers, not personal data, but could narrow
  re-identification if combined with timing.

## Tool

`deploy/scripts/anonymise.py` — runs on the control machine after
`make export-pull`. Usage:

```
python3 deploy/scripts/anonymise.py exports/<dir> exports/<dir>-anon --salt "$(openssl rand -hex 16)"
```

Tests: `python3 deploy/scripts/test_anonymise.py`

## Changes since last review

_<Dated list.>_
