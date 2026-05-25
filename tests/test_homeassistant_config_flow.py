"""Home Assistant config flow tests for Schneider Electric UPS NMC3."""

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar

import pytest
from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_PORT, CONF_SCAN_INTERVAL
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import MockConfigEntry

import custom_components.schneider_ups_nmc3.config_flow as config_flow_module
from custom_components.schneider_ups_nmc3.const import (
    CONF_COMMUNITY,
    CONF_SNMP_VERSION,
    CONF_SYSLOG_BIND_ADDRESS,
    CONF_SYSLOG_ENABLED,
    CONF_SYSLOG_PORT,
    DOMAIN,
)
from custom_components.schneider_ups_nmc3.snmp import (
    SNMP_VERSION_2C,
    SNMPConnectionConfig,
    SNMPError,
    UPSData,
)

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant


pytestmark = pytest.mark.usefixtures("enable_custom_integrations")


async def test_snmpv2c_config_flow_creates_entry(
    hass: HomeAssistant,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Create an entry after validating SNMPv2c settings."""
    _FakeConfigFlowSNMPClient.instances.clear()
    monkeypatch.setattr(config_flow_module, "SNMPClient", _FakeConfigFlowSNMPClient)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
        data={
            CONF_HOST: "192.0.2.10",
            CONF_PORT: 161,
            CONF_SCAN_INTERVAL: 60,
            CONF_SNMP_VERSION: SNMP_VERSION_2C,
        },
    )

    assert result.get("type") is FlowResultType.FORM
    assert result.get("step_id") == "snmpv2c"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_COMMUNITY: "public"},
    )

    assert result.get("type") is FlowResultType.CREATE_ENTRY
    assert result.get("title") == "Rack UPS"
    assert result.get("data") == {
        CONF_HOST: "192.0.2.10",
        CONF_PORT: 161,
        CONF_SCAN_INTERVAL: 60,
        CONF_SNMP_VERSION: SNMP_VERSION_2C,
        CONF_COMMUNITY: "public",
    }
    assert _FakeConfigFlowSNMPClient.instances[0].config == SNMPConnectionConfig(
        host="192.0.2.10",
        port=161,
        version=SNMP_VERSION_2C,
        community="public",
        timeout=2.0,
        retries=1,
    )
    assert _FakeConfigFlowSNMPClient.instances[0].closed


async def test_snmpv2c_config_flow_reports_connection_failure(
    hass: HomeAssistant,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Show a form error when SNMP validation cannot query the UPS."""
    _FailingConfigFlowSNMPClient.instances.clear()
    monkeypatch.setattr(config_flow_module, "SNMPClient", _FailingConfigFlowSNMPClient)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
        data={
            CONF_HOST: "192.0.2.10",
            CONF_PORT: 161,
            CONF_SCAN_INTERVAL: 60,
            CONF_SNMP_VERSION: SNMP_VERSION_2C,
        },
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_COMMUNITY: "public"},
    )

    assert result.get("type") is FlowResultType.FORM
    assert result.get("step_id") == "snmpv2c"
    assert result.get("errors") == {"base": "cannot_connect"}
    assert _FailingConfigFlowSNMPClient.instances[0].closed


async def test_options_flow_saves_polling_and_syslog_options(
    hass: HomeAssistant,
) -> None:
    """Persist scan interval and syslog listener options."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Rack UPS",
        unique_id="ups-test-device",
        data={
            CONF_HOST: "192.0.2.10",
            CONF_PORT: 161,
            CONF_SCAN_INTERVAL: 60,
            CONF_SNMP_VERSION: SNMP_VERSION_2C,
            CONF_COMMUNITY: "public",
        },
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(entry.entry_id)

    assert result.get("type") is FlowResultType.FORM
    assert result.get("step_id") == "init"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {
            CONF_SCAN_INTERVAL: 120,
            CONF_SYSLOG_ENABLED: False,
            CONF_SYSLOG_BIND_ADDRESS: "127.0.0.1",
            CONF_SYSLOG_PORT: 1515,
        },
    )

    assert result.get("type") is FlowResultType.CREATE_ENTRY
    assert result.get("data") == {
        CONF_SCAN_INTERVAL: 120,
        CONF_SYSLOG_ENABLED: False,
        CONF_SYSLOG_BIND_ADDRESS: "127.0.0.1",
        CONF_SYSLOG_PORT: 1515,
    }


class _FakeConfigFlowSNMPClient:
    """SNMP client fake that validates config-flow inputs."""

    instances: ClassVar[list[_FakeConfigFlowSNMPClient]] = []

    def __init__(self, config: SNMPConnectionConfig) -> None:
        """Initialize the fake SNMP client."""
        self.config = config
        self.closed = False
        self.instances.append(self)

    async def async_get_data(self) -> UPSData:
        """Return identity data for config-flow validation."""
        return UPSData(
            values={},
            name="Rack UPS",
            manufacturer="Schneider Electric",
            model="Smart-UPS 1500",
            serial_number="AS1234567890",
            firmware_version="UPS 15.0 / NMC 3.2.1",
            agent_version="NMC 3.2.1",
            mac_address="00:c0:b7:12:34:56",
            unique_id="as1234567890",
        )

    def close(self) -> None:
        """Close the fake SNMP client."""
        self.closed = True


class _FailingConfigFlowSNMPClient(_FakeConfigFlowSNMPClient):
    """SNMP client fake that fails validation."""

    instances: ClassVar[list[_FailingConfigFlowSNMPClient]] = []

    async def async_get_data(self) -> UPSData:
        """Raise a connection failure during validation."""
        raise SNMPError("timeout")
