# Abuse reply template

Last reviewed: 2026-04-16

Canned reply for inbound abuse reports about traffic originating from
the honeypot's IP. Adapt the tone to the reporter; this is a
starting point, not a script.

---

Subject: Re: Abuse report — [IP] / [reference]

Dear [reporter],

Thank you for your report regarding traffic from [IP address].

This IP hosts a **security research honeypot** operated by [operator
name]. The system is designed to receive and fingerprint inbound
connections. Its only outbound traffic is ACME certificate renewal
and a periodic healthcheck ping — it does not initiate connections
to third-party hosts.

If you are seeing traffic from this IP, the most likely explanations
are:

1. **Reply traffic** to a connection your scanner / bot initiated to
   our honeypot (this is expected behaviour).
2. **IP misattribution** — please verify the source IP against your
   logs, as NAT or CDN headers can shift apparent origin.

If you believe this IP is genuinely attacking your infrastructure,
please provide:

- Timestamps (UTC)
- Destination IP and port
- Protocol / payload excerpt

We will investigate promptly. Our abuse contact is published in
`/.well-known/security.txt` on the domain.

Regards,
[operator name]

---

## When NOT to use this template

- If the report comes from law enforcement — follow
  `LE_REQUESTS.md` instead.
- If the report describes traffic the honeypot *should not* be
  generating (e.g. outbound scans) — investigate first, reply second.
  See `OUTBOUND_REPORTING.md`.

## Changes since last review

_<Dated list.>_
