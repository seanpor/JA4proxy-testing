#!/usr/bin/env python3
"""Phase 21-L: unit tests for `_trivyignore.py`.

Every prior 21-* gate that depends on `classify()` or
`parse_policy_ceilings()` was "verified in-session" — i.e. by hand,
once, by the author. The angry reviewer would point out that nothing
in CI proves the gates would *fail* when broken. This file is the
proof: synthetic inputs go in, exact severities and ceilings come
out, and a regression in the parser surfaces immediately.

Run: `python3 scripts/ci/test_trivyignore_gates.py`
(or via `make test-trivyignore-gates` once Phase 21-L lands).
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _trivyignore import classify, parse_policy_ceilings


class TestClassifyBySection(unittest.TestCase):
    def test_critical_section(self):
        text = (
            "# === CRITICALs ===\n"
            "# expires: 2026-06-01\n"
            "CVE-2026-00001\n"
        )
        self.assertEqual(classify(text), {"CVE-2026-00001": "CRITICAL"})

    def test_high_section(self):
        text = (
            "# === HIGHs ===\n"
            "# expires: 2026-06-01\n"
            "CVE-2026-00002\n"
        )
        self.assertEqual(classify(text), {"CVE-2026-00002": "HIGH"})

    def test_singular_critical_header_also_matches(self):
        text = "# === CRITICAL ===\nCVE-2026-00003\n"
        self.assertEqual(classify(text), {"CVE-2026-00003": "CRITICAL"})

    def test_section_persists_across_blank_lines(self):
        text = (
            "# === HIGHs ===\n"
            "CVE-2026-00004\n"
            "\n"
            "CVE-2026-00005\n"
        )
        self.assertEqual(
            classify(text),
            {"CVE-2026-00004": "HIGH", "CVE-2026-00005": "HIGH"},
        )

    def test_section_switches_on_new_header(self):
        text = (
            "# === CRITICALs ===\n"
            "CVE-2026-00006\n"
            "# === HIGHs ===\n"
            "CVE-2026-00007\n"
        )
        self.assertEqual(
            classify(text),
            {"CVE-2026-00006": "CRITICAL", "CVE-2026-00007": "HIGH"},
        )


class TestClassifyMixedAndUnknown(unittest.TestCase):
    def test_mixed_section_without_annotation_is_unknown(self):
        text = (
            "# === CRITICAL + HIGHs ===\n"
            "CVE-2026-00008\n"
        )
        self.assertEqual(classify(text), {"CVE-2026-00008": "UNKNOWN"})

    def test_explicit_annotation_overrides_mixed_section(self):
        text = (
            "# === CRITICAL + HIGHs ===\n"
            "#   CVE-2026-00009 (CRITICAL) — annotated\n"
            "CVE-2026-00009\n"
            "#   CVE-2026-00010 (HIGH) — annotated\n"
            "CVE-2026-00010\n"
        )
        self.assertEqual(
            classify(text),
            {"CVE-2026-00009": "CRITICAL", "CVE-2026-00010": "HIGH"},
        )

    def test_cve_before_any_header_is_unknown(self):
        text = (
            "# expires: 2026-06-01\n"
            "CVE-2026-00011\n"
            "# === HIGHs ===\n"
            "CVE-2026-00012\n"
        )
        result = classify(text)
        self.assertEqual(result["CVE-2026-00011"], "UNKNOWN")
        self.assertEqual(result["CVE-2026-00012"], "HIGH")

    def test_explicit_annotation_overrides_section(self):
        text = (
            "# === HIGHs ===\n"
            "#   CVE-2026-00013 (CRITICAL) — actually critical\n"
            "CVE-2026-00013\n"
        )
        self.assertEqual(classify(text), {"CVE-2026-00013": "CRITICAL"})


class TestParsePolicyCeilings(unittest.TestCase):
    def test_documented_header_shape(self):
        text = (
            "#   CRITICAL → decision within 7 days,  fix within 30\n"
            "#   HIGH     → decision within 30 days, fix within 90\n"
        )
        self.assertEqual(
            parse_policy_ceilings(text),
            {"CRITICAL": 30, "HIGH": 90},
        )

    def test_missing_header_returns_empty(self):
        self.assertEqual(parse_policy_ceilings("# some other comment\n"), {})

    def test_malformed_n_returns_empty(self):
        text = "#   CRITICAL → fix within forever\n"
        self.assertEqual(parse_policy_ceilings(text), {})

    def test_drifted_values_round_trip(self):
        text = (
            "#   CRITICAL → fix within 365\n"
            "#   HIGH     → fix within 90\n"
        )
        self.assertEqual(
            parse_policy_ceilings(text),
            {"CRITICAL": 365, "HIGH": 90},
        )

    def test_partial_header_partial_dict(self):
        text = "#   CRITICAL → fix within 14\n"
        self.assertEqual(parse_policy_ceilings(text), {"CRITICAL": 14})

    def test_case_insensitive_severity(self):
        text = "#   critical → fix within 30\n#   high → fix within 90\n"
        self.assertEqual(
            parse_policy_ceilings(text),
            {"CRITICAL": 30, "HIGH": 90},
        )


class TestCurrentTreeIsConsistent(unittest.TestCase):
    """Pin the contract against the live `.trivyignore` so a
    rewording of the policy header that would fool the production
    `check_image_scan.py` gate also fails this test, with a clearer
    failure mode than 'image-scan-wired prints a generic mismatch'.
    """

    def test_live_header_is_30_90(self):
        path = Path(__file__).resolve().parents[2] / ".trivyignore"
        if not path.exists():
            self.skipTest(".trivyignore absent on this checkout")
        self.assertEqual(
            parse_policy_ceilings(path.read_text()),
            {"CRITICAL": 30, "HIGH": 90},
        )


if __name__ == "__main__":
    unittest.main()
