#!/usr/bin/env python3
"""CI gate for the ADR log.

Asserts that every `docs/adr/*.md` file (except the README and the
0000 template) is a Nygard-style ADR: numbered filename, all five
required H1/H2 headings in order, and a Status line with a known
value.

Exit 0 = all ADRs valid. Exit 1 = one or more problems printed to
stderr. The CI workflow runs this on every PR so the log cannot
decay.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ADR_DIR = ROOT / "docs" / "adr"

FILENAME_RE = re.compile(r"^(\d{4})-[a-z0-9][a-z0-9-]*\.md$")
REQUIRED_SECTIONS = ("Status", "Context", "Decision", "Consequences")
VALID_STATUSES = {"Accepted", "Proposed", "Deprecated", "Superseded"}


def check_file(path: Path) -> list[str]:
    problems: list[str] = []
    text = path.read_text()
    lines = text.splitlines()

    # Title: first non-blank line must be a single '# ' heading.
    title_line = next((ln for ln in lines if ln.strip()), "")
    if not title_line.startswith("# "):
        problems.append("missing H1 title on first non-blank line")
    else:
        title_body = title_line[2:].strip()
        # Expect '# N. Something' or '# NN. Something' etc.
        if not re.match(r"^\d+\.\s+\S", title_body):
            problems.append(
                f"title should start with a number and a period: {title_line!r}"
            )

    # Required section headings must appear in order as '## X'.
    positions: list[int] = []
    for section in REQUIRED_SECTIONS:
        needle = f"## {section}"
        try:
            positions.append(lines.index(needle))
        except ValueError:
            problems.append(f"missing required heading '## {section}'")
    if len(positions) == len(REQUIRED_SECTIONS) and positions != sorted(positions):
        problems.append(
            "required sections are out of order "
            f"(found at line offsets {positions}, expected ascending)"
        )

    # Status line: the first non-blank line after '## Status' must be a
    # known value (or 'Superseded by ...').
    try:
        status_idx = lines.index("## Status")
    except ValueError:
        return problems  # already reported above
    status_body = ""
    for ln in lines[status_idx + 1 :]:
        if ln.strip():
            status_body = ln.strip()
            break
    if not status_body:
        problems.append("'## Status' section is empty")
    else:
        first_word = status_body.split()[0]
        if first_word not in VALID_STATUSES:
            # Accepts pipe-separated values in the template; reject here.
            problems.append(
                f"Status line {status_body!r} does not start with one of "
                f"{sorted(VALID_STATUSES)}"
            )
    return problems


def main() -> int:
    if not ADR_DIR.is_dir():
        print(f"{ADR_DIR} does not exist", file=sys.stderr)
        return 1

    adr_files = sorted(
        p for p in ADR_DIR.glob("*.md") if p.name not in {"README.md", "0000-template.md"}
    )
    if not adr_files:
        print(f"no ADRs found under {ADR_DIR}", file=sys.stderr)
        return 1

    failures: list[tuple[Path, list[str]]] = []
    seen_numbers: dict[str, Path] = {}
    for adr in adr_files:
        m = FILENAME_RE.match(adr.name)
        if not m:
            failures.append(
                (adr, [f"filename {adr.name!r} does not match NNNN-slug.md"])
            )
            continue
        number = m.group(1)
        if number in seen_numbers:
            failures.append(
                (adr, [f"duplicate ADR number {number} (also in {seen_numbers[number].name})"])
            )
        else:
            seen_numbers[number] = adr
        problems = check_file(adr)
        if problems:
            failures.append((adr, problems))

    if failures:
        for adr, problems in failures:
            for p in problems:
                print(f"{adr.relative_to(ROOT)}: {p}", file=sys.stderr)
        return 1

    print(f"✓ {len(adr_files)} ADR(s) valid under docs/adr/")
    return 0


if __name__ == "__main__":
    sys.exit(main())
