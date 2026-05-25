"""Home Assistant config flow tests for APC UPS NMC."""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING, Any, ClassVar
from unittest.mock import Mock

import pytest
from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_PORT, CONF_SCAN_INTERVAL
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers.selector import TextSelector, TextSelectorType
from pytest_homeassistant_custom_component.common import MockConfigEntry

import custom_components.schneider_ups_nmc.config_flow as config_flow_module
from custom_components.schneider_ups_nmc.const import (
    CONF_AUTH_KEY,
    CONF_AUTH_PROTOCOL,
    CONF_COMMUNITY,
    CONF_PRIVACY_KEY,
    CONF_PRIVACY_PROTOCOL,
    CONF_SNMP_VERSION,
    CONF_SYSLOG_BIND_ADDRESS,
    CONF_SYSLOG_ENABLED,
    CONF_SYSLOG_PORT,
    CONF_USERNAME,
    DOMAIN,
)
from custom_components.schneider_ups_nmc.snmp import (
    AUTH_PROTOCOL_SHA,
    PRIVACY_PROTOCOL_AES,
    SNMP_VERSION_2C,
    SNMP_VERSION_3,
    SNMPConnectionConfig,
    SNMPError,
    UPSData,
)

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant


pytestmark = pytest.mark.usefixtures("enable_custom_integrations")

INTEGRATION_DIR = Path(__file__).parents[1] / "custom_components/schneider_ups_nmc"


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


async def test_config_flow_uses_password_selectors_for_snmp_secrets(
    hass: HomeAssistant,
) -> None:
    """Use password inputs for SNMP community strings and passphrases."""
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

    data_schema = result.get("data_schema")
    assert data_schema is not None
    assert _schema_selector(data_schema, CONF_COMMUNITY).config["type"] == (
        TextSelectorType.PASSWORD
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
        data={
            CONF_HOST: "192.0.2.11",
            CONF_PORT: 161,
            CONF_SCAN_INTERVAL: 60,
            CONF_SNMP_VERSION: SNMP_VERSION_3,
        },
    )

    data_schema = result.get("data_schema")
    assert data_schema is not None
    assert _schema_selector(data_schema, CONF_AUTH_KEY).config["type"] == (
        TextSelectorType.PASSWORD
    )
    assert _schema_selector(data_schema, CONF_PRIVACY_KEY).config["type"] == (
        TextSelectorType.PASSWORD
    )


@pytest.mark.parametrize(
    ("translation_file", "expected_auth_label", "expected_privacy_label"),
    [
        ("strings.json", "Authentication passphrase", "Privacy passphrase"),
        ("translations/en.json", "Authentication passphrase", "Privacy passphrase"),
    ],
)
def test_snmpv3_secret_labels_match_apc_passphrase_terminology(
    translation_file: str,
    expected_auth_label: str,
    expected_privacy_label: str,
) -> None:
    """Use APC passphrase terminology for user-facing SNMPv3 credentials."""
    translations = json.loads((INTEGRATION_DIR / translation_file).read_text())

    snmpv3_data = translations["config"]["step"]["snmpv3"]["data"]
    errors = translations["config"]["error"]

    assert snmpv3_data[CONF_AUTH_KEY] == expected_auth_label
    assert snmpv3_data[CONF_PRIVACY_KEY] == expected_privacy_label
    assert errors["missing_auth_key"] == f"{expected_auth_label} is required."
    assert errors["missing_privacy_key"] == f"{expected_privacy_label} is required."


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


async def test_reconfigure_flow_updates_entry_and_schedules_reload(
    hass: HomeAssistant,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Update SNMP settings while preserving unrelated entry data."""
    _FakeConfigFlowSNMPClient.instances.clear()
    monkeypatch.setattr(config_flow_module, "SNMPClient", _FakeConfigFlowSNMPClient)
    reload_mock = Mock()
    monkeypatch.setattr(hass.config_entries, "async_schedule_reload", reload_mock)
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Rack UPS",
        unique_id="as1234567890",
        data={
            CONF_HOST: "192.0.2.10",
            CONF_PORT: 161,
            CONF_SCAN_INTERVAL: 60,
            CONF_SNMP_VERSION: SNMP_VERSION_2C,
            CONF_COMMUNITY: "public",
            CONF_USERNAME: "old-user",
            CONF_AUTH_PROTOCOL: AUTH_PROTOCOL_SHA,
            CONF_AUTH_KEY: "old-auth",
            CONF_PRIVACY_PROTOCOL: PRIVACY_PROTOCOL_AES,
            CONF_PRIVACY_KEY: "old-privacy",
            CONF_SYSLOG_ENABLED: True,
            CONF_SYSLOG_BIND_ADDRESS: "0.0.0.0",
            CONF_SYSLOG_PORT: 1514,
        },
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": config_entries.SOURCE_RECONFIGURE,
            "entry_id": entry.entry_id,
        },
    )

    assert result.get("type") is FlowResultType.FORM
    assert result.get("step_id") == "reconfigure"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_HOST: "192.0.2.20",
            CONF_PORT: 1161,
            CONF_SCAN_INTERVAL: 90,
            CONF_SNMP_VERSION: SNMP_VERSION_2C,
        },
    )

    assert result.get("type") is FlowResultType.FORM
    assert result.get("step_id") == "snmpv2c"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_COMMUNITY: "private"},
    )

    assert result.get("type") is FlowResultType.ABORT
    assert result.get("reason") == "reconfigure_successful"
    assert entry.data == {
        CONF_HOST: "192.0.2.20",
        CONF_PORT: 1161,
        CONF_SCAN_INTERVAL: 90,
        CONF_SNMP_VERSION: SNMP_VERSION_2C,
        CONF_COMMUNITY: "private",
        CONF_SYSLOG_ENABLED: True,
        CONF_SYSLOG_BIND_ADDRESS: "0.0.0.0",
        CONF_SYSLOG_PORT: 1514,
    }
    assert _FakeConfigFlowSNMPClient.instances[0].config == SNMPConnectionConfig(
        host="192.0.2.20",
        port=1161,
        version=SNMP_VERSION_2C,
        community="private",
        timeout=2.0,
        retries=1,
    )
    assert _FakeConfigFlowSNMPClient.instances[0].closed
    reload_mock.assert_called_once_with(entry.entry_id)


async def test_reconfigure_flow_rejects_a_different_ups(
    hass: HomeAssistant,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Reject reconfiguration when SNMP identity belongs to another UPS."""
    _DifferentDeviceConfigFlowSNMPClient.instances.clear()
    monkeypatch.setattr(
        config_flow_module,
        "SNMPClient",
        _DifferentDeviceConfigFlowSNMPClient,
    )
    reload_mock = Mock()
    monkeypatch.setattr(hass.config_entries, "async_schedule_reload", reload_mock)
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Rack UPS",
        unique_id="as1234567890",
        data={
            CONF_HOST: "192.0.2.10",
            CONF_PORT: 161,
            CONF_SCAN_INTERVAL: 60,
            CONF_SNMP_VERSION: SNMP_VERSION_2C,
            CONF_COMMUNITY: "public",
        },
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": config_entries.SOURCE_RECONFIGURE,
            "entry_id": entry.entry_id,
        },
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_HOST: "192.0.2.30",
            CONF_PORT: 161,
            CONF_SCAN_INTERVAL: 60,
            CONF_SNMP_VERSION: SNMP_VERSION_2C,
        },
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_COMMUNITY: "public"},
    )

    assert result.get("type") is FlowResultType.ABORT
    assert result.get("reason") == "wrong_device"
    assert entry.data == {
        CONF_HOST: "192.0.2.10",
        CONF_PORT: 161,
        CONF_SCAN_INTERVAL: 60,
        CONF_SNMP_VERSION: SNMP_VERSION_2C,
        CONF_COMMUNITY: "public",
    }
    reload_mock.assert_not_called()


def _schema_selector(data_schema: Any, key: str) -> TextSelector:
    for marker, selector in data_schema.schema.items():
        if getattr(marker, "schema", None) == key:
            assert isinstance(selector, TextSelector)
            return selector
    raise AssertionError(f"schema field not found: {key}")


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


class _DifferentDeviceConfigFlowSNMPClient(_FakeConfigFlowSNMPClient):
    """SNMP client fake that returns a different device identity."""

    instances: ClassVar[list[_DifferentDeviceConfigFlowSNMPClient]] = []

    async def async_get_data(self) -> UPSData:
        """Return identity data for another UPS."""
        return UPSData(
            values={},
            name="Another Rack UPS",
            manufacturer="Schneider Electric",
            model="Smart-UPS 3000",
            serial_number="AS0000000000",
            firmware_version="UPS 15.0 / NMC 3.2.1",
            agent_version="NMC 3.2.1",
            mac_address="00:c0:b7:65:43:21",
            unique_id="as0000000000",
        )
