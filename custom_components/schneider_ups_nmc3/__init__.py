"""Schneider Electric UPS NMC3 integration."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from homeassistant.config_entries import ConfigEntry

from .const import (
    CONF_SYSLOG_BIND_ADDRESS,
    CONF_SYSLOG_ENABLED,
    CONF_SYSLOG_PORT,
    DOMAIN,
    PLATFORMS,
    SYSLOG_MANAGER,
)
from .coordinator import SchneiderUPSNMC3Coordinator
from .syslog import (
    DEFAULT_SYSLOG_BIND_ADDRESS,
    DEFAULT_SYSLOG_ENABLED,
    DEFAULT_SYSLOG_PORT,
    SyslogPushManager,
)

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
    if not bool(
        entry.options.get(
            CONF_SYSLOG_ENABLED,
            entry.data.get(CONF_SYSLOG_ENABLED, DEFAULT_SYSLOG_ENABLED),
        )
    ):
        _LOGGER.debug("Schneider UPS NMC3 syslog listener disabled for %s", entry.title)
        return

    bind_address = str(
        entry.options.get(
            CONF_SYSLOG_BIND_ADDRESS,
            entry.data.get(CONF_SYSLOG_BIND_ADDRESS, DEFAULT_SYSLOG_BIND_ADDRESS),
        )
    )
    port = int(
        entry.options.get(
            CONF_SYSLOG_PORT,
            entry.data.get(CONF_SYSLOG_PORT, DEFAULT_SYSLOG_PORT),
        )
    )
    manager = _syslog_manager(hass, bind_address=bind_address, port=port)
    if not manager.is_configured_for(bind_address, port):
        _LOGGER.warning(
            (
                "Could not register Schneider UPS NMC3 syslog listener for %s "
                "on %s:%s because the shared listener is already using %s:%s"
            ),
            entry.title,
            bind_address,
            port,
            manager.bind_address,
            manager.port,
        )
        return

    try:
        unregister = await manager.async_register(coordinator)
    except OSError as err:
        _LOGGER.warning(
            "Could not start Schneider UPS NMC3 syslog listener on %s:%s: %s",
            manager.bind_address,
            manager.port,
            err,
        )
        return

    entry.async_on_unload(unregister)


def _syslog_manager(
    hass: HomeAssistant,
    *,
    bind_address: str,
    port: int,
) -> SyslogPushManager:
    """Return the shared syslog push manager."""
    domain_data = hass.data.setdefault(DOMAIN, {})
    manager = domain_data.get(SYSLOG_MANAGER)
    if isinstance(manager, SyslogPushManager):
        if manager.is_configured_for(bind_address, port):
            return manager
        if not manager.is_idle:
            return manager
        manager.close()

    manager = SyslogPushManager(hass, bind_address=bind_address, port=port)
    domain_data[SYSLOG_MANAGER] = manager

    return manager
