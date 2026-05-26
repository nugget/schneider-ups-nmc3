"""Home Assistant repair flow tests for APC UPS NMC."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from homeassistant.const import CONF_HOST, CONF_PORT, CONF_SCAN_INTERVAL
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import MockConfigEntry

import custom_components.schneider_ups_nmc as integration
import custom_components.schneider_ups_nmc.repairs as repairs_module
from custom_components.schneider_ups_nmc.const import (
    CONF_COMMUNITY,
    CONF_SNMP_VERSION,
    CONF_SYSLOG_BIND_ADDRESS,
    CONF_SYSLOG_ENABLED,
    CONF_SYSLOG_PORT,
    CONF_WEB_URL,
    DOMAIN,
)
from custom_components.schneider_ups_nmc.coordinator import SYSLOG_PARSE_FAILURE_ISSUE
from custom_components.schneider_ups_nmc.snmp import SNMP_VERSION_2C
from custom_components.schneider_ups_nmc.syslog import (
    DEFAULT_SYSLOG_BIND_ADDRESS,
    DEFAULT_SYSLOG_PORT,
)

if TYPE_CHECKING:
    from homeassistant.components.repairs import RepairsFlow
    from homeassistant.core import HomeAssistant

ENTRY_ID = "01HZZZZZZZZZZZZZZZZZZZZZZZ"
ENTRY_UNIQUE_ID = "ups-test-device"
pytestmark = pytest.mark.usefixtures("enable_custom_integrations")


async def test_syslog_listener_repair_updates_options_and_reloads(
    hass: HomeAssistant,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Update listener options from a fixable syslog listener repair flow."""
    reloads: list[str] = []

    async def async_reload(entry_id: str) -> None:
        """Record the requested config-entry reload."""
        reloads.append(entry_id)

    monkeypatch.setattr(hass.config_entries, "async_reload", async_reload)
    entry = _mock_entry(
        options={
            CONF_SYSLOG_ENABLED: True,
            CONF_SYSLOG_BIND_ADDRESS: DEFAULT_SYSLOG_BIND_ADDRESS,
            CONF_SYSLOG_PORT: DEFAULT_SYSLOG_PORT,
            CONF_WEB_URL: "https://ups.example.test",
        }
    )
    entry.add_to_hass(hass)
    issue_id = f"{integration.SYSLOG_LISTENER_FAILED_ISSUE}_{ENTRY_ID}"
    flow = await repairs_module.async_create_fix_flow(
        hass,
        issue_id,
        {
            "address": "0.0.0.0:1514",
            "entry_id": ENTRY_ID,
            "error": "address already in use",
            "name": "Rack UPS",
        },
    )
    assert isinstance(flow, repairs_module.SyslogListenerRepairFlow)
    _bind_repair_flow(flow, hass, issue_id)

    result = await flow.async_step_init()

    assert result.get("type") is FlowResultType.FORM
    assert result.get("step_id") == "syslog_options"

    result = await flow.async_step_syslog_options(
        {
            CONF_SYSLOG_ENABLED: False,
            CONF_SYSLOG_BIND_ADDRESS: " 127.0.0.1 ",
            CONF_SYSLOG_PORT: 1515,
        }
    )

    assert result.get("type") is FlowResultType.CREATE_ENTRY
    assert entry.options == {
        CONF_SYSLOG_ENABLED: False,
        CONF_SYSLOG_BIND_ADDRESS: "127.0.0.1",
        CONF_SYSLOG_PORT: 1515,
        CONF_WEB_URL: "https://ups.example.test",
    }
    assert reloads == [ENTRY_ID]


async def test_syslog_listener_repair_rejects_invalid_bind_address(
    hass: HomeAssistant,
) -> None:
    """Reject invalid listener bind addresses from the repair flow."""
    entry = _mock_entry()
    entry.add_to_hass(hass)
    issue_id = f"{integration.SYSLOG_LISTENER_CONFLICT_ISSUE}_{ENTRY_ID}"
    flow = await repairs_module.async_create_fix_flow(
        hass,
        issue_id,
        {
            "active": "0.0.0.0:1514",
            "entry_id": ENTRY_ID,
            "name": "Rack UPS",
            "requested": "not-an-ip:1514",
        },
    )
    assert isinstance(flow, repairs_module.SyslogListenerRepairFlow)
    _bind_repair_flow(flow, hass, issue_id)

    result = await flow.async_step_syslog_options(
        {
            CONF_SYSLOG_ENABLED: True,
            CONF_SYSLOG_BIND_ADDRESS: "not-an-ip",
            CONF_SYSLOG_PORT: 1514,
        }
    )

    assert result.get("type") is FlowResultType.FORM
    assert result.get("errors") == {
        CONF_SYSLOG_BIND_ADDRESS: "invalid_syslog_bind_address"
    }


async def test_syslog_parse_failure_repair_disables_syslog(
    hass: HomeAssistant,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Disable syslog from the parse-failure repair flow."""
    reloads: list[str] = []

    async def async_reload(entry_id: str) -> None:
        """Record the requested config-entry reload."""
        reloads.append(entry_id)

    monkeypatch.setattr(hass.config_entries, "async_reload", async_reload)
    entry = _mock_entry(
        options={
            CONF_SYSLOG_ENABLED: True,
            CONF_SYSLOG_BIND_ADDRESS: "0.0.0.0",
            CONF_SYSLOG_PORT: 1514,
        }
    )
    entry.add_to_hass(hass)
    issue_id = f"{SYSLOG_PARSE_FAILURE_ISSUE}_{ENTRY_ID}"
    flow = await repairs_module.async_create_fix_flow(
        hass,
        issue_id,
        {
            "entry_id": ENTRY_ID,
            "error": "Unsupported syslog message format",
            "name": "Rack UPS",
            "source": "192.0.2.10:514",
        },
    )
    assert isinstance(flow, repairs_module.SyslogParseFailureRepairFlow)
    _bind_repair_flow(flow, hass, issue_id)

    result = await flow.async_step_init()

    assert result.get("type") is FlowResultType.FORM
    assert result.get("step_id") == "confirm_disable"
    assert result.get("description_placeholders") == {
        "error": "Unsupported syslog message format",
        "name": "Rack UPS",
        "source": "192.0.2.10:514",
    }

    result = await flow.async_step_confirm_disable({})

    assert result.get("type") is FlowResultType.CREATE_ENTRY
    assert entry.options == {
        CONF_SYSLOG_ENABLED: False,
        CONF_SYSLOG_BIND_ADDRESS: "0.0.0.0",
        CONF_SYSLOG_PORT: 1514,
    }
    assert reloads == [ENTRY_ID]


def _mock_entry(
    *,
    options: dict[str, object] | None = None,
) -> MockConfigEntry:
    """Return a representative config entry for repair tests."""
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


def _bind_repair_flow(
    flow: RepairsFlow,
    hass: HomeAssistant,
    issue_id: str,
) -> None:
    """Attach flow-manager attributes needed by direct repair-flow tests."""
    flow.hass = hass
    flow.handler = DOMAIN
    flow.flow_id = "repair-flow-id"
    flow.issue_id = issue_id
