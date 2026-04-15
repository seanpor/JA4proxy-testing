# Law-enforcement request handling

Last reviewed: 2026-04-15

Procedure for handling requests from law enforcement for data the
honeypot has collected. The operator is the single point of contact;
this file is the procedure they follow.

## 1. Intake

1. Requests arrive via:
   - the `security.txt` contact address (`Contact:` field),
   - the `/privacy.html` published contact, or
   - the domain registrar / hosting provider forwarding an abuse
     report.
2. Record the request: sender, date, legal instrument (subpoena /
   court order / voluntary request), jurisdiction, scope of data
   requested, deadline.
3. Do **not** respond with data at intake. Acknowledge receipt only.

## 2. Validation

- Is the request from a recognised authority in a jurisdiction that
  can compel production? If no — decline politely, cite jurisdiction.
- Is the legal instrument the right kind for the data being asked
  for? (A subpoena is not the same as a warrant; "voluntary"
  requests are voluntary.)
- Is the scope proportionate and specific? Broad "all logs"
  fishing-style requests should be pushed back on, not silently
  complied with.

If in doubt, seek legal advice before responding. Note in the record
that advice was sought and when.

## 3. Decision

Three outcomes:

1. **Comply fully** — request is valid, scope is proportionate.
2. **Comply partially** — narrow the scope to what is strictly
   required, respond with that only.
3. **Decline** — with written reasoning; the operator is the
   accountable party for a decline decision.

## 4. Production

If producing data:

- Run the data export under the evidence-preservation flow
  (`preserve-evidence.sh` from chunk 15-A) so the export is captured
  in a mode-0600 tarball alongside the original state.
- HMAC-anonymise where the request does not explicitly require raw
  IPs (chunk 12-B, when available).
- Transfer over a channel appropriate to the sensitivity — do not
  email raw IP lists in cleartext.
- Keep a copy of what was produced + the decision log for 7 years
  (or the jurisdiction's retention requirement, whichever is longer).

## 5. Transparency

If the legal instrument permits disclosure, publish a short notice
on the project's public page (aggregated annually). If a gag applies,
record the fact that one applies so the annual transparency note can
be truthful ("N requests received, M under non-disclosure").

## 6. Changes since last review

_<Dated list.>_
