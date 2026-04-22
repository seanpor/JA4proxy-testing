#!/usr/bin/env python3
"""CI gate for the ADR log.

Asserts that every `docs/adr/*.md` file (except the README and the
0000 template) is a Nygard-style ADR: numbered filename, all five
required H1/H2 headings in order, and a Status line with a known
value.

Phase 20 P1-10 hardening:
  * Require at least `MIN_SECTION_CHARS` of non-whitespace content
    under each of Context / Decision / Consequences. A 1-char body
    used to pass.
  * If Status is Deprecated or Superseded, require an explicit
    `Superseded by NNNN-slug.md` pointer that resolves to a sibling
    ADR file.
  * Verify `docs/adr/README.md`'s index table lists exactly the set
    of numbered ADR files on disk (no silent drift between filesystem
    and index).

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
SUBSTANTIVE_SECTIONS = ("Context", "Decision", "Consequences")
VALID_STATUSES = {"Accepted", "Proposed", "Deprecated", "Superseded"}
MIN_SECTION_CHARS = 100
SUPERSEDED_RE = re.compile(
    r"Superseded by\s+(?P<slug>\d{4}-[a-z0-9][a-z0-9-]*\.md)"
)
INDEX_ROW_RE = re.compile(r"^\|\s*\[(\d{4})\]\(([^)]+)\)\s*\|")


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
            problems.append(
                f"Status line {status_body!r} does not start with one of "
                f"{sorted(VALID_STATUSES)}"
            )
        # Phase 20 P1-10: Deprecated / Superseded require a pointer.
        if first_word in {"Deprecated", "Superseded"}:
            m = SUPERSEDED_RE.search(status_body)
            if not m:
                problems.append(
                    f"Status is {first_word!r} but no "
                    f"`Superseded by NNNN-slug.md` pointer found in status body"
                )
            else:
                target = path.parent / m.group("slug")
                if not target.is_file():
                    problems.append(
                        f"Status points to `{m.group('slug')}` but that "
                        f"ADR file does not exist"
                    )

    # Phase 20 P1-10: substantive-section word count. Extract the body
    # between `## X` and the next `## ` heading, strip whitespace, and
    # enforce a floor.
    def section_body(heading: str) -> str:
        try:
            start = lines.index(f"## {heading}")
        except ValueError:
            return ""
        body: list[str] = []
        for ln in lines[start + 1 :]:
            if ln.startswith("## "):
                break
            body.append(ln)
        return "\n".join(body).strip()

    for sec in SUBSTANTIVE_SECTIONS:
        body = section_body(sec)
        compact = re.sub(r"\s+", "", body)
        if len(compact) < MIN_SECTION_CHARS:
            problems.append(
                f"'## {sec}' has only {len(compact)} non-whitespace chars "
                f"(< {MIN_SECTION_CHARS}) — too thin to be a real ADR section"
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

    # Phase 20 P1-10: cross-check README.md index against the filesystem.
    readme = ADR_DIR / "README.md"
    if readme.is_file():
        indexed: set[str] = set()
        for ln in readme.read_text().splitlines():
            m = INDEX_ROW_RE.match(ln)
            if m:
                indexed.add(m.group(2).lstrip("./"))
        on_disk = {adr.name for adr in adr_files}
        missing_from_index = sorted(on_disk - indexed)
        orphan_rows = sorted(indexed - on_disk)
        if missing_from_index:
            failures.append(
                (readme, [
                    f"index missing row(s) for ADR file(s): "
                    f"{missing_from_index}"
                ])
            )
        if orphan_rows:
            failures.append(
                (readme, [
                    f"index has row(s) with no matching file: {orphan_rows}"
                ])
            )

    if failures:
        for adr, problems in failures:
            for p in problems:
                print(f"{adr.relative_to(ROOT)}: {p}", file=sys.stderr)
        return 1

    print(f"✓ {len(adr_files)} ADR(s) valid under docs/adr/")
    return 0


if __name__ == "__main__":
    sys.exit(main())
