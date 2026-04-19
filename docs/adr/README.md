# Architecture Decision Records

This directory is the append-only log of significant architectural
decisions for the JA4proxy research honeypot. Each ADR captures the
context, the decision itself, and its consequences in Michael Nygard's
format.

## Why ADRs

A markdown table of "design decisions" is mutable — rows can be edited
or deleted without trace. An ADR log is **append-only**: when a
decision is reversed, the old ADR is marked `Superseded by NNNN` and
stays in place. The history of why the system looks the way it does
remains inspectable from `git log docs/adr/` alone. SWEBOK v4 endorses
this pattern in both its *Models & Methods* and *Process* KAs.

## Index

| # | Title | Status |
|---|-------|--------|
| [0001](0001-no-build-tools-on-server.md) | No build tools on the server | Accepted |
| [0002](0002-go-binary-for-ja4proxy.md) | Go binary for JA4proxy | Accepted |
| [0003](0003-docker-compose-for-supporting-services.md) | Docker Compose for supporting services | Accepted |
| [0004](0004-no-container-registry.md) | No private container registry | Accepted |
| [0005](0005-static-html-and-caddy-for-honeypot.md) | Static HTML plus Caddy for the honeypot | Accepted |
| [0006](0006-dial-zero-at-start.md) | Dial = 0 at initial deployment | Accepted |
| [0007](0007-no-external-threat-intel.md) | No external threat-intel feeds initially | Accepted |

## Adding a new ADR

1. Copy `0000-template.md` to the next free number, e.g.
   `0008-my-decision.md`. Zero-pad to four digits, kebab-case the slug.
2. Fill in all five sections (Title / Status / Context / Decision /
   Consequences). Keep it to one page — if a decision needs more, it's
   probably two decisions.
3. Add a row to the index table above.
4. Commit the ADR in the same PR that implements (or at least starts)
   the change. `scripts/ci/check_adr_format.py` runs in CI and will
   reject files missing the five headings or a valid `Status:` line.

## Superseding an ADR

Never edit the Decision section of an accepted ADR after the fact. If
the decision changes, write a new ADR, link back to the old one in its
Context, and change the old one's Status to
`Superseded by NNNN-new-title.md`. That's the only permitted edit to
an accepted ADR's body.
