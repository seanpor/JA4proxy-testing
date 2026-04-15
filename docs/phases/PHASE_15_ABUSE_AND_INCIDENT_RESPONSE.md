# Phase 15: Abuse Response and Incident Response

## Purpose

A public honeypot **will** generate abuse correspondence and at least occasional incidents. Today this project has a rollback runbook (`RUNBOOK.md`, 102 lines, scenarios 1–4) but no plan for:

- inbound abuse reports from third parties;
- outbound complaints from ISPs whose customers hit the honeypot;
- credible evidence of active criminal activity observed in the data;
- compromise of the honeypot itself (the VM is deliberately exposed and lightly hardened — a successful compromise is not hypothetical).

This phase fills those gaps. It is a documentation phase; the only code it adds is evidence-preservation tooling.

## Deliverables

### 15.1 Abuse queue

- `abuse@<ja4proxy_domain>` delivers to a real inbox the operator reads at least weekly.
- Canned reply template at `docs/governance/abuse-reply-template.md` explaining: this is a research honeypot, no traffic is relayed onward, the source IP being complained about is almost certainly an attacker hitting *our* box rather than a victim of anything *we* did.
- Log every inbound abuse report at `docs/governance/abuse-log/<YYYY-MM-DD>-<ticket>.md` with: timestamp, reporting party, subject IP/traffic, our response, any action taken. Do not delete this log — it is both an audit trail and a research data point about how internet abuse pipelines perceive our box.

### 15.2 Outbound complaints

If the data shows confirmed criminal activity (credential stuffing against a third party, CSAM-related URLs, active ransomware C2 signatures):

- Document the decision tree in `docs/governance/OUTBOUND_REPORTING.md`:
  - What we report, to whom, when.
  - What we never report (anything where the "crime" is the attacker probing *us* — that's the research target, not a criminal matter).
  - The research-ethics implication of reporting: once we start forwarding data to law enforcement, our "passive observer" posture is gone. Think before doing.

### 15.3 Evidence preservation (automated)

A script `deploy/scripts/preserve-evidence.sh` on the VM that, on invocation:

1. Creates `/var/ja4proxy/evidence/<UTC-timestamp>/`.
2. Dumps:
   - `journalctl --since=-24h --output=export > journald.export`
   - Prometheus TSDB snapshot via admin API.
   - `docker compose logs --tail=10000 --no-color > docker-compose.log`
   - `iptables-save`, `ss -tnp`, `ps auxf`, `ls -la /proc/*/exe`.
   - `/opt/ja4proxy/config/` tarball.
   - The VM's current image digests (`docker images --digests`).
3. Tars + sha256sums the whole directory and prints the hash.
4. Exits with the instruction "rsync this directory to the control machine now; do not reboot the VM".

Make it invokable from the runbook's scenario 4 (VM compromise) and before any deliberate teardown.

### 15.4 Incident-response playbooks

Add to `RUNBOOK.md` (or a sibling `INCIDENT_RESPONSE.md`) these scenarios, each with a preconditions list, a numbered procedure, and a rollback:

1. **SSH lockout** (UFW rule committed that excludes the admin IP).
   - Recovery via cloud provider's VNC / serial console; documented commands to re-open UFW 22.
2. **Caddy ACME rate-limited.**
   - Symptoms (self-signed served, `docker compose logs caddy | grep "urn:ietf:params:acme"`).
   - Fall back to staging; wait out the rate-limit window; re-issue.
3. **Redis ban-list corruption / runaway growth.**
   - Dump, inspect, flush if needed; document expected cardinality bounds.
4. **Disk full.**
   - Which volumes to truncate (journald, Loki, Prometheus WAL) and in what order.
5. **Grafana admin-password forgotten.**
   - `grafana-cli admin reset-admin-password` inside the container.
6. **Compromise of the VM** (indicators: AIDE alarms, unexpected outbound connections, unknown binary in `/tmp`).
   - Step 1: run `preserve-evidence.sh`.
   - Step 2: close UFW 80/443 (kill switch).
   - Step 3: snapshot the disk via Alibaba console before any destructive action.
   - Step 4: pull the tarball to the control machine.
   - Step 5: destroy the VM.
   - Step 6: do **not** provision a replacement onto the same IP within 30 days; attackers who found us will keep trying the IP.
7. **Law-enforcement request received.**
   - Follow `docs/governance/LE_REQUESTS.md`.
   - Preserve evidence; do not reply substantively without legal review.
8. **Mis-configured DNS causes go-live to open UFW before Caddy has a valid cert.**
   - Close UFW 80/443 immediately, fix DNS, re-run `make go-live`.

### 15.5 On-call posture

This is a personal research project without a rotation. Document that explicitly:

- Target response time for abuse email: 3 business days.
- Target response time for a down alert (dead-man's switch silent): 24 h.
- During documented away periods (vacation, conferences), `make go-dark` before leaving, `make go-live` on return.

The worst posture is *implying* 24/7 coverage and not providing it. State the truth.

### 15.6 Stakeholder notification list

Who needs to be told when something bad happens to this box?

- Operator's own email.
- Any collaborating researcher (named in `docs/governance/ETHICS.md`).
- The domain registrar's abuse desk, if the domain is hijacked.
- The cloud provider's security team, if the VM is suspected compromised and we want their side's logs.

Keep it in `docs/governance/STAKEHOLDERS.yml`; reference it from the runbook.

## Acceptance criteria

```
[ ] abuse@<domain> delivers somewhere the operator reads
[ ] preserve-evidence.sh exists on the VM and produces a tarball of > 0 bytes
[ ] RUNBOOK.md covers the eight scenarios above, each with a numbered procedure
[ ] docs/governance/{abuse-reply-template.md, OUTBOUND_REPORTING.md, LE_REQUESTS.md, STAKEHOLDERS.yml} exist
[ ] The on-call posture is stated in README.md (§Operations) and in the honeypot-notice page
```

## Related

- `docs/phases/CRITICAL_REVIEW.md` §C2
- `docs/phases/PHASE_11_LEGAL_ETHICS_AND_HONEYPOT_DISCLOSURE.md` (abuse contact wiring)
- `docs/phases/RUNBOOK.md` (to be expanded with the eight scenarios)
