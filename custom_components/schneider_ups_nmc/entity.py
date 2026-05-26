"""Base entities for APC UPS NMC."""

from __future__ import annotations

from ipaddress import IPv6Address, ip_address
from typing import TYPE_CHECKING
from urllib.parse import quote

from homeassistant.helpers.device_registry import (
    CONNECTION_NETWORK_MAC,
    DeviceInfo,
    format_mac,
)
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import SchneiderUPSNMCCoordinator

if TYPE_CHECKING:
    from homeassistant.helpers.entity import EntityDescription


class SchneiderUPSNMCEntity(CoordinatorEntity[SchneiderUPSNMCCoordinator]):
    """Base entity for APC UPS NMC."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: SchneiderUPSNMCCoordinator,
        description: EntityDescription,
    ) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{coordinator.device_id}_{description.key}"

    @property
    def device_info(self) -> DeviceInfo:
        """Return device registry information."""
        data = self.coordinator.data
        device_info = DeviceInfo(
            configuration_url=_configuration_url(
                self.coordinator.host,
                self.coordinator.web_url,
            ),
            identifiers={(DOMAIN, self.coordinator.device_id)},
            manufacturer=data.manufacturer if data else "Schneider Electric",
            model=data.model if data else None,
            name=data.name if data else self.coordinator.host,
            serial_number=data.serial_number if data else None,
            sw_version=data.firmware_version if data else None,
        )
        if data and data.mac_address:
            device_info["connections"] = {
                (CONNECTION_NETWORK_MAC, format_mac(data.mac_address))
            }

        return device_info


def _configuration_url(host: str, web_url: str | None = None) -> str:
    """Return the NMC web configuration URL for a host."""
    if web_url:
        return _explicit_configuration_url(web_url)

    try:
        address = ip_address(host)
    except ValueError:
        return f"http://{host}"

    if isinstance(address, IPv6Address):
        host_text = address.compressed
        if address.scope_id:
            address_text = host_text[: -(len(address.scope_id) + 1)]
            host_text = f"{address_text}%25{quote(address.scope_id, safe='')}"
        return f"http://[{host_text}]"
    return f"http://{address}"


def _explicit_configuration_url(web_url: str) -> str:
    """Return an absolute explicit NMC web configuration URL."""
    normalized_url = web_url.strip()
    if "://" not in normalized_url:
        normalized_url = f"https://{normalized_url}"

    return normalized_url
