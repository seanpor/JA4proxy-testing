#!/usr/bin/env python3
"""18-H: docs/REQUIREMENTS.md traceability.

Assertions:
  1. docs/REQUIREMENTS.md exists at the documented path.
  2. It carries a `Last reviewed: YYYY-MM-DD` line within the last
     365 days (mirrors THREAT_MODEL + governance freshness gates).
  3. Every `F-NN` and `NF-NN` requirement row has at least one
     backtick-quoted satisfier path containing a `/`.
  4. Every such satisfier path resolves to a file or directory that
     actually exists in the repo. Renaming a cited role/template/script
     without updating the table fails this check (the 18-H acceptance).
  5. Requirement IDs are unique within their family (no duplicate
     F-01s, no duplicate NF-03s).

Backticked tokens without a `/` are treated as inline code (e.g.
`SIGHUP`, `make test`) and ignored.
"""
from __future__ import annotations

import datetime
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DOC = ROOT / "docs" / "REQUIREMENTS.md"

ID_RE = re.compile(r"^\s*\|\s*(F-\d{2}|NF-\d{2})\s*\|", re.MULTILINE)
ROW_RE = re.compile(r"^\s*\|\s*(F-\d{2}|NF-\d{2})\s*\|(.*)$", re.MULTILINE)
BACKTICK_RE = re.compile(r"`([^`]+)`")


def main() -> int:
    errors: list[str] = []

    if not DOC.exists():
        sys.exit(f"missing: {DOC.relative_to(ROOT)} (18-H)")

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

    # 3 + 4 + 5. Walk each requirement row.
    seen_ids: set[str] = set()
    rows_found = 0
    for match in ROW_RE.finditer(text):
        req_id, rest = match.group(1), match.group(2)
        rows_found += 1

        if req_id in seen_ids:
            errors.append(f"{req_id}: duplicate ID")
        seen_ids.add(req_id)

        # The ID is in column 1; satisfiers are in the *last* pipe-delimited
        # cell. Split on `|`, strip empty trailing cell from a closing pipe.
        cells = [c.strip() for c in rest.split("|")]
        if cells and cells[-1] == "":
            cells = cells[:-1]
        if not cells:
            errors.append(f"{req_id}: row has no requirement / satisfier cells")
            continue
        satisfier_cell = cells[-1]

        tokens = BACKTICK_RE.findall(satisfier_cell)
        paths = [t for t in tokens if "/" in t]
        if not paths:
            errors.append(
                f"{req_id}: no backticked satisfier path containing `/` "
                f"in last cell"
            )
            continue

        for raw in paths:
            # Reject absolute paths and parent-escapes — satisfiers must be
            # repo-relative.
            if raw.startswith("/") or ".." in Path(raw).parts:
                errors.append(f"{req_id}: satisfier `{raw}` must be repo-relative")
                continue
            target = ROOT / raw
            if not target.exists():
                errors.append(f"{req_id}: satisfier `{raw}` does not exist")

    if rows_found == 0:
        errors.append("no F-NN or NF-NN rows parsed — table format broken?")

    if errors:
        print(f"{len(errors)} requirements-traceability issue(s):")
        for e in errors:
            print(f"  {e}")
        return 1

    print(
        f"✓ docs/REQUIREMENTS.md: {rows_found} requirements, all satisfier "
        f"paths resolve, fresh (<365d)"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
