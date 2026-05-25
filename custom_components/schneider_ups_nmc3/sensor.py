"""Sensors for Schneider Electric UPS NMC3."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    PERCENTAGE,
    EntityCategory,
    UnitOfApparentPower,
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfEnergy,
    UnitOfFrequency,
    UnitOfPower,
    UnitOfTemperature,
    UnitOfTime,
)

from .entity import SchneiderUPSNMC3Entity

if TYPE_CHECKING:
    from collections.abc import Callable

    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddEntitiesCallback

    from . import SchneiderUPSNMC3ConfigEntry
    from .coordinator import SchneiderUPSNMC3Coordinator
    from .snmp import UPSData


@dataclass(frozen=True, kw_only=True)
class SchneiderUPSNMC3SensorEntityDescription(SensorEntityDescription):
    """Describe a Schneider Electric UPS NMC3 sensor."""

    value_fn: Callable[[UPSData], Any]


def _value(key: str) -> Callable[[UPSData], Any]:
    """Return a value getter for a data key."""

    def get_value(data: UPSData) -> Any:
        return data.value(key)

    return get_value


SENSOR_DESCRIPTIONS: tuple[SchneiderUPSNMC3SensorEntityDescription, ...] = (
    SchneiderUPSNMC3SensorEntityDescription(
        key="battery_status",
        translation_key="battery_status",
        value_fn=_value("battery_status"),
    ),
    SchneiderUPSNMC3SensorEntityDescription(
        key="ups_status",
        translation_key="ups_status",
        value_fn=_value("ups_status"),
    ),
    SchneiderUPSNMC3SensorEntityDescription(
        key="battery_charge",
        translation_key="battery_charge",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.BATTERY,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=_value("battery_charge"),
    ),
    SchneiderUPSNMC3SensorEntityDescription(
        key="estimated_runtime",
        translation_key="estimated_runtime",
        native_unit_of_measurement=UnitOfTime.SECONDS,
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=_value("estimated_runtime"),
    ),
    SchneiderUPSNMC3SensorEntityDescription(
        key="seconds_on_battery",
        translation_key="seconds_on_battery",
        native_unit_of_measurement=UnitOfTime.SECONDS,
        device_class=SensorDeviceClass.DURATION,
        entity_registry_enabled_default=False,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=_value("seconds_on_battery"),
    ),
    SchneiderUPSNMC3SensorEntityDescription(
        key="battery_voltage",
        translation_key="battery_voltage",
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=_value("battery_voltage"),
    ),
    SchneiderUPSNMC3SensorEntityDescription(
        key="battery_current",
        translation_key="battery_current",
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        device_class=SensorDeviceClass.CURRENT,
        entity_registry_enabled_default=False,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=_value("battery_current"),
    ),
    SchneiderUPSNMC3SensorEntityDescription(
        key="battery_temperature",
        translation_key="battery_temperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=_value("battery_temperature"),
    ),
    SchneiderUPSNMC3SensorEntityDescription(
        key="battery_replace_indicator",
        translation_key="battery_replace_indicator",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=_value("battery_replace_indicator"),
    ),
    SchneiderUPSNMC3SensorEntityDescription(
        key="battery_pack_count",
        translation_key="battery_pack_count",
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=_value("battery_pack_count"),
    ),
    SchneiderUPSNMC3SensorEntityDescription(
        key="battery_internal_sku",
        translation_key="battery_internal_sku",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=_value("battery_internal_sku"),
    ),
    SchneiderUPSNMC3SensorEntityDescription(
        key="battery_external_sku",
        translation_key="battery_external_sku",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=_value("battery_external_sku"),
    ),
    SchneiderUPSNMC3SensorEntityDescription(
        key="battery_last_replace_date",
        translation_key="battery_last_replace_date",
        device_class=SensorDeviceClass.DATE,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=_value("battery_last_replace_date"),
    ),
    SchneiderUPSNMC3SensorEntityDescription(
        key="battery_recommended_replace_date",
        translation_key="battery_recommended_replace_date",
        device_class=SensorDeviceClass.DATE,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=_value("battery_recommended_replace_date"),
    ),
    SchneiderUPSNMC3SensorEntityDescription(
        key="input_voltage",
        translation_key="input_voltage",
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=_value("input_voltage"),
    ),
    SchneiderUPSNMC3SensorEntityDescription(
        key="input_frequency",
        translation_key="input_frequency",
        native_unit_of_measurement=UnitOfFrequency.HERTZ,
        device_class=SensorDeviceClass.FREQUENCY,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=_value("input_frequency"),
    ),
    SchneiderUPSNMC3SensorEntityDescription(
        key="input_current",
        translation_key="input_current",
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        device_class=SensorDeviceClass.CURRENT,
        entity_registry_enabled_default=False,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=_value("input_current"),
    ),
    SchneiderUPSNMC3SensorEntityDescription(
        key="input_power",
        translation_key="input_power",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        entity_registry_enabled_default=False,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=_value("input_power"),
    ),
    SchneiderUPSNMC3SensorEntityDescription(
        key="input_line_fail_cause",
        translation_key="input_line_fail_cause",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=_value("input_line_fail_cause"),
    ),
    SchneiderUPSNMC3SensorEntityDescription(
        key="output_source",
        translation_key="output_source",
        value_fn=_value("output_source"),
    ),
    SchneiderUPSNMC3SensorEntityDescription(
        key="output_voltage",
        translation_key="output_voltage",
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=_value("output_voltage"),
    ),
    SchneiderUPSNMC3SensorEntityDescription(
        key="output_frequency",
        translation_key="output_frequency",
        native_unit_of_measurement=UnitOfFrequency.HERTZ,
        device_class=SensorDeviceClass.FREQUENCY,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=_value("output_frequency"),
    ),
    SchneiderUPSNMC3SensorEntityDescription(
        key="output_current",
        translation_key="output_current",
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        device_class=SensorDeviceClass.CURRENT,
        entity_registry_enabled_default=False,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=_value("output_current"),
    ),
    SchneiderUPSNMC3SensorEntityDescription(
        key="output_power",
        translation_key="output_power",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=_value("output_power"),
    ),
    SchneiderUPSNMC3SensorEntityDescription(
        key="output_apparent_power",
        translation_key="output_apparent_power",
        native_unit_of_measurement=UnitOfApparentPower.VOLT_AMPERE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=_value("output_apparent_power"),
    ),
    SchneiderUPSNMC3SensorEntityDescription(
        key="output_load",
        translation_key="output_load",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=_value("output_load"),
    ),
    SchneiderUPSNMC3SensorEntityDescription(
        key="output_efficiency",
        translation_key="output_efficiency",
        native_unit_of_measurement=PERCENTAGE,
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=_value("output_efficiency"),
    ),
    SchneiderUPSNMC3SensorEntityDescription(
        key="output_energy",
        translation_key="output_energy",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=_value("output_energy"),
    ),
    SchneiderUPSNMC3SensorEntityDescription(
        key="alarm_count",
        translation_key="alarm_count",
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=_value("alarm_count"),
    ),
    SchneiderUPSNMC3SensorEntityDescription(
        key="input_line_bads",
        translation_key="input_line_bads",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=_value("input_line_bads"),
    ),
    SchneiderUPSNMC3SensorEntityDescription(
        key="self_test_result",
        translation_key="self_test_result",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=_value("self_test_result"),
    ),
    SchneiderUPSNMC3SensorEntityDescription(
        key="self_test_last_date",
        translation_key="self_test_last_date",
        device_class=SensorDeviceClass.DATE,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=_value("self_test_last_date"),
    ),
)


async def async_setup_entry(
    _hass: HomeAssistant,
    entry: SchneiderUPSNMC3ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Schneider Electric UPS NMC3 sensors."""
    coordinator: SchneiderUPSNMC3Coordinator = entry.runtime_data
    async_add_entities(
        SchneiderUPSNMC3SensorEntity(coordinator, description)
        for description in SENSOR_DESCRIPTIONS
    )


class SchneiderUPSNMC3SensorEntity(SchneiderUPSNMC3Entity, SensorEntity):
    """A Schneider Electric UPS NMC3 sensor."""

    entity_description: SchneiderUPSNMC3SensorEntityDescription

    @property
    def available(self) -> bool:
        """Return whether the sensor has a fresh value."""
        return (
            super().available
            and self.coordinator.data is not None
            and self.entity_description.value_fn(self.coordinator.data) is not None
        )

    @property
    def native_value(self) -> Any:
        """Return the sensor state."""
        if self.coordinator.data is None:
            return None

        return self.entity_description.value_fn(self.coordinator.data)
