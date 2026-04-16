# Outbound reporting — decision tree for LE referrals

Last reviewed: 2026-04-16

Decision tree for when the operator observes something in the
honeypot data that may warrant a report to law enforcement or a
third-party CERT.

## Decision tree

```
Observation in honeypot data
│
├── Known scanner / research traffic (e.g. Censys, Shodan, university)
│   └── No action. Expected traffic; do not report.
│
├── Commodity bot / exploit attempt
│   ├── Already catalogued by public threat feeds?
│   │   └── No action. Research value only.
│   └── Novel / zero-day indicator?
│       ├── Affects a widely deployed product?
│       │   └── Report to vendor PSIRT + relevant national CERT.
│       └── Narrow / obscure target?
│           └── Log for dataset; report only if impact is clear.
│
├── Targeted attack pattern against a specific third party
│   └── Report to the target's published abuse contact or CERT.
│       Do NOT contact the attacker's ISP without legal advice.
│
└── Evidence of compromise of OUR honeypot (unexpected outbound, etc.)
    └── Follow RUNBOOK.md scenario 6 (VM compromise).
        If data was exfiltrated, follow LE_REQUESTS.md §5
        (transparency) and consider self-reporting to the
        supervisory authority under GDPR Art. 33.
```

## Reporting channels

| Recipient | Channel | SLA |
|-----------|---------|-----|
| Vendor PSIRT | Vendor's published security@ or HackerOne | Best-effort; follow responsible disclosure timelines |
| National CERT (e.g. CERT-EU, US-CERT) | Web form or encrypted email | Within 72h of confirming a reportable indicator |
| Third-party abuse contact | abuse@ from WHOIS or security.txt | Informational; no SLA obligation |
| Own supervisory authority (GDPR breach) | Authority's online form | 72h from awareness (Art. 33) |

## What NOT to include in reports

- Raw IP addresses from the honeypot dataset without HMAC
  anonymisation (12-B) unless the report explicitly requires
  attribution.
- Internal infrastructure details (VM IP, admin IP, Grafana URLs).
- Speculative attribution ("we think this is APT-XX") — report
  observables, not conclusions.

## Changes since last review

_<Dated list.>_
