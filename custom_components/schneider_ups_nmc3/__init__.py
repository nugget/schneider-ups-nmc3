"""Schneider Electric UPS NMC3 integration."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from homeassistant.config_entries import ConfigEntry

from .const import DOMAIN, PLATFORMS, SYSLOG_MANAGER
from .coordinator import SchneiderUPSNMC3Coordinator
from .syslog import SyslogPushManager

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)

type SchneiderUPSNMC3ConfigEntry = ConfigEntry[SchneiderUPSNMC3Coordinator]


async def async_setup_entry(
    hass: HomeAssistant, entry: SchneiderUPSNMC3ConfigEntry
) -> bool:
    """Set up Schneider Electric UPS NMC3 from a config entry."""
    coordinator = SchneiderUPSNMC3Coordinator(hass, entry)
    try:
        await coordinator.async_config_entry_first_refresh()
    except Exception:
        coordinator.close()
        raise

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    await _async_register_syslog(hass, entry, coordinator)
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


async def _async_register_syslog(
    hass: HomeAssistant,
    entry: SchneiderUPSNMC3ConfigEntry,
    coordinator: SchneiderUPSNMC3Coordinator,
) -> None:
    """Register a config entry with the shared syslog listener."""
    manager = _syslog_manager(hass)
    try:
        unregister = await manager.async_register(coordinator)
    except OSError as err:
        _LOGGER.warning(
            "Could not start Schneider UPS NMC3 syslog listener: %s",
            err,
        )
        return

    entry.async_on_unload(unregister)


def _syslog_manager(hass: HomeAssistant) -> SyslogPushManager:
    """Return the shared syslog push manager."""
    domain_data = hass.data.setdefault(DOMAIN, {})
    manager = domain_data.get(SYSLOG_MANAGER)
    if not isinstance(manager, SyslogPushManager):
        manager = SyslogPushManager(hass)
        domain_data[SYSLOG_MANAGER] = manager

    return manager
