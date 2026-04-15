# Lawful basis — Article 6(1)(f) balancing test

Last reviewed: 2026-04-15

This file documents the lawful basis under GDPR Article 6(1)(f)
(legitimate interests) for processing the personal data the honeypot
collects. The operator is responsible for the wording below. CI only
enforces that the file exists and is reviewed annually.

## 1. Processing summary

- **Controller:** _<operator name / role>_
- **Purpose:** Collect TLS client fingerprints (JA4) from traffic
  arriving at a public honeypot to study bot / scanner populations.
- **Data categories:** source IP address, TLS ClientHello fields,
  HTTP request metadata, coarse geolocation derived from IP, timing.
- **Retention:** see `RETENTION.md`.
- **Recipients:** none outside the operator unless a law-enforcement
  request is granted (see `LE_REQUESTS.md`).

## 2. Three-part test

### 2.1 Purpose test — is the interest legitimate?

_<Why does this research exist? What's the concrete output — a paper,
a dataset, a tool improvement? Is the interest specific enough that
an informed data subject would recognise it as a real purpose?>_

### 2.2 Necessity test — is processing necessary?

_<Could the research question be answered without personal data? If
partial anonymisation would work, why is raw IP retained during the
live window? Reference `RETENTION.md` enforcement mechanisms.>_

### 2.3 Balancing test — rights and freedoms of the data subject

_<What are the reasonable expectations of someone whose scanner hit
this host? What is the impact if their IP appears in the dataset?
What mitigations reduce that impact (HMAC anonymisation, retention
caps, no publication of raw IPs)?>_

## 3. Decision

_<Conclusion: lawful basis is / is not Article 6(1)(f). If not, fall
back to another basis or stop processing.>_

## 4. Changes since last review

_<Dated list of changes. Any change to collected fields, retention,
or sharing scope invalidates the last balancing test and requires a
new review.>_
