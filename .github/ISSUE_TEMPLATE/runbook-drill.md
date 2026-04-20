---
name: Runbook drill (semi-annual)
about: Walk through the 8 Incident Response scenarios on a disposable VM
title: "Runbook drill — YYYY-HH (H1 or H2)"
labels: ["drill", "runbook"]
assignees: []
---

<!--
Semi-annual drill of the 8 Incident Response scenarios documented in
docs/phases/RUNBOOK.md § Incident Response Scenarios. See the "Drill
cadence" section of the same file for the why and the logging
expectations.

Cadence: ~April (H1) and ~October (H2). Open this issue, spin up a
disposable VM (`make cloud ALIYUN_ARGS='...'`), walk through each
scenario below, tick the box when procedure + rollback both ran
clean, leave notes on anything that drifted from the runbook. Tear
the VM down with `make destroy VM_IP=<ip>` when done.
-->

## VM under test

- VM IP:
- Deployed commit SHA:
- Drill started (UTC):

## Scenarios

Tick only when both the procedure *and* the rollback ran clean on
this VM. If anything is off, note it below the box and open a PR
fixing the runbook as part of closing this issue.

- [ ] **1. SSH lockout** — procedure + rollback from RUNBOOK.md §
      Incident Response Scenarios § 1.
- [ ] **2. Caddy ACME rate-limit** — procedure + rollback.
- [ ] **3. Redis corruption** — procedure + rollback.
- [ ] **4. Disk full** — procedure + rollback.
- [ ] **5. Grafana password reset** — procedure + rollback.
- [ ] **6. VM compromise** — procedure + rollback. Must include a
      successful `preserve-evidence.sh` run.
- [ ] **7. Law-enforcement request** — paper walkthrough of
      `docs/governance/LE_REQUESTS.md`; no VM changes.
- [ ] **8. DNS misconfig opened UFW to the wrong host** — procedure
      + rollback.

## Findings

<!--
For each scenario that failed, drifted, or was ambiguous, write:
- what happened
- what the runbook said to do
- what actually worked
- the PR or commit that fixes it
-->

## Drill closed

- Drill finished (UTC):
- VM destroyed: [ ]
- Follow-up PR(s):
