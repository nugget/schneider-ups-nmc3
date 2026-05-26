"""Tests for APC UPS NMC SNMP normalization."""

from __future__ import annotations

import asyncio
import threading
import unittest
import warnings
from datetime import date
from typing import TYPE_CHECKING

from custom_components.schneider_ups_nmc import snmp

if TYPE_CHECKING:
    from collections.abc import Sequence


class BuildUPSDataTest(unittest.TestCase):
    """Test SNMP value normalization."""

    def test_normalizes_rfc1628_values(self) -> None:
        """RFC1628 integer values become Home Assistant-friendly units."""
        data = snmp.build_ups_data(
            {
                "sys_name": "rack-ups",
                "manufacturer": "Schneider Electric",
                "model": "Smart-UPS 1500",
                "firmware_version": "UPS 10.0",
                "agent_version": "NMC3 3.1.0",
                "battery_status_code": 2,
                "seconds_on_battery": 0,
                "estimated_runtime_minutes": 42,
                "battery_charge": 97,
                "battery_voltage_tenths": 273,
                "battery_current_tenths": -4,
                "battery_temperature": 25,
                "input_frequency_tenths": 600,
                "input_voltage": 121,
                "input_current_tenths": 12,
                "input_power": 144,
                "output_source_code": 3,
                "output_frequency_tenths": 600,
                "output_voltage": 120,
                "output_current_tenths": 11,
                "output_power": 132,
                "output_load": 18,
                "alarm_count": 0,
            },
            fallback_unique_id="192.0.2.10:161",
        )

        self.assertEqual(data.name, "rack-ups")
        self.assertEqual(data.model, "Smart-UPS 1500")
        self.assertEqual(data.unique_id, "rack_ups")
        self.assertEqual(data.value("battery_status"), "normal")
        self.assertEqual(data.value("estimated_runtime"), 2520)
        self.assertEqual(data.value("battery_voltage"), 27.3)
        self.assertEqual(data.value("battery_current"), -0.4)
        self.assertEqual(data.value("input_frequency"), 60.0)
        self.assertEqual(data.value("input_current"), 1.2)
        self.assertEqual(data.value("output_source"), "normal")
        self.assertEqual(data.value("output_frequency"), 60.0)
        self.assertEqual(data.value("output_current"), 1.1)

    def test_uses_powernet_identity_fallbacks(self) -> None:
        """APC PowerNet identity fields supplement RFC1628 identity."""
        data = snmp.build_ups_data(
            {
                "sys_name": "rack-ups",
                "apc_model": "SRTL1500RMXLA",
                "apc_serial_number": "AS1234567890",
                "apc_firmware_version": "UPS 15.0 / NMC 3.2.1",
            }
        )

        self.assertEqual(data.model, "SRTL1500RMXLA")
        self.assertEqual(data.serial_number, "AS1234567890")
        self.assertEqual(data.firmware_version, "UPS 15.0 / NMC 3.2.1")
        self.assertEqual(data.unique_id, "as1234567890")

    def test_normalizes_mac_address(self) -> None:
        """Management card MAC addresses are normalized for HA device matching."""
        data = snmp.build_ups_data(
            {
                "sys_name": "rack-ups",
                "mac_address": "00 C0 B7 12 34 56",
            }
        )

        self.assertEqual(data.mac_address, "00:c0:b7:12:34:56")
        self.assertNotIn("mac_address", data.values)

    def test_snmpv2c_missing_community_is_configuration_error(self) -> None:
        """Missing local SNMPv2c credentials produce a configuration error."""
        client = snmp.SNMPClient(
            snmp.SNMPConnectionConfig(
                host="192.0.2.10",
                version=snmp.SNMP_VERSION_2C,
            )
        )

        with self.assertRaisesRegex(
            snmp.SNMPConfigurationError,
            "SNMPv2c community is required",
        ):
            client._auth_data()

    def test_snmpv3_missing_auth_key_is_configuration_error(self) -> None:
        """Missing local SNMPv3 credentials produce a configuration error."""
        client = snmp.SNMPClient(
            snmp.SNMPConnectionConfig(
                host="192.0.2.10",
                version=snmp.SNMP_VERSION_3,
                username="ups-user",
                auth_protocol=snmp.AUTH_PROTOCOL_SHA,
                privacy_protocol=snmp.PRIVACY_PROTOCOL_NONE,
            )
        )

        with self.assertRaises(snmp.SNMPConfigurationError):
            client._auth_data()

    def test_async_get_batches_large_oid_sets(self) -> None:
        """Large pull requests are split into bounded SNMP GET batches."""

        class FakeSNMPClient(snmp.SNMPClient):
            """SNMP client that records low-level batch requests."""

            def __init__(self) -> None:
                """Initialize the fake client."""
                super().__init__(snmp.SNMPConnectionConfig(host="192.0.2.10"))
                self.batches: list[tuple[str, ...]] = []

            async def _async_get_batch(self, oids: Sequence[str]) -> dict[str, str]:
                """Return values for one fake batch."""
                self.batches.append(tuple(oids))
                return {oid: f"value-{oid}" for oid in oids}

        client = FakeSNMPClient()
        oids = tuple(f"1.3.6.1.2.1.1.{index}.0" for index in range(25))

        values = asyncio.run(client.async_get(oids))

        expected_batch_sizes = [
            len(oids[index : index + snmp.GET_BATCH_SIZE])
            for index in range(0, len(oids), snmp.GET_BATCH_SIZE)
        ]
        self.assertEqual(
            [len(batch) for batch in client.batches],
            expected_batch_sizes,
        )
        self.assertEqual(values[oids[0]], f"value-{oids[0]}")
        self.assertEqual(values[oids[-1]], f"value-{oids[-1]}")

    def test_concurrent_snmp_engine_calls_share_threaded_creation(self) -> None:
        """Concurrent PySNMP engine startup runs once outside the event loop."""

        class FakeSNMPClient(snmp.SNMPClient):
            """SNMP client that records where its engine is created."""

            def __init__(self) -> None:
                """Initialize the fake client."""
                super().__init__(snmp.SNMPConnectionConfig(host="192.0.2.10"))
                self.creation_started = threading.Event()
                self.release_creation = threading.Event()
                self.engine_thread: int | None = None
                self.create_count = 0

            def _create_snmp_engine(self) -> object:
                """Record the thread used for PySNMP engine initialization."""
                self.create_count += 1
                self.engine_thread = threading.get_ident()
                self.creation_started.set()
                if not self.release_creation.wait(timeout=1.0):
                    raise TimeoutError("test did not release SNMP engine creation")
                return object()

        async def get_engine(client: FakeSNMPClient) -> object:
            """Return the lazily created SNMP engine."""
            return await client._async_engine()

        client = FakeSNMPClient()
        event_loop_thread: int | None = None

        async def run_probe() -> tuple[object, object]:
            """Create and reuse the SNMP engine from concurrent tasks."""
            nonlocal event_loop_thread
            event_loop_thread = threading.get_ident()
            first_task = asyncio.create_task(get_engine(client))
            second_task = asyncio.create_task(get_engine(client))
            self.assertTrue(await asyncio.to_thread(client.creation_started.wait, 1.0))
            client.release_creation.set()
            first_engine, second_engine = await asyncio.gather(
                first_task,
                second_task,
            )
            return first_engine, second_engine

        first_engine, second_engine = asyncio.run(run_probe())

        self.assertIs(first_engine, second_engine)
        self.assertEqual(client.create_count, 1)
        self.assertIsNotNone(client.engine_thread)
        self.assertIsNotNone(event_loop_thread)
        self.assertNotEqual(client.engine_thread, event_loop_thread)

    def test_closes_engine_created_after_client_close(self) -> None:
        """Close an engine that finishes startup after the client closes."""

        class FakeEngine:
            """SNMP engine that records dispatcher closure."""

            def __init__(self) -> None:
                """Initialize the fake engine."""
                self.closed = False

            def close_dispatcher(self) -> None:
                """Record that the engine dispatcher was closed."""
                self.closed = True

        class FakeSNMPClient(snmp.SNMPClient):
            """SNMP client that blocks engine creation for close-race testing."""

            def __init__(self) -> None:
                """Initialize the fake client."""
                super().__init__(snmp.SNMPConnectionConfig(host="192.0.2.10"))
                self.creation_started = threading.Event()
                self.release_creation = threading.Event()
                self.created_engine: FakeEngine | None = None

            def _create_snmp_engine(self) -> FakeEngine:
                """Create a fake engine after the test releases startup."""
                self.creation_started.set()
                if not self.release_creation.wait(timeout=1.0):
                    raise TimeoutError("test did not release SNMP engine creation")
                self.created_engine = FakeEngine()
                return self.created_engine

        client = FakeSNMPClient()

        async def run_probe() -> None:
            """Close the client while engine creation is still in flight."""
            engine_task = asyncio.create_task(client._async_engine())
            self.assertTrue(await asyncio.to_thread(client.creation_started.wait, 1.0))
            client.close()
            client.release_creation.set()
            with self.assertRaises(snmp.SNMPError):
                await engine_task

        asyncio.run(run_probe())

        created_engine = client.created_engine
        self.assertIsNotNone(created_engine)
        assert created_engine is not None
        self.assertTrue(created_engine.closed)
        self.assertIsNone(client._snmp_engine)

    def test_async_get_data_tolerates_mac_walk_failure(self) -> None:
        """Main UPS pulls still succeed when optional IF-MIB discovery fails."""

        class FakeSNMPClient(snmp.SNMPClient):
            """SNMP client that returns identity data but no MAC address."""

            async def async_get(self, oids: Sequence[str]) -> dict[str, str | None]:
                """Return fake raw values for the requested OIDs."""
                return {
                    oid: (
                        "rack-ups"
                        if oid
                        in {
                            snmp.RFC1628_OIDS["sys_name"],
                            snmp.RFC1628_OIDS["ups_name"],
                        }
                        else None
                    )
                    for oid in oids
                }

            async def async_get_mac_address(self) -> str | None:
                """Raise an optional IF-MIB discovery error."""
                raise snmp.SNMPError("IF-MIB unavailable")

        client = FakeSNMPClient(snmp.SNMPConnectionConfig(host="192.0.2.10"))

        data = asyncio.run(client.async_get_data())

        self.assertEqual(data.name, "rack-ups")
        self.assertEqual(data.mac_address, None)

    def test_normalizes_powernet_values(self) -> None:
        """PowerNet values prefer high-precision NMC fields."""
        data = snmp.build_ups_data(
            {
                "powernet_battery_status_code": 2,
                "powernet_battery_charge_tenths": 997,
                "powernet_battery_temperature_tenths": 224,
                "powernet_battery_voltage_tenths": 1302,
                "battery_replace_indicator_code": 1,
                "battery_last_replace_date_raw": "04/07/2022",
                "battery_recommended_replace_date_raw": "07/24/2027",
                "powernet_input_voltage_tenths": 1234,
                "powernet_input_frequency_tenths": 600,
                "input_line_fail_cause_code": 7,
                "ups_status_code": 2,
                "powernet_output_voltage_tenths": 1234,
                "powernet_output_frequency_tenths": 600,
                "powernet_output_current_tenths": 67,
                "powernet_output_active_power": 785,
                "powernet_output_apparent_power": 823,
                "powernet_output_load_tenths": 291,
                "output_efficiency_tenths": 961,
                "output_energy_hundredths_kwh": 1830251,
                "self_test_result_code": 1,
                "self_test_last_date_raw": "05/14/2026",
            }
        )

        self.assertEqual(data.value("battery_status"), "normal")
        self.assertEqual(data.value("battery_charge"), 99.7)
        self.assertEqual(data.value("battery_temperature"), 22.4)
        self.assertEqual(data.value("battery_voltage"), 130.2)
        self.assertEqual(data.value("battery_replace_indicator"), "ok")
        self.assertEqual(data.value("battery_last_replace_date"), date(2022, 4, 7))
        self.assertEqual(
            data.value("battery_recommended_replace_date"),
            date(2027, 7, 24),
        )
        self.assertEqual(data.value("input_voltage"), 123.4)
        self.assertEqual(data.value("input_frequency"), 60.0)
        self.assertEqual(data.value("input_line_fail_cause"), "small_momentary_spike")
        self.assertEqual(data.value("ups_status"), "online")
        self.assertEqual(data.value("output_voltage"), 123.4)
        self.assertEqual(data.value("output_frequency"), 60.0)
        self.assertEqual(data.value("output_current"), 6.7)
        self.assertEqual(data.value("output_power"), 785)
        self.assertEqual(data.value("output_apparent_power"), 823)
        self.assertEqual(data.value("output_power_factor"), 95.4)
        self.assertEqual(data.value("output_load"), 29.1)
        self.assertEqual(data.value("output_efficiency"), 96.1)
        self.assertEqual(data.value("output_energy"), 18302.51)
        self.assertEqual(data.value("self_test_result"), "ok")
        self.assertEqual(data.value("self_test_last_date"), date(2026, 5, 14))

    def test_parses_international_date_formats(self) -> None:
        """NMC date strings can follow non-US display locale formats."""
        data = snmp.build_ups_data(
            {
                "battery_last_replace_date_raw": "24/07/2022",
                "battery_recommended_replace_date_raw": "2027/07/24",
                "self_test_last_date_raw": "14/05/26",
            }
        )

        self.assertEqual(data.value("battery_last_replace_date"), date(2022, 7, 24))
        self.assertEqual(
            data.value("battery_recommended_replace_date"),
            date(2027, 7, 24),
        )
        self.assertEqual(data.value("self_test_last_date"), date(2026, 5, 14))

    def test_parses_ambiguous_slash_dates_us_first(self) -> None:
        """Ambiguous slash-formatted NMC dates are interpreted US-first."""
        cases = {
            "05/04/2026": date(2026, 5, 4),
            "13/04/2026": date(2026, 4, 13),
            "04/13/2026": date(2026, 4, 13),
            "01/02/2026": date(2026, 1, 2),
            "2026-05-25": date(2026, 5, 25),
            "2026/05/25": date(2026, 5, 25),
        }

        for value, expected in cases.items():
            with self.subTest(value=value):
                self.assertEqual(snmp._date(value), expected)

    def test_preserves_zero_powernet_values(self) -> None:
        """PowerNet zero readings are not treated as missing fallbacks."""
        data = snmp.build_ups_data(
            {
                "powernet_battery_charge_tenths": 0,
                "battery_charge": 100,
                "powernet_output_active_power": 0,
                "output_power": 100,
                "powernet_output_load_tenths": 0,
                "output_load": 100,
            }
        )

        self.assertEqual(data.value("battery_charge"), 0.0)
        self.assertEqual(data.value("output_power"), 0)
        self.assertEqual(data.value("output_load"), 0.0)

    def test_uses_supplied_fallbacks_when_identity_is_missing(self) -> None:
        """Missing identity still yields a stable name and unique id."""
        data = snmp.build_ups_data(
            {},
            fallback_name="192.0.2.10",
            fallback_unique_id="192.0.2.10:161",
        )

        self.assertEqual(data.name, "192.0.2.10")
        self.assertEqual(data.unique_id, "192_0_2_10_161")

    def test_selects_ethernet_mac_address(self) -> None:
        """IF-MIB selection prefers the ethernet interface MAC address."""
        mac_address = snmp._select_interface_mac_address(
            {"1": 24, "2": snmp.ETHERNET_CSMACD_IF_TYPE},
            {
                "1": bytes.fromhex("112233445566"),
                "2": bytes.fromhex("00c0b7123456"),
            },
        )

        self.assertEqual(mac_address, "00:c0:b7:12:34:56")

    def test_requires_ethernet_type_for_mac_address(self) -> None:
        """IF-MIB selection rejects physical addresses without ethernet type."""
        mac_address = snmp._select_interface_mac_address(
            {},
            {
                "1": "00:00:00:00:00:00",
                "2": "28-29-86-AA-BB-CC",
            },
        )

        self.assertEqual(mac_address, None)

    def test_async_get_mac_address_caches_successful_resolution(self) -> None:
        """Successful MAC discovery is cached across refreshes."""

        class FakeSNMPClient(snmp.SNMPClient):
            """SNMP client that records IF-MIB walks."""

            def __init__(self) -> None:
                """Initialize the fake client."""
                super().__init__(snmp.SNMPConnectionConfig(host="192.0.2.10"))
                self.walk_count = 0

            async def _async_walk_column(self, column_oid: str) -> dict[str, object]:
                """Return fake IF-MIB column values."""
                self.walk_count += 1
                if column_oid == snmp.IF_TYPE_OID:
                    return {"1": snmp.ETHERNET_CSMACD_IF_TYPE}
                return {"1": bytes.fromhex("00c0b7123456")}

        client = FakeSNMPClient()

        first_mac_address = asyncio.run(client.async_get_mac_address())
        second_mac_address = asyncio.run(client.async_get_mac_address())

        self.assertEqual(first_mac_address, "00:c0:b7:12:34:56")
        self.assertEqual(second_mac_address, "00:c0:b7:12:34:56")
        self.assertEqual(client.walk_count, 2)

        client.close()
        self.assertEqual(client._mac_address, None)

    def test_async_get_mac_address_rejects_cached_value_after_close(self) -> None:
        """Closed clients do not return stale cached MAC addresses."""
        client = snmp.SNMPClient(snmp.SNMPConnectionConfig(host="192.0.2.10"))
        client.close()
        client._mac_address = "00:c0:b7:12:34:56"

        with self.assertRaises(snmp.SNMPError):
            asyncio.run(client.async_get_mac_address())

    def test_async_get_mac_address_does_not_cache_after_close(self) -> None:
        """MAC discovery that finishes after close does not repopulate the cache."""

        class FakeSNMPClient(snmp.SNMPClient):
            """SNMP client that blocks IF-MIB walks for close-race testing."""

            def __init__(self) -> None:
                """Initialize the fake client."""
                super().__init__(snmp.SNMPConnectionConfig(host="192.0.2.10"))
                self.release_walk = threading.Event()
                self.walk_count = 0
                self.walk_started = threading.Event()

            async def _async_walk_column(self, column_oid: str) -> dict[str, object]:
                """Return fake IF-MIB values after the test releases the walk."""
                self.walk_count += 1
                self.walk_started.set()
                if not await asyncio.to_thread(self.release_walk.wait, 1.0):
                    raise TimeoutError("test did not release IF-MIB walk")
                if column_oid == snmp.IF_TYPE_OID:
                    return {"1": snmp.ETHERNET_CSMACD_IF_TYPE}
                return {"1": bytes.fromhex("00c0b7123456")}

        client = FakeSNMPClient()

        async def run_probe() -> None:
            """Close the client while MAC discovery is still in flight."""
            mac_task = asyncio.create_task(client.async_get_mac_address())
            self.assertTrue(await asyncio.to_thread(client.walk_started.wait, 1.0))
            client.close()
            client.release_walk.set()
            with self.assertRaises(snmp.SNMPError):
                await mac_task

        asyncio.run(run_probe())

        self.assertEqual(client._mac_address, None)
        self.assertEqual(client.walk_count, 1)

    def test_async_get_mac_address_retries_missing_resolution(self) -> None:
        """Missing MAC discovery is not cached."""

        class FakeSNMPClient(snmp.SNMPClient):
            """SNMP client that records IF-MIB walks without ethernet rows."""

            def __init__(self) -> None:
                """Initialize the fake client."""
                super().__init__(snmp.SNMPConnectionConfig(host="192.0.2.10"))
                self.walk_count = 0

            async def _async_walk_column(self, column_oid: str) -> dict[str, object]:
                """Return fake IF-MIB column values."""
                self.walk_count += 1
                if column_oid == snmp.IF_TYPE_OID:
                    return {}
                return {"1": bytes.fromhex("00c0b7123456")}

        client = FakeSNMPClient()

        first_mac_address = asyncio.run(client.async_get_mac_address())
        second_mac_address = asyncio.run(client.async_get_mac_address())

        self.assertEqual(first_mac_address, None)
        self.assertEqual(second_mac_address, None)
        self.assertEqual(client.walk_count, 4)

    def test_first_result_bind_preserves_flat_var_bind(self) -> None:
        """Flat PySNMP GETNEXT bindings are already `(oid, value)` pairs."""
        var_bind = ("1.3.6.1.2.1.2.2.1.6.1", bytes.fromhex("00c0b7123456"))

        self.assertEqual(snmp._first_result_bind([var_bind]), var_bind)

    def test_first_result_bind_unwraps_nested_table_row(self) -> None:
        """Nested PySNMP GETNEXT table rows unwrap to the first varBind pair."""
        var_bind = ("1.3.6.1.2.1.2.2.1.6.1", bytes.fromhex("00c0b7123456"))

        self.assertEqual(snmp._first_result_bind([[var_bind]]), var_bind)

    def test_close_prefers_modern_transport_dispatcher(self) -> None:
        """Closing SNMP clients does not touch deprecated dispatcher aliases."""

        class FakeTransportDispatcher:
            """Fake PySNMP transport dispatcher."""

            def __init__(self) -> None:
                """Initialize the fake dispatcher."""
                self.closed = False

            def close_dispatcher(self) -> None:
                """Record dispatcher close calls."""
                self.closed = True

        class FakeSNMPEngine:
            """Fake PySNMP engine with modern and deprecated dispatcher names."""

            def __init__(self) -> None:
                """Initialize the fake engine."""
                self.transport_dispatcher = FakeTransportDispatcher()

            @property
            def transportDispatcher(self) -> FakeTransportDispatcher:  # noqa: N802
                """Raise if the deprecated dispatcher alias is touched."""
                warnings.warn(
                    "transportDispatcher is deprecated",
                    DeprecationWarning,
                    stacklevel=2,
                )
                return self.transport_dispatcher

        client = snmp.SNMPClient(snmp.SNMPConnectionConfig(host="192.0.2.10"))
        engine = FakeSNMPEngine()
        client._snmp_engine = engine

        with warnings.catch_warnings():
            warnings.simplefilter("error", DeprecationWarning)
            client.close()

        self.assertTrue(engine.transport_dispatcher.closed)

    def test_close_supports_legacy_transport_dispatcher(self) -> None:
        """Closing SNMP clients supports old PySNMP dispatcher aliases."""

        class FakeTransportDispatcher:
            """Fake legacy PySNMP transport dispatcher."""

            def __init__(self) -> None:
                """Initialize the fake dispatcher."""
                self.closed = False

            def closeDispatcher(self) -> None:  # noqa: N802
                """Record legacy dispatcher close calls."""
                self.closed = True

        class FakeSNMPEngine:
            """Fake PySNMP engine with only the deprecated dispatcher name."""

            def __init__(self) -> None:
                """Initialize the fake engine."""
                self.transportDispatcher = FakeTransportDispatcher()

        client = snmp.SNMPClient(snmp.SNMPConnectionConfig(host="192.0.2.10"))
        engine = FakeSNMPEngine()
        client._snmp_engine = engine

        client.close()

        self.assertTrue(engine.transportDispatcher.closed)


if __name__ == "__main__":
    unittest.main()
