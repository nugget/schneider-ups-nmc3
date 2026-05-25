# Schneider Electric UPS NMC3

Home Assistant custom integration for UPS units managed by Schneider Electric
APC Network Management Card 3 hardware.

This integration is intended for HACS installation and uses local SNMP polling.
The first implementation is read-only and exposes UPS identity, battery, input,
output, load, energy, self-test, replacement, and alarm telemetry from the
RFC1628 UPS-MIB plus Schneider Electric APC PowerNet MIB fields where useful.

## Requirements

- A Schneider Electric APC UPS with an NMC3 card.
- SNMP enabled on the NMC3 web or CLI interface.
- Either SNMPv2c read-only community access or SNMPv3 credentials.

SNMPv3 is preferred. If you use SNMPv2c, use a read-only community and restrict
the NMC access control list to your Home Assistant host.

## Installation

1. Add this repository as a custom integration repository in HACS.
2. Install **Schneider Electric UPS NMC3**.
3. Restart Home Assistant.
4. Go to **Settings > Devices & services > Add integration**.
5. Search for **Schneider Electric UPS NMC3** and enter the NMC host and SNMP
   credentials.

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

## Notes

The first telemetry pass queries line index `1` for input and output table
values. That matches common single-phase UPS deployments. Multi-phase and
multi-output UPS support should grow from real NMC3 walks so the entity model
matches what the card actually reports.

When the NMC exposes a physical network interface through IF-MIB, the
integration registers the NMC MAC address as a Home Assistant device
connection. That helps Home Assistant coalesce the UPS device with discovery or
future integrations that identify the same network card by MAC address.

The NMC3 syslog test message has been probed and a parser exists for its
RFC5424-style event format. The Home Assistant integration does not yet open a
local syslog listener or subscribe entities to push events.
