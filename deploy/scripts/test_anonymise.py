#!/usr/bin/env python3
"""Unit tests for anonymise.py (12-B).

Run: python3 deploy/scripts/test_anonymise.py
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

# Import from sibling module
sys.path.insert(0, str(Path(__file__).parent))
from anonymise import anonymise_ipv4, anonymise_ipv6, anonymise_line, hmac_hash  # noqa: E402


class TestHmacHash(unittest.TestCase):
    def test_deterministic_same_salt(self):
        """Same salt + value → same hash."""
        salt = b"test-salt"
        h1 = hmac_hash(salt, "192.168.1.1")
        h2 = hmac_hash(salt, "192.168.1.1")
        self.assertEqual(h1, h2)

    def test_different_salt_diverges(self):
        """Different salt → different hash for same value."""
        h1 = hmac_hash(b"salt-a", "192.168.1.1")
        h2 = hmac_hash(b"salt-b", "192.168.1.1")
        self.assertNotEqual(h1, h2)

    def test_truncated_to_16_hex(self):
        """Output is 16 hex characters."""
        h = hmac_hash(b"salt", "value")
        self.assertEqual(len(h), 16)
        self.assertTrue(all(c in "0123456789abcdef" for c in h))


class TestAnonymiseIPv4(unittest.TestCase):
    def test_replaces_ip(self):
        result = anonymise_ipv4(b"salt", "10.0.0.1")
        self.assertNotEqual(result, "10.0.0.1")
        self.assertEqual(len(result), 16)

    def test_different_ips_different_hashes(self):
        salt = b"salt"
        h1 = anonymise_ipv4(salt, "10.0.0.1")
        h2 = anonymise_ipv4(salt, "10.0.0.2")
        self.assertNotEqual(h1, h2)


class TestAnonymiseIPv6(unittest.TestCase):
    def test_replaces_ipv6(self):
        result = anonymise_ipv6(b"salt", "2001:db8:85a3:0000:0000:8a2e:0370:7334")
        self.assertNotEqual(result, "2001:db8:85a3:0000:0000:8a2e:0370:7334")

    def test_same_prefix_same_hash(self):
        """Same /64 prefix → same hash regardless of host part."""
        salt = b"salt"
        h1 = anonymise_ipv6(salt, "2001:db8:85a3:0000:0000:0000:0000:0001")
        h2 = anonymise_ipv6(salt, "2001:db8:85a3:0000:ffff:ffff:ffff:ffff")
        self.assertEqual(h1, h2)


class TestAnonymiseLine(unittest.TestCase):
    def test_ipv4_replaced_in_line(self):
        salt = b"salt"
        line = "Connection from 192.168.1.100 on port 443"
        result = anonymise_line(salt, line)
        self.assertIsNotNone(result)
        self.assertNotIn("192.168.1.100", result)
        self.assertIn("port 443", result)

    def test_pii_redacted_not_dropped(self):
        """Email replaced with [REDACTED], line preserved."""
        salt = b"salt"
        line = "User submitted: user@example.com on port 443"
        result = anonymise_line(salt, line)
        self.assertIn("[REDACTED]", result)
        self.assertNotIn("user@example.com", result)
        self.assertIn("port 443", result)

    def test_phone_redacted_not_dropped(self):
        """Phone replaced with [REDACTED], line preserved."""
        salt = b"salt"
        line = "Phone: +1-555-123-4567 logged"
        result = anonymise_line(salt, line)
        self.assertIn("[REDACTED]", result)
        self.assertIn("logged", result)

    def test_pii_and_ip_both_scrubbed(self):
        """Line with both PII and IP: PII redacted, IP HMACed."""
        salt = b"salt"
        line = "From 10.0.0.1 user@test.org"
        result = anonymise_line(salt, line)
        self.assertNotIn("10.0.0.1", result)
        self.assertNotIn("user@test.org", result)
        self.assertIn("[REDACTED]", result)

    def test_ja4_hash_not_mangled(self):
        """JA4 fingerprint hashes must not be treated as IPv6."""
        salt = b"salt"
        line = "TLS handshake complete, JA4=t13d1516h2_8daaf6152771_b0da82dd1658"
        result = anonymise_line(salt, line)
        self.assertEqual(result, line)

    def test_clean_line_unchanged(self):
        salt = b"salt"
        line = "Connection count: 42"
        result = anonymise_line(salt, line)
        self.assertEqual(result, line)

    def test_multiple_ips_in_line(self):
        salt = b"salt"
        line = "Forward 10.0.0.1 -> 10.0.0.2"
        result = anonymise_line(salt, line)
        self.assertNotIn("10.0.0.1", result)
        self.assertNotIn("10.0.0.2", result)


if __name__ == "__main__":
    unittest.main()
