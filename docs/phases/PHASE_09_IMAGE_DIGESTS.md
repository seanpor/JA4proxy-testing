# Phase 9: Container Image Digest Pinning

## Purpose

Replace mutable Docker image tags (`haproxy:2.8-alpine`, `grafana/grafana:latest`, …) with immutable SHA-256 digests (`haproxy@sha256:…`) in the deployed `docker-compose.yml`, so that a future `docker compose pull` cannot silently pick up a compromised or accidentally-republished image.

This is a supply-chain hardening step specific to a long-running research honeypot: the images pulled on day 1 must be the same bytes running on day 90, unless the operator deliberately re-pins.

## Role

`deploy/roles/09-image-digests/` — tagged `digests` and `phase9`. Invoked as `make digests` or implicitly at the end of a full `make deploy`.

## What the role does

1. `docker pull` each of the seven service images listed in `group_vars/all.yml` (`ja4proxy_docker_image_haproxy`, `_redis`, `_caddy`, `_prometheus`, `_grafana`, `_loki`, `_promtail`).
2. For each, `docker inspect --format='{{index .RepoDigests 0}}' <image>` to resolve the RepoDigest (`haproxy@sha256:…`).
3. Write the resulting map to `{{ ja4proxy_docker_base_dir }}/image-digests.yml` as an audit trail.
4. Rewrite `docker-compose.yml` in place, replacing each `image: <tag>` line with the pinned digest form.

## ⚠ Known defect (2026-04-15)

The current rewrite task uses:

```yaml
- name: Update docker-compose.yml with pinned digests
  ansible.builtin.lineinfile:
    path: "{{ ja4proxy_docker_base_dir }}/docker-compose.yml"
    regexp: "^    image: {{ item.value.split(':')[0] }}:"
    line: "    image: {{ item.value }}"
  loop: "{{ resolved_digests | dict2items }}"
```

`item.value` is a full RepoDigest such as `haproxy@sha256:abcdef…`. Splitting on `:` and taking `[0]` produces `haproxy@sha256`, so the regex becomes `^    image: haproxy@sha256:` which **cannot match** the pre-pin compose line `image: haproxy:2.8-alpine`. On a first run the task silently replaces zero lines; `docker-compose.yml` keeps its mutable tags.

### Remediation

Rewrite the task to key off the service name rather than a derived digest prefix:

```yaml
- name: Update docker-compose.yml with pinned digests
  ansible.builtin.replace:
    path: "{{ ja4proxy_docker_base_dir }}/docker-compose.yml"
    regexp: '^(\s*image:\s+){{ image_short[item.key] }}[:@][^\s]+$'
    replace: '\1{{ item.value }}'
  loop: "{{ resolved_digests | dict2items }}"
  vars:
    image_short:
      haproxy: haproxy
      redis:   redis
      caddy:   caddy
      prometheus: prom/prometheus
      grafana: grafana/grafana
      loki:    grafana/loki
      promtail: grafana/promtail
```

Follow it with a verification task that refuses to continue if any `image:` line in the file still lacks an `@sha256:` suffix:

```yaml
- name: Assert every image line is digest-pinned
  ansible.builtin.command:
    cmd: grep -E '^\s*image:' "{{ ja4proxy_docker_base_dir }}/docker-compose.yml"
  register: image_lines
  changed_when: false

- name: Fail if any image line is not digest-pinned
  ansible.builtin.assert:
    that:
      - image_lines.stdout_lines
        | reject('search', '@sha256:[0-9a-f]{64}')
        | list | length == 0
    fail_msg: "docker-compose.yml still contains un-pinned image references."
```

## Operational procedure

**Initial deploy (expected path):**
1. `make deploy` runs roles 01–08 with mutable tags (so Docker pulls the latest of each image).
2. Role 09 resolves digests and rewrites the compose file.
3. Role 10 (go-live) starts the stack from the pinned digests.

**Re-pinning (quarterly review):**
1. `make digests` — re-pulls all images and rewrites the compose file with fresh digests. This is deliberate: it implicitly upgrades you to the newest content of each tag.
2. Review `deploy/roles/.../files/image-digests.yml` diff before committing. Reject any unexpected change of registry or image name.
3. Restart the stack: `ssh root@$VM_IP 'cd /opt/ja4proxy-docker && docker compose up -d --pull always'`.

**Emergency un-pin (temporary):**
If a pinned digest is retracted from Docker Hub and the image is needed urgently, edit the compose file directly, restart, then re-run `make digests` to re-establish a known-good pin.

## Audit trail

`/opt/ja4proxy-docker/image-digests.yml` on the VM records the digest resolution time. Copy this file to the control machine after each pin and commit it under `deploy/audit/image-digests-YYYY-MM-DD.yml` so the research artefact reproduces bit-for-bit.

## Related

- `README.md` §Phase 9
- `docs/phases/PHASE_08_SECURITY_HARDENING.md` §8.3 (supply chain)
- `docs/phases/CRITICAL_REVIEW.md` §A2
- `docs/phases/PHASE_14_CI_AND_IDEMPOTENCY.md` — adds the grep assertion as a CI test
