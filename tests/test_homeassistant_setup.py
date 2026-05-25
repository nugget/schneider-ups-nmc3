"""Home Assistant integration tests for Schneider Electric UPS NMC3."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, ClassVar, cast

import pytest
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import (
    CONF_HOST,
    CONF_PORT,
    CONF_SCAN_INTERVAL,
    STATE_UNAVAILABLE,
)
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers import issue_registry as ir
from pytest_homeassistant_custom_component.common import MockConfigEntry

import custom_components.schneider_ups_nmc3 as integration
import custom_components.schneider_ups_nmc3.coordinator as coordinator_module
from custom_components.schneider_ups_nmc3.const import (
    CONF_COMMUNITY,
    CONF_SNMP_VERSION,
    CONF_SYSLOG_BIND_ADDRESS,
    CONF_SYSLOG_ENABLED,
    CONF_SYSLOG_PORT,
    DOMAIN,
)
from custom_components.schneider_ups_nmc3.snmp import SNMP_VERSION_2C, UPSData

if TYPE_CHECKING:
    from collections.abc import Mapping

    from homeassistant.core import HomeAssistant

    from custom_components.schneider_ups_nmc3.coordinator import (
        SchneiderUPSNMC3Coordinator,
    )

ENTRY_ID = "01HZZZZZZZZZZZZZZZZZZZZZZZ"
ENTRY_UNIQUE_ID = "ups-test-device"
pytestmark = pytest.mark.usefixtures("enable_custom_integrations")


async def test_config_entry_sets_up_entities_and_unloads(
    hass: HomeAssistant,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Set up a config entry, create entities, and unload cleanly."""
    _FakeSNMPClient.instances.clear()
    monkeypatch.setattr(coordinator_module, "SNMPClient", _FakeSNMPClient)

    entry = _mock_entry(options={CONF_SYSLOG_ENABLED: False})
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED
    assert _FakeSNMPClient.instances
    entity_id = er.async_get(hass).async_get_entity_id(
        "sensor",
        DOMAIN,
        f"{ENTRY_UNIQUE_ID}_battery_charge",
    )
    assert entity_id is not None
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == "97"

    missing_entity_id = er.async_get(hass).async_get_entity_id(
        "sensor",
        DOMAIN,
        f"{ENTRY_UNIQUE_ID}_battery_temperature",
    )
    assert missing_entity_id is not None
    missing_state = hass.states.get(missing_entity_id)
    assert missing_state is not None
    assert missing_state.state == STATE_UNAVAILABLE

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.NOT_LOADED
    assert _FakeSNMPClient.instances[0].closed


async def test_config_entry_marks_missing_binary_value_unavailable(
    hass: HomeAssistant,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Mark binary sensors unavailable when their source value is absent."""
    _SparseSNMPClient.instances.clear()
    monkeypatch.setattr(coordinator_module, "SNMPClient", _SparseSNMPClient)

    entry = _mock_entry(options={CONF_SYSLOG_ENABLED: False})
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    entity_id = er.async_get(hass).async_get_entity_id(
        "binary_sensor",
        DOMAIN,
        f"{ENTRY_UNIQUE_ID}_battery_low",
    )
    assert entity_id is not None
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == STATE_UNAVAILABLE

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    assert _SparseSNMPClient.instances[0].closed


async def test_syslog_register_failure_creates_and_clears_repair_issue(
    hass: HomeAssistant,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Create a Repair issue when the syslog listener cannot bind."""
    manager = _FailingSyslogManager()
    monkeypatch.setattr(
        integration,
        "_syslog_manager",
        _manager_factory(manager),
    )
    entry = _mock_entry(
        options={
            CONF_SYSLOG_BIND_ADDRESS: "127.0.0.1",
            CONF_SYSLOG_PORT: 1515,
        }
    )

    await integration._async_register_syslog(
        hass,
        entry,
        cast("SchneiderUPSNMC3Coordinator", object()),
    )

    registry = ir.async_get(hass)
    issue = registry.async_get_issue(
        DOMAIN,
        f"{integration.SYSLOG_LISTENER_FAILED_ISSUE}_{ENTRY_ID}",
    )
    assert issue is not None
    assert issue.translation_placeholders == {
        "address": "127.0.0.1:1515",
        "error": "address already in use",
        "name": "Rack UPS",
    }

    disabled_entry = _mock_entry(options={CONF_SYSLOG_ENABLED: False})
    await integration._async_register_syslog(
        hass,
        disabled_entry,
        cast("SchneiderUPSNMC3Coordinator", object()),
    )

    assert (
        registry.async_get_issue(
            DOMAIN,
            f"{integration.SYSLOG_LISTENER_FAILED_ISSUE}_{ENTRY_ID}",
        )
        is None
    )


async def test_syslog_listener_conflict_creates_repair_issue(
    hass: HomeAssistant,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Create a Repair issue when entries request conflicting listener settings."""
    manager = _ConflictingSyslogManager()
    monkeypatch.setattr(
        integration,
        "_syslog_manager",
        _manager_factory(manager),
    )
    entry = _mock_entry(
        options={
            CONF_SYSLOG_BIND_ADDRESS: "127.0.0.1",
            CONF_SYSLOG_PORT: 1515,
        }
    )

    await integration._async_register_syslog(
        hass,
        entry,
        cast("SchneiderUPSNMC3Coordinator", object()),
    )

    issue = ir.async_get(hass).async_get_issue(
        DOMAIN,
        f"{integration.SYSLOG_LISTENER_CONFLICT_ISSUE}_{ENTRY_ID}",
    )
    assert issue is not None
    assert issue.translation_placeholders == {
        "active": "0.0.0.0:1514",
        "name": "Rack UPS",
        "requested": "127.0.0.1:1515",
    }


def _mock_entry(
    *,
    options: Mapping[str, Any] | None = None,
) -> MockConfigEntry:
    """Return a representative config entry for HA setup tests."""
    return MockConfigEntry(
        domain=DOMAIN,
        entry_id=ENTRY_ID,
        title="Rack UPS",
        unique_id=ENTRY_UNIQUE_ID,
        data={
            CONF_HOST: "192.0.2.10",
            CONF_PORT: 161,
            CONF_SCAN_INTERVAL: 60,
            CONF_SNMP_VERSION: SNMP_VERSION_2C,
            CONF_COMMUNITY: "public",
        },
        options=dict(options or {}),
    )


def _manager_factory(
    manager: _FailingSyslogManager | _ConflictingSyslogManager,
) -> Any:
    """Return a fake syslog manager factory for integration setup."""

    def get_manager(
        _hass: HomeAssistant,
        *,
        bind_address: str,
        port: int,
    ) -> _FailingSyslogManager | _ConflictingSyslogManager:
        assert bind_address == "127.0.0.1"
        assert port == 1515
        return manager

    return get_manager


class _FakeSNMPClient:
    """SNMP client fake that returns stable UPS data."""

    instances: ClassVar[list[_FakeSNMPClient]] = []

    def __init__(self, config: object) -> None:
        """Initialize the fake SNMP client."""
        self.config = config
        self.closed = False
        self.instances.append(self)

    async def async_get_data(self) -> UPSData:
        """Return representative UPS data."""
        return UPSData(
            values={
                "alarm_count": 0,
                "battery_charge": 97,
                "battery_replace_indicator": "ok",
                "battery_status": "battery_normal",
                "output_source": "normal",
                "seconds_on_battery": 0,
            },
            name="Rack UPS",
            manufacturer="Schneider Electric",
            model="Smart-UPS 1500",
            serial_number="AS1234567890",
            firmware_version="UPS 15.0 / NMC 3.2.1",
            agent_version="NMC 3.2.1",
            mac_address="00:c0:b7:12:34:56",
            unique_id=ENTRY_UNIQUE_ID,
        )

    def close(self) -> None:
        """Close the fake SNMP client."""
        self.closed = True


class _SparseSNMPClient(_FakeSNMPClient):
    """SNMP client fake that omits optional values."""

    instances: ClassVar[list[_SparseSNMPClient]] = []

    async def async_get_data(self) -> UPSData:
        """Return UPS data without battery status details."""
        return UPSData(
            values={
                "battery_charge": 97,
            },
            name="Rack UPS",
            manufacturer="Schneider Electric",
            model="Smart-UPS 1500",
            serial_number="AS1234567890",
            firmware_version="UPS 15.0 / NMC 3.2.1",
            agent_version="NMC 3.2.1",
            mac_address="00:c0:b7:12:34:56",
            unique_id=ENTRY_UNIQUE_ID,
        )


class _FailingSyslogManager:
    """Syslog manager fake that fails during registration."""

    bind_address = "127.0.0.1"
    port = 1515

    def is_configured_for(self, bind_address: str, port: int) -> bool:
        """Return whether the fake listener matches the requested settings."""
        return self.bind_address == bind_address and self.port == port

    async def async_register(self, _coordinator: object) -> None:
        """Fail to register a coordinator."""
        raise OSError("address already in use")


class _ConflictingSyslogManager:
    """Syslog manager fake that already owns different listener settings."""

    bind_address = "0.0.0.0"
    port = 1514

    def is_configured_for(self, _bind_address: str, _port: int) -> bool:
        """Return whether the fake listener matches the requested settings."""
        return False
