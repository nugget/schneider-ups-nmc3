"""Schneider Electric UPS NMC3 integration."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN, PLATFORMS
from .coordinator import SchneiderUPSNMC3Coordinator

SchneiderUPSNMC3ConfigEntry = ConfigEntry[SchneiderUPSNMC3Coordinator]


async def async_setup_entry(
    hass: HomeAssistant, entry: SchneiderUPSNMC3ConfigEntry
) -> bool:
    """Set up Schneider Electric UPS NMC3 from a config entry."""
    coordinator = SchneiderUPSNMC3Coordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(async_reload_entry))

    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: SchneiderUPSNMC3ConfigEntry
) -> bool:
    """Unload a Schneider Electric UPS NMC3 config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        coordinator: SchneiderUPSNMC3Coordinator = hass.data[DOMAIN].pop(entry.entry_id)
        coordinator.close()

    return unload_ok


async def async_reload_entry(
    hass: HomeAssistant, entry: SchneiderUPSNMC3ConfigEntry
) -> None:
    """Reload a Schneider Electric UPS NMC3 config entry."""
    await async_unload_entry(hass, entry)
    await async_setup_entry(hass, entry)
