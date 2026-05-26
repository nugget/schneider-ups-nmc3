"""Home Assistant sensor metadata tests for APC UPS NMC."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

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
from custom_components.schneider_ups_nmc.snmp import (
    BATTERY_REPLACE_INDICATOR_OPTIONS,
    BATTERY_STATUS_OPTIONS,
    INPUT_LINE_FAIL_CAUSE_OPTIONS,
    OUTPUT_SOURCE_OPTIONS,
    SELF_TEST_RESULT_OPTIONS,
    UPS_STATUS_OPTIONS,
)

ROOT = Path(__file__).resolve().parents[1]
ENUM_SENSOR_OPTIONS = {
    "battery_replace_indicator": BATTERY_REPLACE_INDICATOR_OPTIONS,
    "battery_status": BATTERY_STATUS_OPTIONS,
    "input_line_fail_cause": INPUT_LINE_FAIL_CAUSE_OPTIONS,
    "output_source": OUTPUT_SOURCE_OPTIONS,
    "self_test_result": SELF_TEST_RESULT_OPTIONS,
    "ups_status": UPS_STATUS_OPTIONS,
}


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


def test_text_status_sensors_are_enum_metadata() -> None:
    """Text status sensors declare Home Assistant enum metadata."""
    for key, options in ENUM_SENSOR_OPTIONS.items():
        description = _sensor_description(key)

        assert description.device_class == SensorDeviceClass.ENUM
        assert description.options == options
        assert description.native_unit_of_measurement is None
        assert description.state_class is None


def test_text_status_sensor_options_have_state_translations() -> None:
    """Every enum status token has a user-facing state translation."""
    for translation_path in (
        ROOT / "custom_components/schneider_ups_nmc/strings.json",
        ROOT / "custom_components/schneider_ups_nmc/translations/en.json",
    ):
        entity_translations = _load_json(translation_path)["entity"]["sensor"]
        for key, options in ENUM_SENSOR_OPTIONS.items():
            assert set(entity_translations[key]["state"]) == set(options)


def _sensor_description(key: str) -> SchneiderUPSNMCSensorEntityDescription:
    """Return one sensor description by key."""
    descriptions = {
        description.key: description
        for description in SENSOR_DESCRIPTIONS
        if isinstance(description.key, str)
    }
    return descriptions[key]


def _load_json(path: Path) -> dict[str, Any]:
    """Load a JSON object from disk."""
    with path.open(encoding="utf-8") as file:
        data: dict[str, Any] = json.load(file)
    return data
