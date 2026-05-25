"""Event entities for Schneider Electric UPS NMC3."""

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar

from homeassistant.components.event import EventEntity, EventEntityDescription
from homeassistant.core import callback
from homeassistant.helpers.entity import EntityCategory

from .entity import SchneiderUPSNMC3Entity
from .syslog import SYSLOG_EVENT_TYPES, RoutedSyslogEvent, syslog_event_state_data

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddEntitiesCallback

    from . import SchneiderUPSNMC3ConfigEntry
    from .coordinator import SchneiderUPSNMC3Coordinator


SYSLOG_EVENT_DESCRIPTION = EventEntityDescription(
    key="syslog_event",
    translation_key="syslog_event",
    entity_category=EntityCategory.DIAGNOSTIC,
)


async def async_setup_entry(
    _hass: HomeAssistant,
    entry: SchneiderUPSNMC3ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Schneider Electric UPS NMC3 event entities."""
    coordinator: SchneiderUPSNMC3Coordinator = entry.runtime_data
    async_add_entities(
        [SchneiderUPSNMC3SyslogEventEntity(coordinator, SYSLOG_EVENT_DESCRIPTION)]
    )


class SchneiderUPSNMC3SyslogEventEntity(SchneiderUPSNMC3Entity, EventEntity):
    """A Schneider Electric UPS NMC3 syslog event entity."""

    _attr_event_types: ClassVar[list[str]] = list(SYSLOG_EVENT_TYPES)
    entity_description: EventEntityDescription

    async def async_added_to_hass(self) -> None:
        """Register for pushed syslog events."""
        await super().async_added_to_hass()
        self.async_on_remove(
            self.coordinator.async_add_syslog_listener(self._async_handle_syslog_event)
        )

    @callback
    def _async_handle_syslog_event(self, event: RoutedSyslogEvent) -> None:
        """Handle a pushed syslog event."""
        self._trigger_event(event.event.severity, syslog_event_state_data(event))
        self.async_write_ha_state()
