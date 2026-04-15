# Phase 10: Go-Live (Public Exposure)

## Purpose

Transition the VM from **locked** (bound to 127.0.0.1, self-signed TLS, UFW closed on 80/443) to **live** (bound to 0.0.0.0, production Let's Encrypt TLS, UFW open on 80/443). This is the only phase that creates public exposure. It must be idempotent, must be gated behind an explicit confirmation flag, and must be reversible.

## Role

`deploy/roles/10-go-live/` — tagged `go-live` and `phase10`. Invoked as `make go-live VM_IP=<ip>`. The Makefile adds `-e ja4proxy_go_live_confirm=true` so the role is a no-op during a normal `make deploy`.

## Preconditions (assert before acting)

All of these must hold when the role enters. If any fails, fail loudly; do not half-open the firewall.

1. `ja4proxy_go_live_confirm` is literally the boolean `true`.
2. `ja4proxy_domain` resolves (via DNS, not via `/etc/hosts`) to the VM's public IP.
3. Port 80 and 443 are reachable from the internet to the VM (LE `HTTP-01` challenge will use 80). A curl from a third-party host is the ground truth; at minimum assert the cloud-provider security group allows 80 and 443.
4. `make verify VM_IP=<ip>` has been run in this deploy cycle — record a marker file on the VM (`/var/lib/ja4proxy/verified-ok`) and refuse go-live if it's older than 24 h or missing.
5. JA4proxy, HAProxy, Caddy, Redis, Prometheus, Grafana, Loki, Promtail are all `active (running)` / `healthy`.
6. `docker-compose.yml` contains only digest-pinned images (grep assertion from PHASE_09).
7. Caddy has a valid staging cert already (i.e. the ACME flow was exercised against `acme-staging-v02.api.letsencrypt.org` on a previous deploy). This bounds the blast radius of the LE rate-limit budget.
8. **DNS A-record preflight (13-G).** `dig +short A {{ ja4proxy_domain }}` on the control machine returns an answer containing `ja4proxy_vm_host`. Mismatch here would waste the Let's Encrypt HTTP-01 challenge and burn rate-limit budget for the domain. Override with `-e ja4proxy_skip_dns_preflight=true` only for split-horizon DNS or test setups.
9. **MX preflight (11-D).** `dig +short MX {{ ja4proxy_domain }}` on the control machine returns a non-empty answer. The disclosure page and `security.txt` advertise `abuse@` and `privacy@` on this domain; without an MX, complaints bounce silently and the honeypot looks malicious. Override with `-e ja4proxy_skip_mx_preflight=true` only if mail for the domain is handled outside DNS (e.g. a catch-all on a parent zone).

## Actions

1. **Rebind Docker ports.** Re-render `docker-compose.yml` with `0.0.0.0` for HAProxy 80/443 only. Grafana (3000), Prometheus (9091), Loki (3100) remain bound to `127.0.0.1` and remain accessible only via SSH tunnel.
2. **Switch Caddy to production ACME** in `Caddyfile`: remove the `acme_ca https://acme-staging-v02.api.letsencrypt.org/directory` directive, reload Caddy.
3. **Request the production cert** and wait up to 120 s for `/var/lib/caddy/.../<domain>/<domain>.crt` to exist and be not-before-now, not-after in future.
4. **Open UFW 80/tcp and 443/tcp** to `any`. Leave 22/tcp restricted to `ja4proxy_admin_ip`. `ufw reload`, assert the new rules are active.
5. **Smoke-test from the VM outwards:** `curl -sI https://$ja4proxy_domain/` must return 200 with a LE-issued cert chain (not self-signed, not staging). Failing this, run the rollback block below.
6. **Record go-live event** to `/var/log/ja4proxy/go-live.log` with timestamp, operator, domain, and resolved image digests.

## Rollback block (on any failure in steps 1–5)

```yaml
rescue:
  - name: Close UFW 80/443 again
    community.general.ufw:
      rule: deny
      port: "{{ item }}"
      proto: tcp
    loop: [80, 443]

  - name: Revert Docker bindings to 127.0.0.1
    # re-render compose with loopback bindings, docker compose up -d

  - name: Revert Caddy to staging ACME
    # re-render Caddyfile, docker compose restart caddy

  - name: Fail with guidance
    ansible.builtin.fail:
      msg: |
        Go-live aborted. System returned to locked state.
        Inspect: journalctl -u ja4proxy -n 200
                 docker compose logs caddy --tail 200
```

## Reversibility (`make go-dark`)

A companion task (to add) should close UFW, rebind to 127.0.0.1, and switch Caddy back to staging ACME — leaving the collected data intact. Proposed Makefile target:

```
go-dark:
	$(ANSIBLE) --tags "go-live,phase10" \
	  -e ja4proxy_go_live_confirm=false \
	  -e ja4proxy_go_dark=true
```

## Cost of mistakes

- Opening UFW before Caddy has a production cert → legitimate visitors see a self-signed warning page that looks like a phishing site. Don't.
- Running go-live twice in a week while the cert is in rate-limit cooldown will fail the handshake silently for the rate-limit duration. Staging-first (precondition 7) protects us.
- Opening UFW before verifying Prometheus/Grafana are *still* bound to loopback — one stray binding change and the admin UIs are on the public internet without auth review.

## Related

- `README.md` §Staged Deployment Model
- `docs/phases/RUNBOOK.md` (emergency takedown)
- `docs/phases/PHASE_13_POST_LAUNCH_OPERATIONS.md` (cert renewal monitoring, DNS preflight)
- `docs/phases/PHASE_11_LEGAL_ETHICS_AND_HONEYPOT_DISCLOSURE.md` (must be complete *before* go-live)
