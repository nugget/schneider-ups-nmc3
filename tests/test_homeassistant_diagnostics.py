"""Home Assistant diagnostics tests for APC UPS NMC."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING

import pytest
from homeassistant.const import CONF_HOST, CONF_PORT, CONF_SCAN_INTERVAL
from homeassistant.helpers.redact import REDACTED
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.schneider_ups_nmc.const import (
    CONF_AUTH_KEY,
    CONF_COMMUNITY,
    CONF_PRIVACY_KEY,
    CONF_SNMP_VERSION,
    CONF_USERNAME,
    DOMAIN,
)
from custom_components.schneider_ups_nmc.diagnostics import (
    async_get_config_entry_diagnostics,
)
from custom_components.schneider_ups_nmc.snmp import SNMP_VERSION_3, UPSData
from custom_components.schneider_ups_nmc.syslog import RoutedSyslogEvent, SyslogEvent

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

pytestmark = pytest.mark.usefixtures("enable_custom_integrations")


async def test_config_entry_diagnostics_redacts_secrets_and_reports_state(
    hass: HomeAssistant,
) -> None:
    """Return useful support data without exposing SNMP credentials."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        entry_id="01HZZZZZZZZZZZZZZZZZZZZZZZ",
        title="Rack UPS",
        unique_id="ups-test-device",
        data={
            CONF_HOST: "192.0.2.10",
            CONF_PORT: 161,
            CONF_SCAN_INTERVAL: 60,
            CONF_SNMP_VERSION: SNMP_VERSION_3,
            CONF_USERNAME: "diagnostic-user",
            CONF_AUTH_KEY: "auth-secret",
            CONF_PRIVACY_KEY: "privacy-secret",
        },
        options={
            CONF_COMMUNITY: "option-secret",
            "nested": {CONF_AUTH_KEY: "nested-secret"},
        },
    )
    entry.add_to_hass(hass)
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = _FakeCoordinator(
        data=_ups_data(),
        last_update_success=True,
        last_syslog_event=_syslog_event(),
    )

    diagnostics = await async_get_config_entry_diagnostics(hass, entry)

    assert diagnostics["entry"]["data"] == {
        CONF_HOST: "192.0.2.10",
        CONF_PORT: 161,
        CONF_SCAN_INTERVAL: 60,
        CONF_SNMP_VERSION: SNMP_VERSION_3,
        CONF_USERNAME: REDACTED,
        CONF_AUTH_KEY: REDACTED,
        CONF_PRIVACY_KEY: REDACTED,
    }
    assert diagnostics["entry"]["options"] == {
        CONF_COMMUNITY: REDACTED,
        "nested": {CONF_AUTH_KEY: REDACTED},
    }
    assert diagnostics["last_update_success"] is True
    assert diagnostics["available_keys"] == ["alarm_count", "battery_charge"]
    assert diagnostics["device"] == {
        "name": "Rack UPS",
        "manufacturer": "Schneider Electric",
        "model": "Smart-UPS 1500",
        "firmware_version": "UPS 15.0 / NMC 3.2.1",
        "agent_version": "NMC 3.2.1",
        "mac_address": "00:c0:b7:12:34:56",
    }
    assert diagnostics["last_syslog_event"] == {
        "source_host": "192.0.2.10",
        "source_port": 514,
        "facility": "user",
        "severity": "notice",
        "hostname": "ups.example.test",
        "app_name": "su_v2.5.5.1",
        "event_category": "System TEST",
        "event_text": "APC: Test Syslog.",
        "timestamp": "2026-05-25T17:45:00+00:00",
    }


@dataclass(frozen=True)
class _FakeCoordinator:
    """Minimal coordinator shape used by diagnostics."""

    data: UPSData
    last_update_success: bool
    last_syslog_event: RoutedSyslogEvent | None


def _ups_data() -> UPSData:
    """Return representative UPS data for diagnostics."""
    return UPSData(
        values={
            "alarm_count": 0,
            "battery_charge": 97,
        },
        name="Rack UPS",
        manufacturer="Schneider Electric",
        model="Smart-UPS 1500",
        serial_number="AS1234567890",
        firmware_version="UPS 15.0 / NMC 3.2.1",
        agent_version="NMC 3.2.1",
        mac_address="00:c0:b7:12:34:56",
        unique_id="ups-test-device",
    )


def _syslog_event() -> RoutedSyslogEvent:
    """Return a representative routed syslog event for diagnostics."""
    return RoutedSyslogEvent(
        source_host="192.0.2.10",
        source_port=514,
        event=SyslogEvent(
            priority=13,
            facility="user",
            severity="notice",
            timestamp=datetime(2026, 5, 25, 17, 45, tzinfo=UTC),
            hostname="ups.example.test",
            app_name="su_v2.5.5.1",
            proc_id="System",
            msg_id="TEST",
            structured_data="-",
            message="APC: Test Syslog.",
            event_category="System TEST",
            event_text="APC: Test Syslog.",
        ),
    )
