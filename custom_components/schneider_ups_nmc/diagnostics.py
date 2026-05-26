"""Diagnostics support for APC UPS NMC."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from homeassistant.components.diagnostics import async_redact_data

from .const import (
    CONF_AUTH_KEY,
    CONF_COMMUNITY,
    CONF_PRIVACY_KEY,
    CONF_USERNAME,
)

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant

    from .coordinator import SchneiderUPSNMCCoordinator
    from .syslog import RoutedSyslogEvent, RoutedSyslogParseFailure

TO_REDACT = {
    CONF_AUTH_KEY,
    CONF_COMMUNITY,
    CONF_PRIVACY_KEY,
    CONF_USERNAME,
}


async def async_get_config_entry_diagnostics(
    _hass: HomeAssistant, entry: ConfigEntry[SchneiderUPSNMCCoordinator]
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator = entry.runtime_data
    data = coordinator.data

    return {
        "entry": {
            "data": async_redact_data(entry.data, TO_REDACT),
            "options": async_redact_data(entry.options, TO_REDACT),
        },
        "last_update_success": coordinator.last_update_success,
        "device": {
            "name": data.name if data else None,
            "manufacturer": data.manufacturer if data else None,
            "model": data.model if data else None,
            "firmware_version": data.firmware_version if data else None,
            "agent_version": data.agent_version if data else None,
            "mac_address": data.mac_address if data else None,
        },
        "last_syslog_event": _routed_syslog_event(coordinator.last_syslog_event),
        "syslog_parse_failures": {
            "count": coordinator.syslog_parse_failure_count,
            "last_failure": _routed_syslog_parse_failure(
                coordinator.last_syslog_parse_failure
            ),
        },
        "available_keys": sorted(data.values.keys()) if data else [],
    }


def _routed_syslog_event(event: RoutedSyslogEvent | None) -> dict[str, Any] | None:
    """Return diagnostic data for the last routed syslog event."""
    if event is None:
        return None

    syslog_event = event.event
    return {
        "source_host": event.source_host,
        "source_port": event.source_port,
        "facility": syslog_event.facility,
        "severity": syslog_event.severity,
        "hostname": syslog_event.hostname,
        "app_name": syslog_event.app_name,
        "event_category": syslog_event.event_category,
        "event_text": syslog_event.event_text,
        "timestamp": syslog_event.timestamp.isoformat(),
    }


def _routed_syslog_parse_failure(
    failure: RoutedSyslogParseFailure | None,
) -> dict[str, Any] | None:
    """Return diagnostic data for the last syslog parse failure."""
    if failure is None:
        return None

    return {
        "source_host": failure.source_host,
        "source_port": failure.source_port,
        "error": failure.error,
    }
