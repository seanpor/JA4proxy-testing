#!/usr/bin/env python3
"""Ansible collection hygiene (A6 regression).

Fails when:
  1. Any playbook/role shells out to `ansible-galaxy collection install`
     with collection names instead of `-r .../requirements.yml`.
  2. A collection is used in a task's `module: collection.ns.module`
     form without being declared (by name) in deploy/requirements.yml.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

try:
    import yaml
except ImportError:
    sys.exit("pyyaml not installed. Run: make lint-install")

ROOT = Path(__file__).resolve().parents[2]
REQS = ROOT / "deploy" / "requirements.yml"
PLAYBOOK_DIRS = [ROOT / "deploy" / "playbooks", ROOT / "deploy" / "roles"]

errors: list[str] = []

# 1. Parse declared collections.
reqs_doc = yaml.safe_load(REQS.read_text()) or {}
declared = {c["name"] for c in reqs_doc.get("collections", []) if "name" in c}
if not declared:
    errors.append(f"{REQS.relative_to(ROOT)}: no collections declared")

# 2. Walk parsed YAML, find any `ansible-galaxy collection install` command,
#    and require `-r` to be among the args. Parsing the YAML (not regexing
#    the raw file) handles folded scalars, multi-line strings, etc.
INSTALL_PREFIX = "ansible-galaxy collection install"


def walk(node, path_rel: str, out: list[str]) -> None:
    if isinstance(node, dict):
        for key, val in node.items():
            if key == "cmd" and isinstance(val, str):
                normalised = " ".join(val.split())
                if normalised.startswith(INSTALL_PREFIX):
                    rest = normalised[len(INSTALL_PREFIX):].strip().split()
                    if "-r" not in rest and "--role-file" not in rest:
                        out.append(
                            f"{path_rel}: unpinned `{normalised[:100]}` — "
                            "use `-r deploy/requirements.yml`"
                        )
            walk(val, path_rel, out)
    elif isinstance(node, list):
        for item in node:
            walk(item, path_rel, out)


for base in PLAYBOOK_DIRS:
    for path in base.rglob("*.yml"):
        try:
            docs = list(yaml.safe_load_all(path.read_text()))
        except yaml.YAMLError:
            continue
        rel = str(path.relative_to(ROOT))
        for doc in docs:
            walk(doc, rel, errors)

# 3. Every FQCN used in task YAML must reference a declared collection
#    (or ansible.builtin / ansible.posix-ish builtins we've pinned).
fqcn_re = re.compile(r"^\s+(?:module|action|tasks):\s*\n?|^\s+([a-z_]+\.[a-z_]+\.[a-z_0-9]+):\s*(?=\n|\s*#)", re.MULTILINE)
# Simpler: walk all lines and look for `ns.coll.module:` as a key.
used_fqcns: set[str] = set()
key_re = re.compile(r"^\s*([a-z][a-z_0-9]+\.[a-z][a-z_0-9]+\.[a-z][a-z_0-9]+):\s*(?:#.*)?$")
for base in PLAYBOOK_DIRS:
    for path in base.rglob("*.yml"):
        for line in path.read_text().splitlines():
            m = key_re.match(line)
            if m:
                used_fqcns.add(m.group(1))

ALWAYS_PRESENT = {"ansible.builtin"}  # ships with ansible-core

missing = set()
for fqcn in used_fqcns:
    ns_coll = ".".join(fqcn.split(".", 2)[:2])
    if ns_coll in ALWAYS_PRESENT:
        continue
    if ns_coll not in declared:
        missing.add(ns_coll)

for ns_coll in sorted(missing):
    errors.append(
        f"{REQS.relative_to(ROOT)}: collection `{ns_coll}` is used in "
        "tasks but not declared — add it (pinned) to requirements.yml"
    )

if errors:
    print(f"{len(errors)} collection hygiene issue(s):")
    for e in errors:
        print(f"  {e}")
    sys.exit(1)

print(
    f"✓ {len(declared)} collections declared, "
    f"{len(used_fqcns)} FQCN module refs all covered"
)
