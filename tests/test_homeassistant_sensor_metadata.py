"""Home Assistant sensor metadata tests for APC UPS NMC."""

from __future__ import annotations

from homeassistant.components.sensor import SensorDeviceClass, SensorStateClass
from homeassistant.const import (
    PERCENTAGE,
    UnitOfApparentPower,
    UnitOfEnergy,
    UnitOfPower,
)

from custom_components.schneider_ups_nmc.sensor import (
    SENSOR_DESCRIPTIONS,
    SchneiderUPSNMCSensorEntityDescription,
)


def test_output_energy_metadata_supports_energy_dashboard() -> None:
    """Output energy has the metadata Home Assistant Energy expects."""
    description = _sensor_description("output_energy")

    assert description.device_class == SensorDeviceClass.ENERGY
    assert description.native_unit_of_measurement == UnitOfEnergy.KILO_WATT_HOUR
    assert description.state_class == SensorStateClass.TOTAL_INCREASING
    assert description.suggested_display_precision == 2


def test_output_power_metadata_supports_energy_helpers() -> None:
    """Output power has the metadata needed for power-derived energy helpers."""
    description = _sensor_description("output_power")

    assert description.device_class == SensorDeviceClass.POWER
    assert description.native_unit_of_measurement == UnitOfPower.WATT
    assert description.state_class == SensorStateClass.MEASUREMENT
    assert description.suggested_display_precision == 0


def test_output_power_quality_metadata_uses_specific_device_classes() -> None:
    """Apparent power and power factor use Home Assistant power-quality classes."""
    apparent_power = _sensor_description("output_apparent_power")
    power_factor = _sensor_description("output_power_factor")

    assert apparent_power.device_class == SensorDeviceClass.APPARENT_POWER
    assert apparent_power.native_unit_of_measurement == UnitOfApparentPower.VOLT_AMPERE
    assert apparent_power.state_class == SensorStateClass.MEASUREMENT
    assert apparent_power.suggested_display_precision == 0

    assert power_factor.device_class == SensorDeviceClass.POWER_FACTOR
    assert power_factor.native_unit_of_measurement == PERCENTAGE
    assert power_factor.state_class == SensorStateClass.MEASUREMENT
    assert power_factor.suggested_display_precision == 1


def _sensor_description(key: str) -> SchneiderUPSNMCSensorEntityDescription:
    """Return one sensor description by key."""
    descriptions = {
        description.key: description
        for description in SENSOR_DESCRIPTIONS
        if isinstance(description.key, str)
    }
    return descriptions[key]
