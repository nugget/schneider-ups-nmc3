"""APC UPS NMC integration."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers import issue_registry as ir

from .const import (
    CONF_SYSLOG_BIND_ADDRESS,
    CONF_SYSLOG_ENABLED,
    CONF_SYSLOG_PORT,
    DOMAIN,
    PLATFORMS,
    SYSLOG_MANAGER,
)
from .coordinator import SYSLOG_PARSE_FAILURE_ISSUE, SchneiderUPSNMCCoordinator
from .syslog import (
    DEFAULT_SYSLOG_BIND_ADDRESS,
    DEFAULT_SYSLOG_ENABLED,
    DEFAULT_SYSLOG_PORT,
    SyslogPushManager,
)

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)
SYSLOG_LISTENER_CONFLICT_ISSUE = "syslog_listener_conflict"
SYSLOG_LISTENER_FAILED_ISSUE = "syslog_listener_failed"

type SchneiderUPSNMCConfigEntry = ConfigEntry[SchneiderUPSNMCCoordinator]


async def async_setup_entry(
    hass: HomeAssistant, entry: SchneiderUPSNMCConfigEntry
) -> bool:
    """Set up APC UPS NMC from a config entry."""
    coordinator = SchneiderUPSNMCCoordinator(hass, entry)
    try:
        await coordinator.async_config_entry_first_refresh()
    except Exception:
        coordinator.close()
        raise

    entry.runtime_data = coordinator
    try:
        await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
        await _async_register_syslog(hass, entry, coordinator)
    except Exception:
        coordinator.close()
        del entry.runtime_data
        raise

    entry.async_on_unload(entry.add_update_listener(_async_update_listener))

    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: SchneiderUPSNMCConfigEntry
) -> bool:
    """Unload an APC UPS NMC config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        entry.runtime_data.close()

    return unload_ok


async def _async_update_listener(
    hass: HomeAssistant, entry: SchneiderUPSNMCConfigEntry
) -> None:
    """Reload an APC UPS NMC config entry after options change."""
    await hass.config_entries.async_reload(entry.entry_id)


async def _async_register_syslog(
    hass: HomeAssistant,
    entry: SchneiderUPSNMCConfigEntry,
    coordinator: SchneiderUPSNMCCoordinator,
) -> None:
    """Register a config entry with the shared syslog listener."""
    if not bool(
        entry.options.get(
            CONF_SYSLOG_ENABLED,
            entry.data.get(CONF_SYSLOG_ENABLED, DEFAULT_SYSLOG_ENABLED),
        )
    ):
        _LOGGER.debug("APC UPS NMC syslog listener disabled for %s", entry.title)
        _delete_syslog_issues(hass, entry)
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
                "Could not register APC UPS NMC syslog listener for %s "
                "on %s:%s because the shared listener is already using %s:%s"
            ),
            entry.title,
            bind_address,
            port,
            manager.bind_address,
            manager.port,
        )
        _create_syslog_listener_conflict_issue(
            hass,
            entry,
            requested=f"{bind_address}:{port}",
            active=f"{manager.bind_address}:{manager.port}",
        )
        return

    try:
        unregister = await manager.async_register(coordinator)
    except OSError as err:
        _LOGGER.warning(
            "Could not start APC UPS NMC syslog listener on %s:%s: %s",
            manager.bind_address,
            manager.port,
            err,
        )
        _create_syslog_listener_failed_issue(
            hass,
            entry,
            address=f"{manager.bind_address}:{manager.port}",
            error=str(err),
        )
        return

    _delete_syslog_issues(hass, entry)
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


def _create_syslog_listener_conflict_issue(
    hass: HomeAssistant,
    entry: SchneiderUPSNMCConfigEntry,
    *,
    requested: str,
    active: str,
) -> None:
    """Create a repair issue for conflicting shared syslog listener options."""
    ir.async_create_issue(
        hass,
        DOMAIN,
        _syslog_issue_id(entry, SYSLOG_LISTENER_CONFLICT_ISSUE),
        is_fixable=False,
        issue_domain=DOMAIN,
        severity=ir.IssueSeverity.ERROR,
        translation_key=SYSLOG_LISTENER_CONFLICT_ISSUE,
        translation_placeholders={
            "active": active,
            "name": entry.title,
            "requested": requested,
        },
    )
    _delete_syslog_issue(hass, entry, SYSLOG_LISTENER_FAILED_ISSUE)


def _create_syslog_listener_failed_issue(
    hass: HomeAssistant,
    entry: SchneiderUPSNMCConfigEntry,
    *,
    address: str,
    error: str,
) -> None:
    """Create a repair issue for syslog listener startup failures."""
    ir.async_create_issue(
        hass,
        DOMAIN,
        _syslog_issue_id(entry, SYSLOG_LISTENER_FAILED_ISSUE),
        is_fixable=False,
        issue_domain=DOMAIN,
        severity=ir.IssueSeverity.ERROR,
        translation_key=SYSLOG_LISTENER_FAILED_ISSUE,
        translation_placeholders={
            "address": address,
            "error": error,
            "name": entry.title,
        },
    )
    _delete_syslog_issue(hass, entry, SYSLOG_LISTENER_CONFLICT_ISSUE)


def _delete_syslog_issues(
    hass: HomeAssistant,
    entry: SchneiderUPSNMCConfigEntry,
) -> None:
    """Delete stale syslog repair issues for a config entry."""
    _delete_syslog_issue(hass, entry, SYSLOG_LISTENER_CONFLICT_ISSUE)
    _delete_syslog_issue(hass, entry, SYSLOG_LISTENER_FAILED_ISSUE)
    _delete_syslog_issue(hass, entry, SYSLOG_PARSE_FAILURE_ISSUE)


def _delete_syslog_issue(
    hass: HomeAssistant,
    entry: SchneiderUPSNMCConfigEntry,
    issue: str,
) -> None:
    """Delete one syslog listener repair issue for a config entry."""
    ir.async_delete_issue(hass, DOMAIN, _syslog_issue_id(entry, issue))


def _syslog_issue_id(
    entry: SchneiderUPSNMCConfigEntry,
    issue: str,
) -> str:
    """Return the per-entry syslog listener repair issue ID."""
    return f"{issue}_{entry.entry_id}"
