"""Shared `.trivyignore` parser — CVE-to-severity classification.

Two CI gates need to know which allowlisted CVE belongs to which
severity tier:

  * `check_cve_reachability.py` (21-G coverage invariant) needs the
    CRITICAL set, so it can fail when a CRITICAL entry has no
    reachability probe.
  * `check_image_scan.py` (21-H expiry-ceiling enforcement) needs both
    CRITICAL and HIGH so it can fail when an entry's expiry is more
    than {30, 90} days out — codifying the policy header
    (`CRITICAL → fix within 30 days, HIGH → fix within 90`) into a
    mechanical gate rather than a written aspiration.

Keeping the classifier in one module prevents the two gates from
silently disagreeing on a borderline case — exactly the drift mode
this governance work was created to attack.

The classifier is a pure function over the file's text; callers do
their own file I/O so unit tests can supply synthetic inputs."""
from __future__ import annotations

import re

CVE_ANNOT_RE = re.compile(r"(CVE-\d{4}-\d+)\s*\((CRITICAL|HIGH)\)")
SECTION_RE = re.compile(
    r"#\s*===\s*(CRITICALs?|HIGHs?|CRITICAL\s*\+\s*HIGHs?)",
    re.IGNORECASE,
)
CVE_LINE_RE = re.compile(r"^(CVE-\d{4}-\d+)\s*$")


def classify(text: str) -> dict[str, str]:
    """`{CVE_ID: severity}` for every uncommented CVE entry in `text`.

    Severity precedence:
      1. Explicit `(CRITICAL)` / `(HIGH)` annotation in any preceding
         comment (handles mixed `=== CRITICAL + HIGHs ===` sections).
      2. Most recent `=== CRITICALs ===` or `=== HIGHs ===` section
         header.
      3. `UNKNOWN` when neither — caller decides how strict to be."""
    explicit: dict[str, str] = {}
    for m in CVE_ANNOT_RE.finditer(text):
        explicit[m.group(1)] = m.group(2)

    section: str | None = None
    out: dict[str, str] = {}
    for raw in text.splitlines():
        sm = SECTION_RE.match(raw)
        if sm:
            label = sm.group(1).upper().replace(" ", "")
            if "CRITICAL" in label and "HIGH" not in label:
                section = "CRITICAL"
            elif "HIGH" in label and "CRITICAL" not in label:
                section = "HIGH"
            else:
                section = None  # mixed → require explicit annotation
            continue

        cm = CVE_LINE_RE.match(raw)
        if cm:
            cve = cm.group(1)
            out[cve] = explicit.get(cve) or section or "UNKNOWN"
    return out
