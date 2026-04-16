#!/usr/bin/env python3
"""17-B: Detect identical files between deploy/files/ and deploy/roles/*/files/."""
from __future__ import annotations

import hashlib
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
DEPLOY_FILES = REPO / "deploy" / "files"
ROLES = REPO / "deploy" / "roles"

duplicates: list[str] = []


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


# Index every file under deploy/files/
if DEPLOY_FILES.is_dir():
    top_files: dict[str, Path] = {}
    for f in DEPLOY_FILES.rglob("*"):
        if f.is_file():
            rel = str(f.relative_to(DEPLOY_FILES))
            top_files[rel] = f

    # Check for identical copies under each role's files/
    for role_dir in sorted(ROLES.iterdir()):
        role_files = role_dir / "files"
        if not role_files.is_dir():
            continue
        for f in role_files.rglob("*"):
            if not f.is_file():
                continue
            rel = str(f.relative_to(role_files))
            if rel in top_files and sha256(f) == sha256(top_files[rel]):
                duplicates.append(
                    f"deploy/files/{rel} == "
                    f"deploy/roles/{role_dir.name}/files/{rel}"
                )

if duplicates:
    print("Duplicate files found (keep the role copy, remove deploy/files/ copy):")
    for d in duplicates:
        print(f"  {d}")
    sys.exit(1)

print("✓ no duplicate files between deploy/files/ and role files/")
