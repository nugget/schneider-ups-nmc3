# APC UPS NMC

[![HACS Custom](https://img.shields.io/badge/HACS-Custom-41BDF5.svg?style=flat-square)](https://www.hacs.xyz/)
[![CI](https://img.shields.io/github/actions/workflow/status/nugget/schneider-ups-nmc/ci.yml?branch=main&style=flat-square&label=ci)](https://github.com/nugget/schneider-ups-nmc/actions/workflows/ci.yml)
[![Manifest version](https://img.shields.io/badge/dynamic/json?style=flat-square&label=manifest&query=%24.version&url=https%3A%2F%2Fraw.githubusercontent.com%2Fnugget%2Fschneider-ups-nmc%2Fmain%2Fcustom_components%2Fschneider_ups_nmc%2Fmanifest.json)](https://github.com/nugget/schneider-ups-nmc/blob/main/custom_components/schneider_ups_nmc/manifest.json)
[![Release](https://img.shields.io/github/v/release/nugget/schneider-ups-nmc?style=flat-square&label=release)](https://github.com/nugget/schneider-ups-nmc/releases)
[![License](https://img.shields.io/github/license/nugget/schneider-ups-nmc?style=flat-square)](LICENSE)

Home Assistant custom integration for APC by Schneider Electric UPS units with
network management cards.

This integration is intended for HACS installation. It uses local SNMP polling
as the source of truth for UPS telemetry and can optionally listen for local
syslog push events from one or more NMC cards. Current support is developed and
tested against NMC3 hardware while the repository and Home Assistant domain leave
room for additional Schneider Electric/APC Network Management Card generations.
The integration is read-only and exposes UPS identity, battery, input, output,
load, energy, self-test, replacement, and alarm telemetry from the RFC1628
UPS-MIB plus Schneider Electric APC PowerNet MIB fields where useful.

## Requirements

- An APC by Schneider Electric UPS with a supported Network Management Card.
- SNMP enabled on the NMC web or CLI interface.
- Either SNMPv2c read-only community access or SNMPv3 credentials.

SNMPv3 is preferred. If you use SNMPv2c, use a read-only community and restrict
the NMC access control list to your Home Assistant host.

## Installation

1. Add this repository as a custom integration repository in HACS.
2. Install **APC UPS NMC**.
3. Restart Home Assistant.
4. Go to **Settings > Devices & services > Add integration**.
5. Search for **APC UPS NMC** and enter the NMC host and SNMP credentials.

The setup flow validates the SNMP settings before creating an entry. SNMP
community strings and SNMPv3 passphrases are entered as password fields in Home
Assistant, and diagnostics redact stored SNMP secrets before they are exposed
for support.

Each UPS/NMC card should be added as its own integration entry with its own
host or IP address. The integration uses the UPS identity learned from SNMP to
avoid duplicate entries and to protect reconfiguration from accidentally
pointing an existing Home Assistant device at a different UPS.

After setup, use **Reconfigure** from the integration entry to change the NMC
host, SNMP port, SNMP version, or SNMP credentials without deleting and
re-adding the device. Polling interval and syslog listener settings live in the
entry options.

## Current entities

- UPS and battery status, battery charge, runtime, voltage, current,
  temperature, pack count, replacement status, replacement dates, and battery
  SKU diagnostics.
- Input voltage, frequency, current, power, line fault counter, and last
  transfer reason.
- Output source, voltage, frequency, current, real power, apparent power, load,
  efficiency, and total energy.
- Self-test result and last self-test date.
- Active alarm count.
- Binary sensors for on battery, battery low, battery needs replacing, and alarm
  present.
- A syslog event entity whose event type is the pushed syslog severity and whose
  event data includes the NMC message, category, facility, timestamp, and packet
  source.

Entities whose backing OID is not exposed by a particular UPS model or firmware
report unavailable rather than presenting a fresh but ambiguous unknown value.

## Notes

The first telemetry pass queries line index `1` for input and output table
values. That matches common single-phase UPS deployments. Multi-phase and
multi-output UPS support should grow from real NMC walks so the entity model
matches what the card actually reports.

When the NMC exposes a physical network interface through IF-MIB, the
integration registers the NMC MAC address as a Home Assistant device
connection. That helps Home Assistant coalesce the UPS device with discovery or
future integrations that identify the same network card by MAC address.

The Home Assistant device registry entry also includes the NMC web
configuration URL derived from the configured SNMP host, plus manufacturer,
model, serial number, and firmware details when the NMC exposes them.

The integration opens a shared UDP syslog listener on port `1514`. Configure
one or more NMC cards to send syslog events to the Home Assistant host on that
port. Events are routed to configured UPS entries by packet source IP and used
to fire the entry's syslog event entity and request an immediate SNMP refresh
while SNMP polling remains the source of truth for telemetry.

The syslog listener can be disabled or moved to another bind address and UDP
port from the integration options. Because Home Assistant only needs one local
syslog socket for all configured UPS entries, every syslog-enabled entry should
use the same listener settings.

If the listener cannot bind its configured address and port, or if two
syslog-enabled entries request different listener settings, the integration
raises a Home Assistant Repair issue with the settings that need attention.

## License

APC UPS NMC is released under the [Apache License 2.0](LICENSE),
matching Home Assistant's source license.
