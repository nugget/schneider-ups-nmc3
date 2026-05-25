"""Tests for Schneider Electric UPS NMC3 syslog parsing."""

from __future__ import annotations

import sys
import unittest
from importlib import util
from pathlib import Path

SYSLOG_PATH = (
    Path(__file__).resolve().parents[1]
    / "custom_components"
    / "schneider_ups_nmc3"
    / "syslog.py"
)
SYSLOG_SPEC = util.spec_from_file_location("schneider_ups_nmc3_syslog", SYSLOG_PATH)
assert SYSLOG_SPEC is not None
syslog = util.module_from_spec(SYSLOG_SPEC)
sys.modules[SYSLOG_SPEC.name] = syslog
assert SYSLOG_SPEC.loader is not None
SYSLOG_SPEC.loader.exec_module(syslog)


class ParseSyslogMessageTest(unittest.TestCase):
    """Test NMC syslog message parsing."""

    def test_parses_nmc3_test_message(self) -> None:
        """Parse the RFC5424-ish NMC3 syslog test format."""
        event = syslog.parse_syslog_message(
            (
                "<8>1 2026-05-25T01:20:40-05:00 "
                "ups.example.test su_v2.5.5.1 System TEST - APC: Test Syslog."
            )
        )

        self.assertEqual(event.priority, 8)
        self.assertEqual(event.facility, "user")
        self.assertEqual(event.severity, "emergency")
        self.assertEqual(event.hostname, "ups.example.test")
        self.assertEqual(event.app_name, "su_v2.5.5.1")
        self.assertEqual(event.proc_id, "System")
        self.assertEqual(event.msg_id, "TEST")
        self.assertEqual(event.structured_data, "-")
        self.assertEqual(event.event_category, "System TEST")
        self.assertEqual(event.event_text, "APC: Test Syslog.")


if __name__ == "__main__":
    unittest.main()
