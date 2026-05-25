"""Diagnostics support for Schneider Electric UPS NMC3."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from homeassistant.components.diagnostics import async_redact_data

from .const import (
    CONF_AUTH_KEY,
    CONF_COMMUNITY,
    CONF_PRIVACY_KEY,
    CONF_USERNAME,
    DOMAIN,
)

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant

TO_REDACT = {
    CONF_AUTH_KEY,
    CONF_COMMUNITY,
    CONF_PRIVACY_KEY,
    CONF_USERNAME,
}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    data = coordinator.data

    return {
        "entry": {
            "data": async_redact_data(entry.data, TO_REDACT),
            "options": dict(entry.options),
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
        "available_keys": sorted(data.values.keys()) if data else [],
    }
