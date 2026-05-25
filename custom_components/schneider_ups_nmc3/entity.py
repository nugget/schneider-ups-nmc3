"""Base entities for Schneider Electric UPS NMC3."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import SchneiderUPSNMC3Coordinator


class SchneiderUPSNMC3Entity(CoordinatorEntity[SchneiderUPSNMC3Coordinator]):
    """Base entity for Schneider Electric UPS NMC3."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: SchneiderUPSNMC3Coordinator,
        description,
    ) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{coordinator.device_id}_{description.key}"

    @property
    def device_info(self) -> DeviceInfo:
        """Return device registry information."""
        data = self.coordinator.data
        return DeviceInfo(
            identifiers={(DOMAIN, self.coordinator.device_id)},
            manufacturer=data.manufacturer if data else "Schneider Electric",
            model=data.model if data else None,
            name=data.name if data else self.coordinator.host,
            serial_number=data.serial_number if data else None,
            sw_version=data.firmware_version if data else None,
        )
