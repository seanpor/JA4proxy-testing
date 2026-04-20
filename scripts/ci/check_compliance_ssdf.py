#!/usr/bin/env python3
"""18-K: docs/COMPLIANCE_SSDF.md traceability.

Assertions:
  1. docs/COMPLIANCE_SSDF.md exists.
  2. It carries a `Last reviewed: YYYY-MM-DD` line within the last 365
     days (mirrors THREAT_MODEL, governance, REQUIREMENTS freshness
     gates).
  3. Every SSDF task row (first cell like `PO.1.1`, `PW.4.4`,
     `RV.3.2`) has a status value in {Yes, N/A, Partial, Not yet}.
  4. Rows whose status is Yes or Partial must cite at least one
     backticked satisfier path containing `/` in the last cell, and
     every such path must resolve to a file or directory that
     actually exists in the repo.
  5. N/A rows must include a rationale (non-empty last cell) — no
     silent skips.
  6. Task IDs are unique (no duplicate PO.1.1 rows).

Backticked tokens without a `/` are treated as inline code (e.g.
`make test`, `SIGHUP`) and ignored.
"""
from __future__ import annotations

import datetime
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DOC = ROOT / "docs" / "COMPLIANCE_SSDF.md"

ROW_RE = re.compile(
    r"^\s*\|\s*([A-Z]{2}\.\d+\.\d+)\s*\|(.*)$", re.MULTILINE
)
BACKTICK_RE = re.compile(r"`([^`]+)`")
VALID_STATUS = {"Yes", "N/A", "Partial", "Not yet"}


def main() -> int:
    errors: list[str] = []

    if not DOC.exists():
        sys.exit(f"missing: {DOC.relative_to(ROOT)} (18-K)")

    text = DOC.read_text()

    # 2. Freshness.
    m = re.search(r"^Last reviewed:\s*(\d{4}-\d{2}-\d{2})", text, re.MULTILINE)
    if not m:
        errors.append("missing or malformed `Last reviewed: YYYY-MM-DD` line")
    else:
        try:
            last = datetime.date.fromisoformat(m.group(1))
            age = (datetime.date.today() - last).days
            if age > 365:
                errors.append(f"Last reviewed {last} is {age} days old (>365)")
            if age < 0:
                errors.append(f"Last reviewed {last} is in the future")
        except ValueError as exc:
            errors.append(f"Last reviewed unparseable: {exc}")

    # 3 + 4 + 5 + 6. Walk each SSDF task row.
    seen_ids: set[str] = set()
    rows_found = 0
    for match in ROW_RE.finditer(text):
        task_id, rest = match.group(1), match.group(2)
        rows_found += 1

        if task_id in seen_ids:
            errors.append(f"{task_id}: duplicate task ID")
        seen_ids.add(task_id)

        cells = [c.strip() for c in rest.split("|")]
        if cells and cells[-1] == "":
            cells = cells[:-1]
        if len(cells) < 3:
            errors.append(
                f"{task_id}: row has fewer than 3 cells (summary/status/satisfier)"
            )
            continue

        # Layout: | ID | Summary | Status | Satisfier |
        # After splitting on the leading `| ID |`, cells are
        # [Summary, Status, Satisfier].
        status = cells[-2]
        satisfier_cell = cells[-1]

        if status not in VALID_STATUS:
            errors.append(
                f"{task_id}: status '{status}' not in {sorted(VALID_STATUS)}"
            )
            continue

        if status == "N/A":
            if not satisfier_cell:
                errors.append(f"{task_id}: N/A row missing rationale")
            continue

        if status == "Not yet":
            # Tracking link is nice-to-have but we don't enforce an
            # existing path yet — the point of "Not yet" is that the
            # satisfier isn't built. We still require a non-empty cell.
            if not satisfier_cell:
                errors.append(f"{task_id}: 'Not yet' row missing tracking link")
            continue

        # Yes / Partial: must cite at least one existing repo path.
        tokens = BACKTICK_RE.findall(satisfier_cell)
        paths = [t for t in tokens if "/" in t]
        if not paths:
            errors.append(
                f"{task_id}: {status} row has no backticked satisfier path "
                f"containing `/` in last cell"
            )
            continue

        for raw in paths:
            if raw.startswith("/") or ".." in Path(raw).parts:
                errors.append(
                    f"{task_id}: satisfier `{raw}` must be repo-relative"
                )
                continue
            target = ROOT / raw
            if not target.exists():
                errors.append(f"{task_id}: satisfier `{raw}` does not exist")

    if rows_found == 0:
        errors.append("no SSDF task rows parsed — table format broken?")

    if errors:
        print(f"{len(errors)} compliance-ssdf issue(s):")
        for e in errors:
            print(f"  {e}")
        return 1

    print(
        f"✓ docs/COMPLIANCE_SSDF.md: {rows_found} SSDF tasks mapped, all "
        f"Yes/Partial satisfier paths resolve, fresh (<365d)"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
