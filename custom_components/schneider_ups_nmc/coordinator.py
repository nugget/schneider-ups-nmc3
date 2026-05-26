"""Data coordinator for APC UPS NMC."""

from __future__ import annotations

import logging
from datetime import timedelta
from typing import TYPE_CHECKING

from homeassistant.const import CONF_HOST, CONF_PORT, CONF_SCAN_INTERVAL
from homeassistant.core import callback
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    CONF_AUTH_KEY,
    CONF_AUTH_PROTOCOL,
    CONF_COMMUNITY,
    CONF_PRIVACY_KEY,
    CONF_PRIVACY_PROTOCOL,
    CONF_SNMP_VERSION,
    CONF_USERNAME,
    CONF_WEB_URL,
    DEFAULT_PORT,
    DEFAULT_RETRIES,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_TIMEOUT,
    DOMAIN,
)
from .snmp import (
    AUTH_PROTOCOL_NONE,
    PRIVACY_PROTOCOL_NONE,
    SNMPClient,
    SNMPConnectionConfig,
    SNMPError,
    UPSData,
)

if TYPE_CHECKING:
    from collections.abc import Callable

    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant

    from .syslog import RoutedSyslogEvent

_LOGGER = logging.getLogger(__name__)


class SchneiderUPSNMCCoordinator(DataUpdateCoordinator[UPSData]):
    """Coordinate data updates for APC UPS NMC."""

    config_entry: ConfigEntry

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize the coordinator."""
        self.client = SNMPClient(_config_from_entry(entry))
        self.device_id = entry.unique_id or (
            f"{entry.data[CONF_HOST]}:{entry.data.get(CONF_PORT, DEFAULT_PORT)}"
        )
        self.host = entry.data[CONF_HOST]
        self.web_url = entry.options.get(CONF_WEB_URL, entry.data.get(CONF_WEB_URL))
        self.last_syslog_event: RoutedSyslogEvent | None = None
        self._syslog_listeners: set[Callable[[RoutedSyslogEvent], None]] = set()

        scan_interval = entry.options.get(
            CONF_SCAN_INTERVAL,
            entry.data.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL),
        )

        super().__init__(
            hass,
            logger=_LOGGER,
            name=DOMAIN,
            config_entry=entry,
            update_interval=timedelta(seconds=int(scan_interval)),
        )

        entry.runtime_data = self

    async def _async_update_data(self) -> UPSData:
        """Fetch data from the UPS."""
        try:
            return await self.client.async_get_data()
        except SNMPError as err:
            raise UpdateFailed(f"SNMP query failed: {err}") from err

    async def async_handle_syslog_event(self, event: RoutedSyslogEvent) -> None:
        """Handle a pushed syslog event from the NMC."""
        self.last_syslog_event = event
        for listener in tuple(self._syslog_listeners):
            try:
                listener(event)
            except Exception:
                _LOGGER.debug(
                    "Failed to notify APC UPS NMC syslog listener",
                    exc_info=True,
                )
        await self.async_request_refresh()

    @callback
    def async_add_syslog_listener(
        self,
        listener: Callable[[RoutedSyslogEvent], None],
    ) -> Callable[[], None]:
        """Add a listener for pushed syslog events."""
        self._syslog_listeners.add(listener)

        def remove_listener() -> None:
            """Remove a pushed syslog event listener."""
            self._syslog_listeners.discard(listener)

        return remove_listener

    def close(self) -> None:
        """Close the SNMP client."""
        self.client.close()


def _config_from_entry(entry: ConfigEntry) -> SNMPConnectionConfig:
    """Build an SNMP connection config from a config entry."""
    return SNMPConnectionConfig(
        host=entry.data[CONF_HOST],
        port=int(entry.data.get(CONF_PORT, DEFAULT_PORT)),
        version=entry.data[CONF_SNMP_VERSION],
        community=entry.data.get(CONF_COMMUNITY),
        username=entry.data.get(CONF_USERNAME),
        auth_protocol=entry.data.get(CONF_AUTH_PROTOCOL, AUTH_PROTOCOL_NONE),
        auth_key=entry.data.get(CONF_AUTH_KEY),
        privacy_protocol=entry.data.get(CONF_PRIVACY_PROTOCOL, PRIVACY_PROTOCOL_NONE),
        privacy_key=entry.data.get(CONF_PRIVACY_KEY),
        timeout=DEFAULT_TIMEOUT,
        retries=DEFAULT_RETRIES,
    )
